"""Challenge scoring (W3 defines the challenges and their goals in lifeline_sim.api.challenges()).

A life plays a challenge when its character id and start year match the challenge. After every write to such a
life (create, age, choice, action, rewind) the API evaluates the goal on the new state and latches the first
final result ("won" or "lost") per (life, challenge) in the per-user document "challenges". Latching matters:
a goal like "own a home by 30" is decided at the moment it happens, not by looking at the state years later.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from lifeline_api.state import AppState
from lifeline_contracts.domain import Challenge, Life

log = logging.getLogger(__name__)

DOC_CHALLENGES = "challenges"
Status = Literal["won", "lost", "in_progress"]


def matches(challenge: Challenge, life: Life) -> bool:
    return life.character.id == challenge.character_id and life.start_year == challenge.start_year


def _num(goal: dict[str, float | str], key: str) -> float:
    return float(goal[key])


def evaluate(challenge: Challenge, life: Life) -> tuple[Status, str]:
    """Status of the goal on this state of the life, and a plain-English line. Unknown goal types stay in progress."""
    g = challenge.goal
    kind = str(g.get("type", ""))
    f = life.finances
    if kind == "own_home_by_age":
        age = _num(g, "age")
        if f.property_value > 0 and life.age <= age:
            return "won", f"You owned a home at {life.age}."
        if life.age > age or not life.alive:
            return "lost", f"No home by {age:.0f}."
        return "in_progress", f"{age - life.age:.0f} years left to buy a home."
    if kind == "no_missed_payments_until":
        year = _num(g, "year")
        if life.index.missed_payments > 0:
            return "lost", f"A payment was missed before {year:.0f}."
        if life.year >= year:
            return "won", f"No missed payments up to {year:.0f}."
        if not life.alive:
            return "lost", "The life ended first."
        return "in_progress", f"Keep every payment until {year:.0f}."
    if kind == "index_at_least_by_year":
        target, year = _num(g, "index"), _num(g, "year")
        if life.index.value >= target and life.year <= year:
            return "won", f"Index {life.index.value:.0f} by {life.year}."
        if life.year >= year or not life.alive:
            return "lost", f"Index below {target:.0f} in {year:.0f}."
        return "in_progress", f"Index {life.index.value:.0f} of {target:.0f}."
    if kind == "debt_free_by_age":
        age = _num(g, "age")
        debt = f.other_debt + f.student_loan
        if debt <= 0 and life.age <= age:
            return "won", f"Debt free at {life.age}."
        if life.age > age or not life.alive:
            return "lost", f"Still in debt at {age:.0f}."
        return "in_progress", f"£{debt:,.0f} of debt left."
    if kind == "net_worth_at_least":
        amount = _num(g, "amount")
        if f.net_worth >= amount:
            return "won", f"Net worth £{f.net_worth:,.0f}."
        if not life.alive:
            return "lost", f"Net worth stayed below £{amount:,.0f}."
        return "in_progress", f"Net worth £{f.net_worth:,.0f} of £{amount:,.0f}."
    if kind == "pension_at_least_by_age":
        amount, age = _num(g, "amount"), _num(g, "age")
        if f.pension >= amount and life.age <= age:
            return "won", f"Pension £{f.pension:,.0f} at {life.age}."
        if life.age > age or not life.alive:
            return "lost", f"Pension below £{amount:,.0f} at {age:.0f}."
        return "in_progress", f"Pension £{f.pension:,.0f} of £{amount:,.0f}."
    return "in_progress", "This goal is not scored yet."


async def record(state: AppState, sub: str, life: Life, all_challenges: list[Challenge], *,
                 reset: bool = False) -> None:
    """Latch final results for the challenges this life plays. `reset` (after a rewind) clears earlier
    results for this life first. Never fails the request."""
    playing = [c for c in all_challenges if matches(c, life)]
    if not playing:
        return
    try:
        doc: dict[str, Any] = await state.store.get_doc(sub, DOC_CHALLENGES) or {}
        changed = False
        for c in playing:
            key = f"{life.id}:{c.id}"
            if reset and key in doc:
                del doc[key]
                changed = True
            if doc.get(key, {}).get("status") in ("won", "lost"):
                continue
            status, detail = evaluate(c, life)
            entry = {"life_id": life.id, "challenge_id": c.id, "status": status, "detail": detail,
                     "year": life.year}
            if doc.get(key) != entry:
                doc[key] = entry
                changed = True
        if changed:
            await state.store.put_doc(sub, DOC_CHALLENGES, doc)
    except Exception as exc:
        log.warning("challenge progress not recorded: %s", type(exc).__name__)


async def progress(state: AppState, sub: str) -> list[dict[str, Any]]:
    doc: dict[str, Any] = await state.store.get_doc(sub, DOC_CHALLENGES) or {}
    return sorted(doc.values(), key=lambda e: (e["challenge_id"], e["life_id"]))
