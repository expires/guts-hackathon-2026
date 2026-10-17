"""Habit score (ADR 0046, ADR 0052): six ratios, each 0 to 100, and an overall. Pure: no I/O, no clock, no RNG.

Every component is a ratio of the user's own amounts, so scaling all amounts by the same factor gives the same
score: income does not predict the score ("Rich or broke, it's about habits"). Friends see these scores only,
never an amount (privacy rule, ADR 0052).

| Component | Ratio | 100 when | 0 when |
|---|---|---|---|
| savings_rate | (income - spending) / income, last 3 full months | 20% or more saved | nothing saved |
| months_of_cover | cash / known monthly costs | 3 months or more | no cash |
| spend_stability | 1 - coefficient of variation (CV) of weekly spend, last 8 weeks | same each week | CV >= 1 |
| discretionary_share | 1 - (eating out, shopping, fun, travel, personal care) / spending / 0.5 | none | half or more |
| subscription_creep | 1 - subscriptions per month / monthly spending / 0.15 | none | 15% or more |
| debt_pressure | 1 - expensive debt / (3 x monthly costs) | no expensive debt | 3 months of costs or more |

A component is None when its inputs are unknown (no income, no known costs, no spending). The overall is the mean
of the known components, rounded; None when fewer than MIN_COMPONENTS are known.
"""

from __future__ import annotations

from datetime import date

import numpy as np

from lifeline_contracts.finance import Category, FinanceSnapshot, HabitComponents, HabitScore
from lifeline_engine.money.categorise import merchant_key
from lifeline_engine.money.profile import full_months_before, known_monthly_costs, liquid, monthly_spend
from lifeline_engine.money.recurring import detect_subscriptions
from lifeline_engine.money.spending import by_category
from lifeline_engine.student import detect_income, entered_monthly_income, from_snapshot, weekly_spend

DISCRETIONARY: tuple[Category, ...] = ("eating_out", "shopping", "entertainment", "travel", "personal_care")
SAVE_TARGET = 0.20
COVER_TARGET_MONTHS = 3.0
DISCRETIONARY_CEILING = 0.5
SUBSCRIPTION_CEILING = 0.15
DEBT_CEILING_MONTHS = 3.0
STABILITY_WEEKS = 8
MIN_COMPONENTS = 3

COMPONENTS: tuple[str, ...] = (
    "savings_rate",
    "months_of_cover",
    "spend_stability",
    "discretionary_share",
    "subscription_creep",
    "debt_pressure",
)


def _score(x: float) -> int:
    """Clamp a 0..1 ratio to a whole score 0..100."""
    return int(round(100 * min(1.0, max(0.0, x))))


def monthly_income(s: FinanceSnapshot, today: date) -> float | None:
    """Average monthly money in: entered income sources (ADR 0049) when given, else regular credits found in the
    data (any source). None when neither is known."""
    entered = entered_monthly_income(s)
    if entered is not None:
        return entered if entered > 0 else None
    months = full_months_before(today, 3)
    keys = {src.name for src in detect_income(s.transactions, today)}
    if not keys:
        return None
    total = sum(t.amount for t in s.transactions if t.amount > 0 and t.date[:7] in months and merchant_key(t) in keys)
    return total / len(months) if total > 0 else None


def savings_rate(s: FinanceSnapshot, today: date) -> int | None:
    income = monthly_income(s, today)
    spend = monthly_spend(s, today)
    if income is None or spend <= 0:
        return None
    return _score((income - spend) / income / SAVE_TARGET)


def months_of_cover(s: FinanceSnapshot, today: date) -> int | None:
    costs = known_monthly_costs(s, today)
    if costs is None:
        return None
    return _score(max(0.0, liquid(s)) / costs / COVER_TARGET_MONTHS)


def spend_stability(s: FinanceSnapshot, today: date) -> int | None:
    weeks = weekly_spend(s.transactions, today, STABILITY_WEEKS)
    mean = float(np.mean(weeks))
    if mean <= 0:
        return None
    cv = float(np.std(weeks)) / mean
    return _score(1.0 - cv)


def discretionary_share(s: FinanceSnapshot, today: date) -> int | None:
    months = full_months_before(today, 3)
    total = fun = 0.0
    for m in months:
        cats = by_category(s.transactions, m)
        total += sum(v for v, _ in cats.values())
        fun += sum(cats.get(c, (0.0, 0))[0] for c in DISCRETIONARY)
    if total <= 0:
        return None
    return _score(1.0 - fun / total / DISCRETIONARY_CEILING)


def subscription_creep(s: FinanceSnapshot, today: date) -> int | None:
    spend = monthly_spend(s, today)
    if spend <= 0:
        return None
    subs = sum(x.monthly_cost for x in detect_subscriptions(s.transactions, today))
    return _score(1.0 - subs / spend / SUBSCRIPTION_CEILING)


def debt_pressure(s: FinanceSnapshot, today: date) -> int | None:
    costs = known_monthly_costs(s, today)
    if costs is None:
        return None
    debt = sum(d.expensive for d in from_snapshot(s, today).debts)
    return _score(1.0 - debt / (DEBT_CEILING_MONTHS * costs))


def habit_score(s: FinanceSnapshot, today: date) -> HabitScore:
    parts: dict[str, int | None] = {
        "savings_rate": savings_rate(s, today),
        "months_of_cover": months_of_cover(s, today),
        "spend_stability": spend_stability(s, today),
        "discretionary_share": discretionary_share(s, today),
        "subscription_creep": subscription_creep(s, today),
        "debt_pressure": debt_pressure(s, today),
    }
    known = [v for v in parts.values() if v is not None]
    overall = int(round(sum(known) / len(known))) if len(known) >= MIN_COMPONENTS else None
    return HabitScore(components=HabitComponents(**parts), overall=overall)
