"""Next move, Test it and the plan (ADR 0018, Tier 1, top priority).

- GET /v1/next-move: FinanceSnapshot (W1) + MacroTable (W1) -> lifeline_engine.next_move (W2). The latest
  response and the hash of its macro table are stored per subject, so Test it and Do this refer to the same moves.
- POST /v1/next-move/test: one scenario per option (W2 option_policy -> W3 play_scenario) with the same seed and
  the same pinned macro table. Each scenario is stored as a life of the caller.
- GET/POST /v1/plan: per-subject plan items.
"""

from __future__ import annotations

import asyncio
import hashlib
import secrets
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request

from lifeline_api import money
from lifeline_api.auth import Subject
from lifeline_api.errors import ApiError, not_found
from lifeline_api.routes.lives import MAX_SEED, new_life_id
from lifeline_api.sim_bridge import call_pure
from lifeline_api.state import AppState, get_state
from lifeline_api.store import LifeRecord, macro_hash
from lifeline_contracts.domain import CharacterSpec, Life
from lifeline_contracts.finance import Point
from lifeline_contracts.macro import MacroTable
from lifeline_contracts.next_move import (
    AddPlanItemRequest,
    Move,
    NextMoveResponse,
    OptionOutcome,
    PlanItem,
    PlanResponse,
    TestMoveRequest,
    TestMoveResult,
)
from lifeline_engine import next_move as next_move_engine
from lifeline_sim import api as sim_api

router = APIRouter(tags=["next-move"])

DOC_NEXT_MOVE = "next_move"
DOC_PLAN = "plan"


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def subject_seed(sub: str) -> int:
    """Stable per subject, so the same data gives the same next move."""
    digest = hashlib.sha256(f"next-move:{sub}".encode()).digest()
    return int.from_bytes(digest[:8], "big") % (MAX_SEED + 1)


async def _compute(state: AppState, sub: str) -> tuple[NextMoveResponse, str]:
    """Fresh next move. Pins the macro table so Test it replays with the same numbers."""
    snap = await money.snapshot(state, sub)
    table = await state.hub.macro_table()
    digest = macro_hash(table)
    await state.store.put_macro(digest, table)
    resp = await call_pure(
        next_move_engine.next_move, snap, table, money.today(snap), subject_seed(sub), money.returns()
    )
    resp = resp.model_copy(update={"meta": money.meta(snap), "generated_at": _utc_now()})
    await state.store.put_doc(sub, DOC_NEXT_MOVE, {"response": resp.model_dump(mode="json"), "macro_hash": digest})
    return resp, digest


async def _latest(state: AppState, sub: str) -> tuple[NextMoveResponse, str]:
    """The stored next move for this subject, or a fresh one if none is stored."""
    doc = await state.store.get_doc(sub, DOC_NEXT_MOVE)
    if doc is None:
        return await _compute(state, sub)
    return NextMoveResponse.model_validate(doc["response"]), str(doc["macro_hash"])


def _find(resp: NextMoveResponse, move_id: str) -> Move | None:
    return next((m for m in [resp.top, *resp.runners_up] if m.id == move_id), None)


async def _find_move(state: AppState, sub: str, move_id: str) -> tuple[Move, str]:
    resp, digest = await _latest(state, sub)
    move = _find(resp, move_id)
    if move is None:
        # The stored response may be stale (e.g. a new day). Recompute once before answering 404.
        resp, digest = await _compute(state, sub)
        move = _find(resp, move_id)
    if move is None:
        raise not_found(f"Unknown move {move_id}")
    return move, digest


@router.get("/v1/next-move", response_model=NextMoveResponse, response_model_exclude_none=True)
async def get_next_move(request: Request, sub: Subject) -> NextMoveResponse:
    resp, _ = await _compute(get_state(request), sub)
    return resp


# ---------- Test it ----------


def scenario_seed(sub: str, move_id: str) -> int:
    """Same seed for every option of one move, and the same seed when the caller tests the move again."""
    digest = hashlib.sha256(f"test-it:{sub}:{move_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big") % (MAX_SEED + 1)


def shift_to_period(character: CharacterSpec, this_year: int, start_year: int) -> CharacterSpec:
    """Today's you, placed in the past period: same age at start_year as now, same money figures."""
    birth = character.birth_year - (this_year - start_year)
    return character.model_copy(update={"birth_year": max(1930, min(2026, birth))})


def _year_end(life: Life) -> list[tuple[int, float]]:
    """Net worth at the end of each year (the last history entry per year), in year order."""
    by_year: dict[int, float] = {}
    for h in life.history:
        by_year[h.year] = h.net_worth
    return sorted(by_year.items())


def worst_year_of(path: list[tuple[int, float]], fallback_year: int) -> tuple[int, float]:
    """Year with the largest fall (or smallest rise) in net worth vs the year before. The first point is the start."""
    if len(path) < 2:
        return (path[0][0] if path else fallback_year), 0.0
    changes = [(y, v - pv) for (_, pv), (y, v) in zip(path, path[1:], strict=False)]
    return min(changes, key=lambda c: (c[1], c[0]))


def outcome_from_life(option_id: str, label: str, is_recommended: bool, life: Life) -> OptionOutcome:
    path = _year_end(life)
    points = [Point(date=f"{y}-12-31", value=round(v, 2)) for y, v in path]
    worst_year, worst_change = worst_year_of(path, life.year)
    return OptionOutcome(
        option_id=option_id,
        label=label,
        is_recommended=is_recommended,
        life_id=life.id,
        net_worth_path=points,
        end_net_worth=round(life.finances.net_worth, 2),
        total_cost=round(scenario_cost(life), 2),
        missed_payments=life.index.missed_payments,
        worst_year=worst_year,
        worst_year_change=round(worst_change, 2),
        index=life.index.value,
    )


