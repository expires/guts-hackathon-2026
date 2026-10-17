"""Bridge from the data hub (W1) and the money engine (W2) to the routes.

- `snapshot(state, sub)`: the caller's FinanceSnapshot, cached per subject for a short time.
- `meta(snap)`: FinanceMeta for every finance response. Mock data carries the label "Sample data".
- `today(snap)`: the reference day for engine calls. It is the snapshot's `as_of` day, so results
  are deterministic for one snapshot (the engine has no clock).
- `fill_personal(state, sub, lesson)`: Lesson.personal from the PersonalFact whose concept_id matches.
"""

from __future__ import annotations

import logging
import time
from datetime import date
from typing import Any, cast

from lifeline_api.sim_bridge import call_pure
from lifeline_api.state import AppState
from lifeline_contracts.domain import CharacterSpec, DecisionProfile, Lesson
from lifeline_contracts.finance import FinanceMeta, FinanceSnapshot, PersonalFact
from lifeline_data.finance import persona_for_subject
from lifeline_engine import money as money_engine
from lifeline_engine.money import ProfileHints

log = logging.getLogger(__name__)

SNAPSHOT_TTL_SECONDS = 60.0


async def snapshot(state: AppState, sub: str) -> FinanceSnapshot:
    key = ("snapshot", sub)
    hit = state.memo.get(key)
    now = time.monotonic()
    if hit is not None and now - hit[0] < SNAPSHOT_TTL_SECONDS:
        return cast(FinanceSnapshot, hit[1])
    # `finance_snapshot` is on lifeline_data.hub.DataHub (ADR 0016); the shared Protocol does not list it yet.
    hub: Any = state.hub
    snap: FinanceSnapshot = await hub.finance_snapshot(sub)
    state.memo[key] = (now, snap)
    return snap


def meta(snap: FinanceSnapshot) -> FinanceMeta:
    return money_engine.finance_meta(snap)


def hints(sub: str, snap: FinanceSnapshot) -> ProfileHints | None:
    """Facts that bank data does not carry (name, age, place, job). Fixture data: from the persona."""
    if snap.source != "fixtures":
        return None
    p = persona_for_subject(sub)
    return ProfileHints(name=p.name, age=p.age(today(snap)), region=p.region, town=p.town, postcode=p.postcode,
                        occupation=p.occupation)


def today(snap: FinanceSnapshot) -> date:
    return date.fromisoformat(snap.as_of)


async def personal_facts(state: AppState, sub: str) -> list[PersonalFact]:
    snap = await snapshot(state, sub)
    key = ("facts", sub)
    hit = state.memo.get(key)
    if hit is not None and hit[0] is snap:
        return cast(list[PersonalFact], hit[1])
    facts = await call_pure(money_engine.personal_facts, snap)
    state.memo[key] = (snap, facts)
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


def engine_profile(sub: str, snap: FinanceSnapshot) -> tuple[DecisionProfile, CharacterSpec]:
    """The same profile for /v1/finance/profile, the next move and Test it (ADR 0018)."""
    profile, character = money_engine.profile(snap, today(snap), hints(sub, snap))
    return profile, character
