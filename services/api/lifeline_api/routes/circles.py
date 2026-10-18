"""Circles: friends share habit scores, never amounts (ADR 0052, 0059).

- Members see each other's HabitScore (ratios 0-100) and `improvement`: overall points now minus the member's
  own first recorded score (the baseline). Rank is by improvement, never by score or income.
- Penny's weekly recap is a template over ratios only.
- Storage (Postgres user_docs): circle "circle:<id>"/"circle", code index "circle-code:<CODE>"/"id", the user's
  circle ids under kind "circles" and the habit baseline under kind "habit_baseline".
"""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Path, Request, Response

from lifeline_api import codeguard, money
from lifeline_api.auth import Subject
from lifeline_api.errors import ApiError, not_found
from lifeline_api.names import clean_name
from lifeline_api.ratelimit import client_ip
from lifeline_api.rooms import new_circle_code
from lifeline_api.routes.rooms import _display_name as display_name
from lifeline_api.sim_bridge import call_pure
from lifeline_api.state import AppState, get_state
from lifeline_contracts.finance import HabitComponents, HabitScore
from lifeline_contracts.play import Circle, CircleMember, CirclesResponse, CreateCircleRequest, JoinCircleRequest
from lifeline_engine.habits import habit_score

log = logging.getLogger(__name__)

router = APIRouter(tags=["circles"])

CircleId = Annotated[str, Path(max_length=64)]
MAX_MEMBERS = 30
MAX_CIRCLES_PER_USER = 10
DOC_CIRCLES = "circles"
DOC_BASELINE = "habit_baseline"
HABIT_LABELS = {
    "savings_rate": "savings rate",
    "months_of_cover": "months of cover",
    "spend_stability": "spending stability",
    "discretionary_share": "fun spending share",
    "subscription_creep": "subscription control",
    "debt_pressure": "debt pressure",
}


def _owner(circle_id: str) -> str:
    return f"circle:{circle_id}"


def _code_owner(code: str) -> str:
    return f"circle-code:{code}"


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _week() -> str:
    y, w, _ = datetime.now(UTC).isocalendar()
    return f"{y}-W{w:02d}"


async def _load(state: AppState, circle_id: str) -> dict[str, Any] | None:
    doc: dict[str, Any] | None = await state.store.get_doc(_owner(circle_id), "circle")
    return doc


async def _my_ids(state: AppState, sub: str) -> list[str]:
    return list(await state.store.get_doc(sub, DOC_CIRCLES) or [])


async def _habits_of(state: AppState, sub: str) -> HabitScore:
    """The member's own habit score from their own data. No data: every ratio is unknown."""
    snap = await money.maybe_snapshot(state, sub)
    if snap is None:
        return HabitScore(components=HabitComponents())
    score: HabitScore = await call_pure(habit_score, snap, money.today(snap))
    return score


async def _improvement(state: AppState, sub: str, score: HabitScore) -> int | None:
    """Overall points vs the member's own first recorded score. The first score becomes the baseline."""
    if score.overall is None:
        return None
    base = await state.store.get_doc(sub, DOC_BASELINE)
    if base is None:
        await state.store.put_doc(sub, DOC_BASELINE, {"overall": score.overall, "at": _now()})
        return 0
    return max(-100, min(100, score.overall - int(base["overall"])))


def recap(members: list[CircleMember]) -> str | None:
    """Penny's weekly recap. Ratios and points only, never amounts."""
    ranked = [m for m in members if m.improvement is not None]
    if not ranked:
        return None
    top = max(ranked, key=lambda m: m.improvement or 0)
    if (top.improvement or 0) > 0:
        parts = [f"This week {top.name} improved most ({top.improvement:+d} points)."]
    else:
        parts = ["No change yet this week."]
    totals: dict[str, list[int]] = {}
    for m in members:
        for key, val in m.habits.components.model_dump().items():
            if val is not None:
                totals.setdefault(key, []).append(int(val))
    if totals:
        best = max(totals, key=lambda k: sum(totals[k]) / len(totals[k]))
        avg = round(sum(totals[best]) / len(totals[best]))
        parts.append(f"The circle is strongest on {HABIT_LABELS.get(best, best)}: {avg} out of 100.")
    parts.append("Rich or broke, it's about habits.")
    return " ".join(parts)[:400]


async def _view(state: AppState, doc: dict[str, Any], me: str) -> Circle:
    members: list[CircleMember] = []
    for m in doc["members"]:
        score = await _habits_of(state, m["sub"])
        name = m["name"]
        if name.startswith("Member "):  # joined before naming: use the account or sample name if there is one now
            name = await display_name(state, m["sub"]) or name
        members.append(CircleMember(id=m["id"], name=name, habits=score,
                                    improvement=await _improvement(state, m["sub"], score), is_you=m["sub"] == me))
    order = sorted([m for m in members if m.improvement is not None], key=lambda m: -(m.improvement or 0))
    ranks: dict[str, int] = {}
    for i, m in enumerate(order):
        prev = order[i - 1] if i else None
        ranks[m.id] = ranks[prev.id] if prev is not None and prev.improvement == m.improvement else i + 1
    members = [m.model_copy(update={"rank": ranks.get(m.id)}) for m in members]
    return Circle(id=doc["id"], name=doc["name"], code=doc["code"], members=members, recap=recap(members),
                  recap_week=_week())