def scenario_cost(life: Life) -> float:
    """GBP paid over the period. Uses the sim's own figure when it reports one."""
    fn: Any = getattr(sim_api, "scenario_cost", None)
    if fn is not None:
        return float(fn(life))
    return 0.0


def _gbp(x: float) -> str:
    return f"£{abs(x):,.0f}"


def summary_sentence(outcomes: list[OptionOutcome], end_year: int) -> str:
    """Plain English. Every number comes from the outcomes."""
    ranked = sorted(outcomes, key=lambda o: o.end_net_worth, reverse=True)
    best, runner = ranked[0], ranked[1] if len(ranked) > 1 else None
    if runner is None:
        return f"“{best.label}” ended {end_year} with a net worth of {_gbp(best.end_net_worth)}."
    gap = best.end_net_worth - runner.end_net_worth
    if gap < 1:
        return f"“{best.label}” and “{runner.label}” ended {end_year} level."
    return (f"“{best.label}” left you {_gbp(gap)} better off by {end_year} "
            f"than “{runner.label}”.")


def _evidence_sentence(move: Move) -> str:
    text = move.confidence_label.strip()
    return text if text.endswith(".") else f"{text}."


async def _play(state: AppState, sub: str, character: CharacterSpec, move: Move, option_id: str, seed: int,
                table: MacroTable, digest: str) -> Life:
    assert move.test_period is not None
    policy: dict[str, str] = await call_pure(next_move_engine.option_policy, move, option_id)
    life_id = new_life_id()
    life: Life = await call_pure(
        sim_api.play_scenario, life_id, character, move.test_period.start, move.test_period.end, policy, seed, table
    )
    await state.store.create(LifeRecord(id=life.id, owner=sub, life=life, macro_hash=digest))
    return life


@router.post("/v1/next-move/test", response_model=TestMoveResult, response_model_exclude_none=True)
async def test_next_move(body: TestMoveRequest, request: Request, sub: Subject) -> TestMoveResult:
    state = get_state(request)
    move, digest = await _find_move(state, sub, body.move_id)
    if not move.testable or move.test_period is None:
        raise ApiError(409, "not_testable", "This move cannot be tested in a past period yet")
    by_id = {o.id: o for o in move.options}
    wanted = body.option_ids or [o.id for o in move.options]
    unknown = [o for o in wanted if o not in by_id]
    if unknown:
        raise not_found(f"Unknown option {unknown[0]} for move {move.id}")
    wanted = list(dict.fromkeys(wanted))

    table = await state.store.get_macro(digest)
    if table is None:
        # The pinned table is gone (store reset). Pin the current table instead.
        table = await state.hub.macro_table()
        digest = macro_hash(table)
        await state.store.put_macro(digest, table)

    snap = await money.snapshot(state, sub)
    _, character = await call_pure(money.engine_profile, sub, snap)
    character = shift_to_period(character, money.today(snap).year, move.test_period.start)
    seed = scenario_seed(sub, move.id)
    lives = await asyncio.gather(*(_play(state, sub, character, move, oid, seed, table, digest) for oid in wanted))

    outcomes = [
        outcome_from_life(oid, by_id[oid].label, by_id[oid].is_recommended, life)
        for oid, life in zip(wanted, lives, strict=True)
    ]
    return TestMoveResult(
        move_id=move.id,
        period=move.test_period,
        character=character,
        outcomes=outcomes,
        summary=summary_sentence(outcomes, move.test_period.end),
        evidence_sentence=_evidence_sentence(move),
        sources=move.sources,
    )


# ---------- plan ----------


def _plan_response(items: list[PlanItem]) -> PlanResponse:
    return PlanResponse(items=items, total_impact_per_year=round(sum(i.impact_per_year for i in items), 2))


async def _plan_items(state: AppState, sub: str) -> list[PlanItem]:
    doc = await state.store.get_doc(sub, DOC_PLAN)
    return [PlanItem.model_validate(x) for x in (doc or [])]


@router.get("/v1/plan", response_model=PlanResponse, response_model_exclude_none=True)
async def get_plan(request: Request, sub: Subject) -> PlanResponse:
    return _plan_response(await _plan_items(get_state(request), sub))


@router.post("/v1/plan", status_code=201, response_model=PlanItem, response_model_exclude_none=True)
async def add_plan_item(body: AddPlanItemRequest, request: Request, sub: Subject) -> PlanItem:
    state = get_state(request)
    move, _ = await _find_move(state, sub, body.move_id)
    async with state.subject_locks[f"{sub}:{DOC_PLAN}"]:
        items = await _plan_items(state, sub)
        existing = next((i for i in items if i.move_id == move.id), None)
        if existing is not None:
            return existing  # Adding the same move twice keeps one item.
        item = PlanItem(
            id=f"pl_{secrets.token_hex(6)}",
            move_id=move.id,
            kind=move.kind,
            action=move.action,
            impact_per_year=move.impact_per_year,
            added_at=_utc_now(),
        )
        items.append(item)
        await state.store.put_doc(sub, DOC_PLAN, [i.model_dump(mode="json") for i in items])
    return item
