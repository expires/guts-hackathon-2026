"""Learn course progress per user (ADR 0068). One document per subject, kind "learn": the passed lesson ids.

A stored document that no longer validates is skipped (treated as no progress), never a 500. The judge reset
deletes it with the other per-user documents (account.erase).
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from lifeline_api.state import AppState
from lifeline_api.store import StoreUnavailable
from lifeline_sim import learn as sim_learn

log = logging.getLogger(__name__)

DOC_LEARN = "learn"
BONUS_LIVES = 50  # most recent lives read for Life game bonuses


class LearnDoc(BaseModel):
    model_config = ConfigDict(extra="ignore")

    passed: list[str] = Field(default_factory=list, max_length=500)


async def passed(state: AppState, sub: str) -> list[str]:
    raw = await state.store.get_doc(sub, DOC_LEARN)
    if raw is None:
        return []
    try:
        doc = LearnDoc.model_validate(raw)
    except ValidationError:
        log.warning("learn progress document skipped: does not validate")
        return []
    return [i for i in doc.passed if isinstance(i, str) and sim_learn.has_lesson(i)]


async def save(state: AppState, sub: str, lesson_ids: list[str]) -> None:
    await state.store.put_doc(sub, DOC_LEARN, LearnDoc(passed=lesson_ids).model_dump())


async def mark_sample_passed(state: AppState, sub: str) -> None:
    """A sample student starts with the first lessons passed, so a judge sees progress. Keeps any other passes.
    Never fails the import."""
    try:
        have = set(await passed(state, sub)) | set(sim_learn.sample_passed())
        await save(state, sub, [i for i in sim_learn.lesson_ids() if i in have])
    except Exception as exc:
        log.warning("sample learn progress not saved: %s", type(exc).__name__)


async def life_bonus(state: AppState, sub: str) -> set[str]:
    """Concept ids the user earned in any of their Life games. Empty when the lives cannot be read."""
    try:
        records = await state.store.list_by_owner(sub, limit=BONUS_LIVES)
    except StoreUnavailable:
        raise
    except Exception as exc:
        log.warning("life bonus skipped: %s", type(exc).__name__)
        return set()
    return {c for r in records for c in r.life.concepts_unlocked}
