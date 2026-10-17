"""Habit factors: ratios, months and 0-100 scores. No money amounts leave this module.

Window: the last `window_months` complete calendar months ending at or before `today`. If `today` is the
last day of its month, that month is included; otherwise the current (incomplete) month is excluded.

Reuses the money helpers: `monthly_totals` / `by_category` for spending (transfers, savings and income are not
spending), `categorise` for income and treat spending, `detect_recurring` for subscriptions. Scores use fixed
piecewise-linear bands, so they are deterministic and need no population data. Pure: callers pass `today`.
"""

from __future__ import annotations

import calendar
import statistics
from collections import defaultdict
from datetime import date

from lifeline_contracts.accounts import Holding
from lifeline_contracts.finance import Account, FinanceSnapshot, Transaction
from lifeline_contracts.habits import FactorId, HabitFactor, HabitFactors, HabitWindow
from lifeline_engine.money import dates
from lifeline_engine.money.categorise import categorise, merchant_key
from lifeline_engine.money.profile import is_cash_savings
from lifeline_engine.money.recurring import detect_recurring
from lifeline_engine.money.spending import by_category, monthly_totals

DISCRETIONARY = frozenset(
    {"eating_out", "shopping", "entertainment", "travel", "personal_care", "gifts", "subscriptions"}
)
HOUSING_WORDS = ("rent", "landlord", "mortgage", "council tax", "letting")
MAX_BILLING_DAY_SPREAD = 6  # subscriptions bill on a fixed day; allow drift for short months and weekends
DEFAULT_WORST_DRAWDOWN = 0.35

NO_HISTORY = "Not enough history yet"
NO_INCOME = "No income in this period"
NO_SPEND = "No spending in this period"
NO_INVESTMENTS = "No investments found"

LABELS: dict[FactorId, tuple[str, str]] = {
    "savings_rate": ("Money you keep", "The share of what you earn that you do not spend."),
    "runway_months": ("Cover if pay stopped", "Months you could cover if your pay stopped."),
    "spend_stability": ("Steady spending", "How similar your spending is from month to month."),
    "discretionary_share": ("Treat spending", "The share of your spending that is on things you could do without."),
    "subscription_creep": ("Subscription growth", "How much your regular subscriptions have grown lately."),
    "isa_concentration": ("Spread of your investments", "How much of your investments sits in just a few holdings."),
    "shock_resilience": ("Cushion for a bad patch", "Months you could cover if markets fell and your pay stopped."),
}
FACTOR_IDS: tuple[FactorId, ...] = tuple(LABELS)
_SPEND_BASED: tuple[FactorId, ...] = tuple(f for f in FACTOR_IDS if f != "isa_concentration")
_NEEDS_SPEND: tuple[FactorId, ...] = ("runway_months", "spend_stability", "discretionary_share", "shock_resilience")

_COVER: list[tuple[float, int]] = [(0, 0), (1, 20), (3, 50), (6, 80), (12, 100)]
BANDS: dict[FactorId, list[tuple[float, int]]] = {
    "savings_rate": [(-0.1, 0), (0.0, 20), (0.1, 50), (0.2, 75), (0.35, 100)],
    "runway_months": _COVER,
    "spend_stability": [(0.0, 0), (1.0, 100)],
    # lower is better
    "discretionary_share": [(0.1, 100), (0.25, 70), (0.4, 40), (0.6, 0)],
    "subscription_creep": [(0.0, 100), (0.1, 70), (0.25, 40), (0.5, 0)],
    "isa_concentration": [(0.1, 100), (0.2, 80), (0.35, 50), (0.6, 20), (1.0, 0)],
    "shock_resilience": _COVER,
}


def _interp(knots: list[tuple[float, int]], x: float) -> float:
    if x <= knots[0][0]:
        return float(knots[0][1])
    if x >= knots[-1][0]:
        return float(knots[-1][1])
    for (x0, y0), (x1, y1) in zip(knots, knots[1:], strict=False):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return float(knots[-1][1])  # pragma: no cover


def score_factor(factor: FactorId, raw: float | None) -> int | None:
    """Map a raw value to 0-100. None passes through."""
    return None if raw is None else round(_interp(BANDS[factor], raw))


def overall_score(scores: list[int | None]) -> int | None:
    """Rounded mean of the non-null scores; None if there are none."""
    got = [s for s in scores if s is not None]
    return round(sum(got) / len(got)) if got else None


# ---------- inputs ----------


def window_months_list(today: date, window_months: int) -> list[str]:
    """'YYYY-MM' for each month of the window, oldest first."""
    month_end = today.day == calendar.monthrange(today.year, today.month)[1]
    last = dates.month_of(today) if month_end else dates.prev_month(dates.month_of(today))
    return [dates.prev_month(last, k) for k in range(window_months - 1, -1, -1)]


def hhi(holdings: list[Holding]) -> float | None:
    """Sum of squared shares of each holding's value. None when nothing is held."""
    total = sum(h.value for h in holdings)
    if total <= 0:
        return None
    return sum((h.value / total) ** 2 for h in holdings)


