"""Habit vector: ratios and scores only. No money fields leave the device.

Window choice: the last ``window_months`` complete calendar months ending at
or before ``as_of``. If ``as_of`` is the last day of its month, that month is
included (e.g. as_of 2026-09-30, 6 months -> Apr..Sep 2026); otherwise the
current (incomplete) month is excluded.
"""

from __future__ import annotations

import calendar
import statistics
from collections import defaultdict
from collections.abc import Sequence
from datetime import date
from typing import Literal

from pydantic import BaseModel

from playyourself.decision.scoring import score_factor
from playyourself.domain.models import DISCRETIONARY_CATEGORIES, Snapshot, Transaction

FACTOR_NAMES = (
    "savings_rate",
    "runway_months",
    "spend_stability",
    "discretionary_share",
    "subscription_creep",
    "isa_diversification",
    "shock_resilience",
)
_SPEND_BASED = (
    "savings_rate",
    "runway_months",
    "spend_stability",
    "discretionary_share",
    "subscription_creep",
    "shock_resilience",
)
_INSUFFICIENT = "insufficient history"


class FactorValue(BaseModel):
    raw: float | None
    score: int | None
    reason: str | None = None


class Window(BaseModel):
    months: int
    end: date


class HabitVector(BaseModel):
    version: Literal["hv-1"] = "hv-1"
    window: Window
    factors: dict[str, FactorValue]


def effective_n(hhi: float) -> float:
    """Effective number of equally weighted holdings, 1/HHI."""
    return 1.0 / hhi


def _midx(d: date) -> int:
    return d.year * 12 + d.month - 1


def _month_end(idx: int) -> date:
    y, m = divmod(idx, 12)
    return date(y, m + 1, calendar.monthrange(y, m + 1)[1])


# Recurring housing obligations look exactly like subscriptions (same amount, monthly) but
# aren't discretionary, so they're excluded by merchant keyword. Category alone can't do it:
# Monzo files rent and phone contracts alike under "bills".
NON_SUBSCRIPTION_KEYWORDS = ("RENT", "LANDLORD", "MORTGAGE", "COUNCIL TAX", "LETTING")
# Subscriptions bill on a fixed day; allow drift for short months and weekends.
MAX_BILLING_DAY_SPREAD = 6


def detect_subscriptions(transactions: Sequence[Transaction]) -> list[str]:
    """Merchants with monthly recurring outflows.

    Same merchant, outflows in >=3 distinct months, every amount within +-10%
    of the merchant's median, median gap between payments 25-35 days, and billed on a
    fixed day of month (spread <= MAX_BILLING_DAY_SPREAD; month-end wraparound is ignored).
    Housing obligations (NON_SUBSCRIPTION_KEYWORDS) are excluded.
    """
    by_merchant: dict[str, list[Transaction]] = defaultdict(list)
    for t in transactions:
        if any(k in t.merchant.upper() for k in NON_SUBSCRIPTION_KEYWORDS):
            continue
        if t.amount_pence < 0 and not t.is_transfer:
            by_merchant[t.merchant].append(t)
    found = []
    for merchant, txs in by_merchant.items():
        if len({_midx(t.ts.date()) for t in txs}) < 3:
            continue
        med = statistics.median(abs(t.amount_pence) for t in txs)
        if any(abs(abs(t.amount_pence) - med) > 0.1 * med for t in txs):
            continue
        days = [t.ts.day for t in txs]
        if max(days) - min(days) > MAX_BILLING_DAY_SPREAD:
            continue
        dates = sorted(t.ts for t in txs)
        gaps = [(b - a).total_seconds() / 86400 for a, b in zip(dates, dates[1:], strict=False)]
        if gaps and 25 <= statistics.median(gaps) <= 35:
            found.append(merchant)
    return sorted(found)


def habit_vector(
    snapshot: Snapshot,
    window_months: int = 6,
    as_of: date | None = None,
    worst_drawdown: float = 0.35,
) -> HabitVector:
    txs = [t for t in snapshot.transactions if not t.is_transfer]
    all_dates = [t.ts.date() for t in snapshot.transactions]
    if as_of is None:
        as_of = max(all_dates) if all_dates else snapshot.as_of.date()

    end_idx = _midx(as_of)
    if as_of != _month_end(end_idx):
        end_idx -= 1
    start_idx = end_idx - window_months + 1
    window = Window(months=window_months, end=_month_end(end_idx))

    in_window = [t for t in txs if start_idx <= _midx(t.ts.date()) <= end_idx]
    income = sum(t.amount_pence for t in in_window if t.amount_pence > 0)
    monthly = [0] * window_months
    disc = 0
    for t in in_window:
        if t.amount_pence < 0:
            monthly[_midx(t.ts.date()) - start_idx] += -t.amount_pence
            if t.category in DISCRETIONARY_CATEGORIES:
                disc += -t.amount_pence
    spend = sum(monthly)
    mean_spend = spend / window_months

    raw: dict[str, tuple[float | None, str | None]] = {}
    first_idx = min((_midx(d) for d in all_dates), default=None)
    if first_idx is None or first_idx > start_idx:
        for n in _SPEND_BASED:
            raw[n] = (None, _INSUFFICIENT)
    else:
        no_spend = "no spend in window"
        raw["savings_rate"] = (
            ((income - spend) / income, None) if income > 0 else (None, "no income in window")
        )
        if spend > 0:
            raw["runway_months"] = (snapshot.liquid_cash_pence / mean_spend, None)
            cv = statistics.pstdev(monthly) / mean_spend
            raw["spend_stability"] = (min(1.0, max(0.0, 1 - cv)), None)
            raw["discretionary_share"] = (disc / spend, None)
            raw["shock_resilience"] = (
                (snapshot.liquid_cash_pence + snapshot.isa_value_pence * (1 - worst_drawdown))
                / mean_spend,
                None,
            )
        else:
            for n in (
                "runway_months",
                "spend_stability",
                "discretionary_share",
                "shock_resilience",
            ):
                raw[n] = (None, no_spend)
        raw["subscription_creep"] = _creep(txs, end_idx)

    total = sum(h.value_pence for h in snapshot.holdings)
    if total > 0:
        raw["isa_diversification"] = (
            sum((h.value_pence / total) ** 2 for h in snapshot.holdings),
            None,
        )
    else:
        raw["isa_diversification"] = (None, "no ISA holdings")

    factors: dict[str, FactorValue] = {}
    for n in FACTOR_NAMES:
        value, reason = raw[n]
        # Rounded: full-precision ratios would make reverse-engineering amounts easier.
        value = None if value is None else round(value, 3)
        factors[n] = FactorValue(raw=value, score=score_factor(n, value), reason=reason)
    return HabitVector(window=window, factors=factors)


def _creep(txs: list[Transaction], end_idx: int) -> tuple[float | None, str | None]:
    subs = set(detect_subscriptions([t for t in txs if _midx(t.ts.date()) <= end_idx]))
    per_month: dict[int, int] = defaultdict(int)
    for t in txs:
        if t.merchant in subs and t.amount_pence < 0:
            per_month[_midx(t.ts.date())] += -t.amount_pence
    last = sum(per_month[i] for i in range(end_idx - 2, end_idx + 1)) / 3
    prior = sum(per_month[i] for i in range(end_idx - 5, end_idx - 2)) / 3
    if prior == 0:
        return (1.0 if last > 0 else 0.0), None
    return (last - prior) / prior, None
