"""Habit score from the sim's own game ledger (Quick Life summary card, ADR 0052, ADR 0059).

Same six ratio names, targets and 0-100 scale as `lifeline_engine.habits` (the real-money score), so a player
reads one scale. The inputs are game money from the life's ledger (`SimState.ledger`), never real money:

| Component | Game ratio | 100 when | 0 when |
|---|---|---|---|
| savings_rate | (take-home - spending) / take-home, last 2 years | SAVE_TARGET (20%) or more | nothing saved |
| months_of_cover | (cash + savings) / monthly costs now | COVER_TARGET_MONTHS (3) or more | no cash |
| spend_stability | 1 - coefficient of variation of yearly spending | same each year | CV >= 1 |
| discretionary_share | 1 - wants / spending / DISCRETIONARY_CEILING, last 2 years | no wants | half or more |
| subscription_creep | 1 - subscriptions per month / monthly spending / SUBSCRIPTION_CEILING | none | 15% or more |
| debt_pressure | 1 - (card debt + missed months x month costs) / (DEBT_CEILING_MONTHS x month costs) | none | 3 mo |

Wants: weekly wants spending (a baseline that choices raise or lower, `lifeline_sim.paths.path_living`) plus
one-off spending on choices tagged `want`.
Subscriptions: the monthly change from choices tagged `subscription`. Student loans are not expensive debt.
Overall: the mean of the known components, rounded; None when fewer than MIN_COMPONENTS are known.
"""

from __future__ import annotations

import statistics

from lifeline_contracts.domain import HabitComponents, HabitScore
from lifeline_engine.habits import (
    COVER_TARGET_MONTHS,
    DEBT_CEILING_MONTHS,
    DISCRETIONARY_CEILING,
    MIN_COMPONENTS,
    SAVE_TARGET,
    SUBSCRIPTION_CEILING,
)
from lifeline_sim.state import SimState

RECENT_YEARS = 2  # savings rate, wants share and subscriptions use the last 2 ledger years (habits now)


def _score(x: float) -> int:
    return int(round(100 * min(1.0, max(0.0, x))))


def game_habit_score(s: SimState) -> HabitScore:
    rows = s.ledger
    recent = rows[-RECENT_YEARS:]
    take_home = sum(r[1] for r in recent)
    spending = sum(r[2] for r in recent)
    wants = sum(r[3] for r in recent)
    monthly = s.monthly_costs
    parts: dict[str, int | None] = dict.fromkeys(
        (
            "savings_rate",
            "months_of_cover",
            "spend_stability",
            "discretionary_share",
            "subscription_creep",
            "debt_pressure",
        )
    )
    if take_home > 0 and spending > 0:
        parts["savings_rate"] = _score((take_home - spending) / take_home / SAVE_TARGET)
    if monthly > 0:
        parts["months_of_cover"] = _score(max(0.0, s.cash + s.savings) / monthly / COVER_TARGET_MONTHS)
        # Missed payments in the last 2 ledger years count as debt: each missed month adds one month of costs.
        missed_months = sum(r[4] for r in recent)
        pressure = (s.other_debt + missed_months * monthly) / (DEBT_CEILING_MONTHS * monthly)
        parts["debt_pressure"] = _score(1.0 - pressure)
    yearly = [r[2] for r in rows]
    if len(yearly) >= 2 and statistics.fmean(yearly) > 0:
        cv = statistics.pstdev(yearly) / statistics.fmean(yearly)
        parts["spend_stability"] = _score(1.0 - cv)
    if spending > 0:
        parts["discretionary_share"] = _score(1.0 - wants / spending / DISCRETIONARY_CEILING)
        subs = max(0.0, s.tag_living.get("subscription", 0.0))
        last_month = (rows[-1][2] / 12) if rows else monthly
        if last_month > 0:
            parts["subscription_creep"] = _score(1.0 - subs / last_month / SUBSCRIPTION_CEILING)
    known = [v for v in parts.values() if v is not None]
    overall = int(round(sum(known) / len(known))) if len(known) >= MIN_COMPONENTS else None
    return HabitScore(components=HabitComponents(**parts), overall=overall)
