"""Ribbons: achievements earned during a life.

A ribbon is earned once and kept. Each reason ends with the year in brackets, for example
"You owned a home at 29 (2011).", so rewind can drop ribbons earned at or after the target year.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from lifeline_contracts.domain import Ribbon, YearLog
from lifeline_sim.state import SimState

_YEAR = re.compile(r"\((\d{4})\)\.?$")
MILLION = 1_000_000.0
PENSION_POT_TARGET = 100_000.0
EMERGENCY_MONTHS = 6.0
BEAT_TWIN_INDEX = 110.0
SCHOLAR_CONCEPTS = 10
CRASH_YEARS = (2008, 2009)


@dataclass(frozen=True)
class RibbonCtx:
    s: SimState
    history: list[YearLog]
    index: float
    concepts: int


@dataclass(frozen=True)
class RibbonSpec:
    id: str
    title: str
    emoji: str
    earned: Callable[[RibbonCtx], bool]
    reason: Callable[[RibbonCtx], str]


def _missed_in(history: list[YearLog], years: tuple[int, ...]) -> bool:
    return any(h.year in years and h.decision_id is None and "You missed" in h.text for h in history)


def _started_in_debt(s: SimState) -> bool:
    c = s.character
    return c.debt > 0 or c.mortgage_balance > 0 or s.nw0 < 0


RIBBONS: tuple[RibbonSpec, ...] = (
    RibbonSpec(
        "homeowner", "Homeowner", "🏡",
        lambda c: c.s.housing in ("own", "mortgage") and c.s.character.housing in ("rent", "parents"),
        lambda c: f"You owned a home at {c.s.age} ({c.s.year}).",
    ),
    RibbonSpec(
        "mortgage-free", "Mortgage free", "🔓",
        lambda c: c.s.housing == "own" and c.s.property_value > 0 and c.s.character.housing != "own",
        lambda c: f"You paid off your mortgage at {c.s.age} ({c.s.year}).",
    ),
    RibbonSpec(
        "debt-free", "Debt free", "🧹",
        lambda c: _started_in_debt(c.s) and c.s.other_debt <= 0 and c.s.student_loan <= 0
        and c.s.mortgage_balance <= 0,
        lambda c: f"You owed nothing at {c.s.age} ({c.s.year}).",
    ),
    RibbonSpec(
        "millionaire", "Millionaire", "💎",
        lambda c: c.s.net_worth >= MILLION,
        lambda c: f"Your net worth passed £1,000,000 at {c.s.age} ({c.s.year}).",
    ),
    RibbonSpec(
        "safety-net", "Safety net", "🛟",
        lambda c: c.s.monthly_costs > 0 and c.s.cash + c.s.savings >= EMERGENCY_MONTHS * c.s.monthly_costs,
        lambda c: f"You held 6 months of costs in cash and savings ({c.s.year}).",
    ),
    RibbonSpec(
        "crash-survivor", "Crash survivor", "🛡️",
        lambda c: c.s.start_year <= 2007 and c.s.year >= 2010 and not _missed_in(c.history, CRASH_YEARS),
        lambda c: f"You got through 2008 and 2009 with no missed payment ({c.s.year}).",
    ),
    RibbonSpec(
        "beat-the-twin", "Beat the twin", "🏁",
        lambda c: c.index >= BEAT_TWIN_INDEX,
        lambda c: f"Your Index reached {c.index:.0f} at {c.s.age} ({c.s.year}).",
    ),
    RibbonSpec(
        "scholar", "Scholar", "🎓",
        lambda c: c.concepts >= SCHOLAR_CONCEPTS,
        lambda c: f"You unlocked {c.concepts} concepts ({c.s.year}).",
    ),
    RibbonSpec(
        "pension-builder", "Pension builder", "👵",
        lambda c: c.s.pension >= PENSION_POT_TARGET,
        lambda c: f"Your pension passed £100,000 at {c.s.age} ({c.s.year}).",
    ),
    RibbonSpec(
        "centenarian", "Centenarian", "🎂",
        lambda c: c.s.age >= 100,
        lambda c: f"You reached 100 ({c.s.year}).",
    ),
    RibbonSpec(
        "never-missed", "Never missed a payment", "✅",
        lambda c: not c.s.alive and c.s.missed == 0,
        lambda c: f"You never missed a payment in your life ({c.s.year}).",
    ),
)  # fmt: skip


def ribbon_year(r: Ribbon) -> int | None:
    m = _YEAR.search(r.reason)
    return int(m.group(1)) if m else None


def update_ribbons(
    prev: list[Ribbon], s: SimState, history: list[YearLog], index: float, concepts: int
) -> list[Ribbon]:
    """Previous ribbons plus any newly earned, in catalogue order of earning."""
    have = {r.id for r in prev}
    out = list(prev)
    ctx = RibbonCtx(s=s, history=history, index=index, concepts=concepts)
    for spec in RIBBONS:
        if spec.id not in have and spec.earned(ctx):
            out.append(Ribbon(id=spec.id, title=spec.title, emoji=spec.emoji, reason=spec.reason(ctx)))
    return out


def ribbons_before(prev: list[Ribbon], year: int) -> list[Ribbon]:
    """Ribbons earned before `year`. Used by rewind."""
    return [r for r in prev if (ribbon_year(r) or year) < year]
