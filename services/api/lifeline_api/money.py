"""Bridge from the data hub (W1) and the money engine (W2) to the routes.

- `snapshot(state, sub)`: the caller's FinanceSnapshot, cached per subject for a short time.
- `meta(snap)`: FinanceMeta for every finance response. Mock data carries the label "Sample data".
- `today(snap)`: the reference day for engine calls. It is the snapshot's `as_of` day, so results
  are deterministic for one snapshot (the engine has no clock).
- `fill_personal(state, sub, lesson)`: Lesson.personal from the PersonalFact whose concept_id matches.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import date
from typing import Any, cast

from lifeline_api.errors import ApiError
from lifeline_api.sim_bridge import call_pure
from lifeline_api.state import AppState
from lifeline_api.store import StoreUnavailable
from lifeline_contracts.domain import CharacterSpec, DecisionProfile, Lesson
from lifeline_contracts.finance import FinanceMeta, FinanceSnapshot, PersonalFact
from lifeline_data.finance import persona_for_subject
from lifeline_engine import money as money_engine
from lifeline_engine.money import ProfileHints

log = logging.getLogger(__name__)



def no_finance_data() -> ApiError:
    """Live mode (ADR 0027): the user has not connected or entered their own money data yet."""
    return ApiError(409, "no_finance_data", "Connect your money first.", source="data")


async def stored_snapshot(state: AppState, sub: str) -> FinanceSnapshot | None:
    """The data the user gave us (statement, manual entry, logged payments). Kept by the data hub (W1)."""
    hub: Any = state.hub
    snap: FinanceSnapshot | None = await hub.get_user_snapshot(sub)
    return snap


async def save_snapshot(state: AppState, sub: str, snap: FinanceSnapshot) -> None:
    """Replace the user's own data. Raises StoreUnavailable when it cannot be kept durably."""
    hub: Any = state.hub
    try:
        durable = await hub.set_user_snapshot(sub, snap)
    except Exception as exc:
        log.warning("user snapshot write failed: %s", type(exc).__name__)
        raise StoreUnavailable() from exc
    finally:
        forget(state, sub)
    try:
        await state.store.delete_doc(sub, "next_move")  # the stored next move was built from the old data
    except StoreUnavailable:
        log.warning("stale next move not cleared: store unavailable")
    if not durable and not state.settings.is_test and state.settings.database_url:
        raise StoreUnavailable()


async def delete_snapshot(state: AppState, sub: str) -> None:
    hub: Any = state.hub
    await hub.delete_user_snapshot(sub)
    forget(state, sub)


def forget(state: AppState, sub: str) -> None:
    """Drop every per-subject cache entry (after the user's data changes or is deleted)."""
    for key in [k for k in state.memo if len(k) > 1 and k[1] == sub]:
        state.memo.pop(key, None)


async def maybe_snapshot(state: AppState, sub: str) -> FinanceSnapshot | None:
    """The caller's FinanceSnapshot, or None when there is none (live mode without user data).

    The hub returns the user's own data first; otherwise the demo persona (demo mode) or None (live mode).
    """
    hub: Any = state.hub  # Protocol may still say FinanceSnapshot; W1 returns None in live mode (ADR 0027)
    snap: FinanceSnapshot | None = await hub.finance_snapshot(sub)
    return snap


def fingerprint(snap: FinanceSnapshot) -> str:
    """Changes whenever the snapshot content changes. Keys the per-snapshot caches."""
    return hashlib.sha256(snap.model_dump_json().encode()).hexdigest()[:16]


async def snapshot(state: AppState, sub: str) -> FinanceSnapshot:
    """The caller's FinanceSnapshot. 409 no_finance_data when there is none."""
    snap = await maybe_snapshot(state, sub)
    if snap is None:
        raise no_finance_data()
    return snap


def meta(snap: FinanceSnapshot) -> FinanceMeta:
    return money_engine.finance_meta(snap)


def hints(state: AppState, sub: str, snap: FinanceSnapshot) -> ProfileHints | None:
    """Facts that bank data does not carry (name, age, place, job).

    Fixture data: from the persona. User data: None, so the engine reads `snapshot.holder` and `region`.
    """
    if snap.source != "fixtures":
        return None
    p = persona_for_subject(sub)
    return ProfileHints(name=p.name, age=p.age(today(snap)), region=p.region, town=p.town, postcode=p.postcode,
                        occupation=p.occupation)


def today(snap: FinanceSnapshot) -> date:
    return date.fromisoformat(snap.as_of)


async def personal_facts(state: AppState, sub: str) -> list[PersonalFact]:
    """Facts from the caller's own data only. Empty when the caller has none."""
    snap = await maybe_snapshot(state, sub)
    if snap is None:
        return []
    key = ("facts", sub)
    fp = fingerprint(snap)
    hit = state.memo.get(key)
    if hit is not None and hit[0] == fp:
        return cast(list[PersonalFact], hit[1])
    facts = await call_pure(money_engine.personal_facts, snap)
    state.memo[key] = (fp, facts)
    return facts


async def fill_personal(state: AppState, sub: str, lesson: Lesson | None) -> Lesson | None:
    """Return the lesson with `personal` set from a matching PersonalFact. Never fails the request."""
    if lesson is None or lesson.personal is not None:
        return lesson
    try:
        facts = await personal_facts(state, sub)
    except Exception as exc:
        log.warning("personal facts unavailable: %s", type(exc).__name__)
        return lesson
    match = next((f for f in facts if f.concept_id == lesson.concept_id), None)
    if match is None:
        return lesson
    return lesson.model_copy(update={"personal": match.text})


def engine_profile(snap: FinanceSnapshot, hints_: ProfileHints | None) -> tuple[DecisionProfile, CharacterSpec]:
    """The same profile for /v1/finance/profile, the next move and Test it (ADR 0018)."""
    profile, character = money_engine.profile(snap, today(snap), hints_)
    return profile, character