def invested_value(snapshot: FinanceSnapshot) -> float:
    """Investments: holdings when there are any, else stocks and shares ISA balances."""
    if snapshot.holdings:
        return sum(h.value for h in snapshot.holdings)
    return max(0.0, sum(a.balance for a in snapshot.accounts if a.kind == "isa" and not is_cash_savings(a)))


def cash_value(snapshot: FinanceSnapshot) -> float:
    """Money you could use now: current accounts, savings and cash ISAs."""

    def counts(a: Account) -> bool:
        return a.kind == "current" or is_cash_savings(a)

    return max(0.0, sum(a.balance for a in snapshot.accounts if counts(a)))


def _is_housing(t: Transaction) -> bool:
    text = f"{t.description} {t.merchant or ''}".lower()
    return any(w in text for w in HOUSING_WORDS)


def subscription_keys(txs: list[Transaction], end: date) -> set[str]:
    """Merchant keys of fixed-day subscriptions: category subscriptions, not housing, monthly or slower,
    billed within MAX_BILLING_DAY_SPREAD days of the month."""
    keys: set[str] = set()
    for r in detect_recurring([t for t in txs if not _is_housing(t)], end):
        if r.category != "subscriptions" or r.cadence == "weekly":
            continue
        days = [dates.parse(c.date).day for c in r.charges]
        if max(days) - min(days) <= MAX_BILLING_DAY_SPREAD:
            keys.add(r.key)
    return keys


def _creep(txs: list[Transaction], months: list[str], end: date) -> float:
    in_window = [t for t in txs if t.date[:7] <= months[-1]]
    keys = subscription_keys(in_window, end)
    per_month: dict[str, float] = defaultdict(float)
    for t in in_window:
        if t.amount < 0 and merchant_key(t) in keys:
            per_month[t.date[:7]] += -t.amount
    last = sum(per_month[m] for m in months[-3:]) / 3
    prior = sum(per_month[m] for m in months[-6:-3]) / 3
    if prior == 0:
        return 1.0 if last > 0 else 0.0
    return (last - prior) / prior


# ---------- main ----------


def habit_factors(
    snapshot: FinanceSnapshot,
    today: date,
    window_months: int = 6,
    worst_drawdown: float = DEFAULT_WORST_DRAWDOWN,
) -> HabitFactors:
    months = window_months_list(today, window_months)
    txs = snapshot.transactions
    first_month = min((t.date[:7] for t in txs), default=None)
    end = dates.month_bounds(months[-1])[1]
    raw: dict[FactorId, tuple[float | None, str | None]] = {}

    if first_month is None or first_month > months[0]:
        for f in _SPEND_BASED:
            raw[f] = (None, NO_HISTORY)
    else:
        income = sum(t.amount for t in txs if t.date[:7] in months and t.amount > 0 and categorise(t) == "income")
        totals = monthly_totals(txs, months)
        monthly = [totals[m] for m in months]
        spend = sum(monthly)
        mean = spend / window_months
        raw["savings_rate"] = ((income - spend) / income, None) if income > 0 else (None, NO_INCOME)
        if spend > 0:
            disc = sum(
                v for m in months for c, (v, _) in by_category(txs, m).items() if c in DISCRETIONARY
            )
            cv = statistics.pstdev(monthly) / mean
            cash = cash_value(snapshot)
            raw["runway_months"] = (cash / mean, None)
            raw["spend_stability"] = (min(1.0, max(0.0, 1 - cv)), None)
            raw["discretionary_share"] = (disc / spend, None)
            raw["shock_resilience"] = ((cash + invested_value(snapshot) * (1 - worst_drawdown)) / mean, None)
        else:
            for f in _NEEDS_SPEND:
                raw[f] = (None, NO_SPEND)
        raw["subscription_creep"] = (_creep(txs, months, end), None)

    h = hhi(snapshot.holdings)
    raw["isa_concentration"] = (h, None) if h is not None else (None, NO_INVESTMENTS)

    factors: list[HabitFactor] = []
    for f in FACTOR_IDS:
        value, reason = raw[f]
        value = None if value is None else round(value, 3)  # rounded: full precision would ease reverse-engineering
        label, explainer = LABELS[f]
        factors.append(
            HabitFactor(id=f, label=label, explainer=explainer, raw=value, score=score_factor(f, value), reason=reason)
        )
    return HabitFactors(
        window=HabitWindow(months=window_months, end=dates.iso(end)),
        factors=factors,
        overall=overall_score([f.score for f in factors]),
    )


def monthly_saving(txs: list[Transaction], today: date, months: int = 6) -> float | None:
    """Mean per month of money moved to savings or an ISA over the last `months` complete months.

    None when nothing was moved in the window. Used to suggest a monthly contribution for the ISA replay.
    """
    window = set(window_months_list(today, months))
    moved = sum(-t.amount for t in txs if t.amount < 0 and t.date[:7] in window and categorise(t) == "savings")
    return round(moved / months, 2) if moved > 0 else None
