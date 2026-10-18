"""Explicit preconditions per Next Move kind (ADR 0053 bug 1). Pure: no I/O, no clock, no RNG.

A move kind is offered only when its precondition holds on the user's own data. A precondition never fills a
missing field with a guess: no deal end date, no payday and no tariff type are invented (ADR 0053 bug 3).

| Kind | Precondition on the snapshot |
|---|---|
| fix_mortgage | a mortgage with balance > 0, years left > 0, a fixed rate with a known end date 0 to 365 days away |
| remortgage | a mortgage with balance > 0, years left > 0, on a variable or tracker rate, or a fixed deal |
|  | that has ended |
| move_savings | cash savings of at least MIN_SAVINGS |
| cancel_subscription | at least one detected subscription with a price rise |
| switch_subscription | never: there is no plan or price list data |
| switch_energy | energy details with a monthly cost > 0, and a fixed deal ending in 0 to 60 days, or a tariff |
|  | that is not fixed |
| pay_off_debt | money owed on cards, overdrafts or loans of at least MIN_DEBT |
| build_emergency_fund | known monthly costs (see known_monthly_costs), and cash below EMERGENCY_MONTHS of costs |
| cut_budget | spending in the last full month and in at least one of the 3 months before |
| spread_investments | never: deprecated (ADR 0046) |
| weekly_budget | a known next payment date after today (entered, or one cadence after a regular credit), recent |
|  | spending, and cash < bills due before that date + spending at the current pace (ADR 0057) |
| lifetime_isa | age known to be 18 to 39, no mortgage, no expensive debt, known costs, and savings above |
|  | EMERGENCY_MONTHS of costs |
| keep_cash | cash savings of at least MIN_CASH with a known (measured) rate |
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from lifeline_contracts.finance import FinanceSnapshot
from lifeline_contracts.next_move import MoveKind
from lifeline_engine.money import dates
from lifeline_engine.money.profile import (
    cash_savings_total,
    full_data_months,
    full_months_before,
    known_monthly_costs,
    liquid,
    savings_rate_pct,
    savings_total,
)
from lifeline_engine.money.recurring import detect_subscriptions
from lifeline_engine.student import from_snapshot, lisa_age_ok
from lifeline_engine.student import weekly_budget as weekly_budget_calc

MIN_SAVINGS = 1_000.0
MIN_CASH = 100.0
MIN_DEBT = 100.0
EMERGENCY_MONTHS = 3
DEAL_WINDOW_DAYS = 365
ENERGY_WINDOW_DAYS = 60


def has_mortgage(s: FinanceSnapshot) -> bool:
    m = s.mortgage
    return m is not None and m.balance > 0 and m.years_left > 0


def mortgage_days_left(s: FinanceSnapshot, today: date) -> int | None:
    """Days until the fixed deal ends. None when there is no fixed deal with a known end date."""
    m = s.mortgage
    if m is None or m.rate_type != "fixed" or m.fixed_until is None:
        return None
    return (dates.parse(m.fixed_until) - today).days


def fix_mortgage(s: FinanceSnapshot, today: date) -> bool:
    days = mortgage_days_left(s, today)
    return has_mortgage(s) and days is not None and 0 <= days <= DEAL_WINDOW_DAYS


def remortgage(s: FinanceSnapshot, today: date) -> bool:
    if not has_mortgage(s):
        return False
    assert s.mortgage is not None
    if s.mortgage.rate_type in ("variable", "tracker"):
        return True
    days = mortgage_days_left(s, today)
    return days is not None and days < 0


def move_savings(s: FinanceSnapshot, today: date) -> bool:
    return cash_savings_total(s) >= MIN_SAVINGS


def cancel_subscription(s: FinanceSnapshot, today: date) -> bool:
    return any(x.price_rise is not None for x in detect_subscriptions(s.transactions, today))


def never(s: FinanceSnapshot, today: date) -> bool:
    return False


def energy_is_variable(s: FinanceSnapshot) -> bool:
    """A tariff with no end date whose name does not say 'fix' is a variable tariff."""
    e = s.energy
    return e is not None and e.fixed_until is None and "fix" not in e.tariff.lower()


def energy_days_left(s: FinanceSnapshot, today: date) -> int | None:
    e = s.energy
    if e is None or e.fixed_until is None:
        return None
    return (dates.parse(e.fixed_until) - today).days


def switch_energy(s: FinanceSnapshot, today: date) -> bool:
    e = s.energy
    if e is None or e.monthly_cost <= 0:
        return False
    days = energy_days_left(s, today)
    return energy_is_variable(s) or (days is not None and 0 <= days <= ENERGY_WINDOW_DAYS)


def expensive_debt(s: FinanceSnapshot, today: date) -> float:
    """GBP owed that costs interest: cards, loans, an overdraft beyond its known free limit, BNPL with a rate."""
    return round(sum(d.expensive for d in from_snapshot(s, today).debts), 2)


def pay_off_debt(s: FinanceSnapshot, today: date) -> bool:
    return expensive_debt(s, today) >= MIN_DEBT


def build_emergency_fund(s: FinanceSnapshot, today: date) -> bool:
    costs = known_monthly_costs(s, today)
    return costs is not None and max(0.0, liquid(s)) < EMERGENCY_MONTHS * costs


def cut_budget(s: FinanceSnapshot, today: date) -> bool:
    months = full_data_months(s, full_months_before(today, 4))
    seen = {t.date[:7] for t in s.transactions if t.amount < 0}
    return (
        bool(months)
        and months[-1] == full_months_before(today, 1)[0]
        and months[-1] in seen
        and any(m in seen for m in months[:-1])
    )


def weekly_budget(s: FinanceSnapshot, today: date) -> bool:
    wb = weekly_budget_calc(s, from_snapshot(s, today), today, max(0.0, liquid(s)))
    # F-V2-2: offered whenever the money runs short before the next payment, also when bills alone exceed the cash
    # (the move then says how much is missing).
    return wb is not None and wb.short_by > 0


def lisa_room(s: FinanceSnapshot, today: date) -> float:
    """Savings above EMERGENCY_MONTHS of known costs, capped at the yearly limit. 0 when costs are unknown."""
    costs = known_monthly_costs(s, today)
    if costs is None:
        return 0.0
    return max(0.0, min(4_000.0, savings_total(s) - EMERGENCY_MONTHS * costs))


def lifetime_isa(s: FinanceSnapshot, today: date) -> bool:
    has_home = s.mortgage is not None or any(a.kind == "mortgage" for a in s.accounts)
    return (
        lisa_age_ok(from_snapshot(s, today))
        and not has_home
        and expensive_debt(s, today) == 0
        and lisa_room(s, today) > 0
    )


def keep_cash(s: FinanceSnapshot, today: date) -> bool:
    return cash_savings_total(s) >= MIN_CASH and savings_rate_pct(s, today) is not None


PRECONDITIONS: dict[MoveKind, Callable[[FinanceSnapshot, date], bool]] = {
    "fix_mortgage": fix_mortgage,
    "remortgage": remortgage,
    "move_savings": move_savings,
    "cancel_subscription": cancel_subscription,
    "switch_subscription": never,
    "switch_energy": switch_energy,
    "pay_off_debt": pay_off_debt,
    "build_emergency_fund": build_emergency_fund,
    "cut_budget": cut_budget,
    "spread_investments": never,
    "weekly_budget": weekly_budget,
    "lifetime_isa": lifetime_isa,
    "keep_cash": keep_cash,
}


def met(kind: MoveKind, s: FinanceSnapshot, today: date) -> bool:
    """True when the data supports offering `kind`. Unknown kinds are never offered."""
    check = PRECONDITIONS.get(kind)
    return check is not None and check(s, today)