async def _member_name(state: AppState, sub: str, doc: dict[str, Any]) -> str:
    """The account name, cleaned; else "Member N" with N unique in this circle (never reused after a leave)."""
    name = await display_name(state, sub)
    if name:
        return name
    used = [int(m["name"].split()[-1]) for m in doc.get("members", [])
            if m["name"].startswith("Member ") and m["name"].split()[-1].isdigit()]
    n = max([doc.get("member_seq", 0), *used]) + 1
    doc["member_seq"] = n
    return f"Member {n}"


@router.get("/v1/circles", response_model=CirclesResponse, response_model_exclude_none=True)
async def list_circles(request: Request, sub: Subject) -> CirclesResponse:
    state = get_state(request)
    out: list[Circle] = []
    for cid in await _my_ids(state, sub):
        doc = await _load(state, cid)
        if doc is not None and any(m["sub"] == sub for m in doc["members"]):
            out.append(await _view(state, doc, sub))
    return CirclesResponse(circles=out)


@router.post("/v1/circles", status_code=201, response_model=Circle, response_model_exclude_none=True)
async def create_circle(body: CreateCircleRequest, request: Request, sub: Subject) -> Circle:
    state = get_state(request)
    async with state.subject_locks[f"{sub}:{DOC_CIRCLES}"]:
        mine = await _my_ids(state, sub)
        if len(mine) >= MAX_CIRCLES_PER_USER:
            raise ApiError(422, "validation_error", f"You can be in up to {MAX_CIRCLES_PER_USER} circles")
        for _ in range(10):
            code = new_circle_code()
            if await state.store.get_doc(_code_owner(code), "id") is None:
                break
        circle_name = clean_name(body.name, 40)
        if circle_name is None:
            raise ApiError(422, "validation_error", "name: use letters or numbers")
        cid = f"ci_{secrets.token_hex(6)}"
        doc: dict[str, Any] = {"id": cid, "name": circle_name, "code": code, "created_at": _now(), "members": []}
        doc["members"].append({"id": f"m_{secrets.token_hex(4)}", "sub": sub,
                               "name": await _member_name(state, sub, doc), "joined_at": _now()})
        await state.store.put_doc(_owner(cid), "circle", doc)
        await state.store.put_doc(_code_owner(code), "id", {"id": cid})
        await state.store.put_doc(sub, DOC_CIRCLES, [*mine, cid])
    return await _view(state, doc, sub)


@router.post("/v1/circles/join", response_model=Circle, response_model_exclude_none=True)
async def join_circle(body: JoinCircleRequest, request: Request, sub: Subject) -> Circle:
    state = get_state(request)
    ip = client_ip(request.scope)
    await codeguard.guard(state, ip, sub)
    ref = await state.store.get_doc(_code_owner(body.code), "id")
    if ref is None:
        await codeguard.record_wrong(state, ip, sub)
        raise not_found("No circle with that code")
    cid = str(ref["id"])
    async with state.subject_locks[f"circle:{cid}"]:
        doc = await _load(state, cid)
        if doc is None:
            raise not_found("No circle with that code")
        if not any(m["sub"] == sub for m in doc["members"]):
            if len(doc["members"]) >= MAX_MEMBERS:
                raise ApiError(422, "validation_error", "This circle is full")
            name = await _member_name(state, sub, doc)
            doc["members"].append({"id": f"m_{secrets.token_hex(4)}", "sub": sub, "name": name, "joined_at": _now()})
            await state.store.put_doc(_owner(cid), "circle", doc)
    async with state.subject_locks[f"{sub}:{DOC_CIRCLES}"]:
        mine = await _my_ids(state, sub)
        if cid not in mine:
            await state.store.put_doc(sub, DOC_CIRCLES, [*mine, cid])
    return await _view(state, doc, sub)


async def leave(state: AppState, sub: str, cid: str) -> bool:
    """Remove the member. The last member out deletes the circle and its code. False if not a member."""
    async with state.subject_locks[f"circle:{cid}"]:
        doc = await _load(state, cid)
        if doc is None or not any(m["sub"] == sub for m in doc["members"]):
            return False
        doc["members"] = [m for m in doc["members"] if m["sub"] != sub]
        if doc["members"]:
            await state.store.put_doc(_owner(cid), "circle", doc)
        else:
            await state.store.delete_doc(_owner(cid), "circle")
            await state.store.delete_doc(_code_owner(doc["code"]), "id")
    async with state.subject_locks[f"{sub}:{DOC_CIRCLES}"]:
        mine = [c for c in await _my_ids(state, sub) if c != cid]
        await state.store.put_doc(sub, DOC_CIRCLES, mine)
    return True


@router.post("/v1/circles/{circle_id}/leave", status_code=204)
async def leave_circle(circle_id: CircleId, request: Request, sub: Subject) -> Response:
    if not await leave(get_state(request), sub, circle_id):
        raise not_found("Circle not found")
    return Response(status_code=204)


async def leave_all(state: AppState, sub: str) -> None:
    """Account reset or deletion: leave every circle."""
    for cid in await _my_ids(state, sub):
        try:
            await leave(state, sub, cid)
        except Exception as exc:
            log.warning("circle not left on reset: %s", type(exc).__name__)
