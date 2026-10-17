"""Cash-flow projection (ADR 0033). Pure: no I/O, no clock. "Today" is the snapshot's as_of day.

Model, month by month (month 1 = the month after today):
- start balance = cash: current accounts + cash savings (savings accounts, cash ISAs; not stocks and shares ISAs).
- income = monthly net salary from detected salary credits (0 when none is found).
- outgoings = average monthly spending over the last 3 complete months (money.profile.monthly_spend). This
  includes rent or mortgage, bills and subscriptions. Transfers, savings and card repayments are not spending.
- balance(m) = balance(m - 1) + income(m) - outgoings(m).

What-ifs:
- job_loss(months): no salary in months 1..months.
- rate_rise(points): the mortgage payment is recomputed with finance.monthly_payment at (current rate + points)
  on the balance and years left. It applies from the first month after the fixed deal ends (from month 1 when
  the mortgage is not fixed). A deal that ends on the 1st of a month: the new rate applies from that month.
  No mortgage: no effect.
- one_off_cost(gbp, month): an extra outgoing in that month.
- cancel(subscription_ids): the monthly cost of those subscriptions (ids from detect_subscriptions) stops
  from month 1. Unknown ids are ignored and reported.

Outputs: months of cover (cash / outgoings, no income; None when there is no spending), the lowest balance and its
month, the first month the
balance goes below 0 (None when it never does), and the month-by-month path.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from lifeline_contracts.finance import FinanceSnapshot
from lifeline_engine.finance import monthly_payment
from lifeline_engine.money import dates
from lifeline_engine.money.profile import MIN_KNOWN_COSTS, liquid, monthly_spend
from lifeline_engine.money.recurring import detect_salary, detect_subscriptions

MAX_MONTHS = 60


class _W(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class JobLoss(_W):
    kind: Literal["job_loss"] = "job_loss"
    months: int = Field(ge=1, le=MAX_MONTHS)


class RateRise(_W):
    kind: Literal["rate_rise"] = "rate_rise"
    points: float = Field(gt=0, le=10, description="Percentage points added to the mortgage rate")


class OneOffCost(_W):
    kind: Literal["one_off_cost"] = "one_off_cost"
    gbp: float = Field(gt=0, le=1_000_000)
    month: int = Field(ge=1, le=MAX_MONTHS)


class Cancel(_W):
    kind: Literal["cancel"] = "cancel"
    subscription_ids: list[Annotated[str, Field(min_length=1, max_length=64)]] = Field(min_length=1, max_length=20)


WhatIf = Annotated[JobLoss | RateRise | OneOffCost | Cancel, Field(discriminator="kind")]


@dataclass(frozen=True)
class MonthRow:
    month: int  # 1 = the month after today
    date: str  # first day of that month
    income: float
    outgoings: float
    balance: float  # end of month


@dataclass(frozen=True)
class Projection:
    start_balance: float
    monthly_income: float
    monthly_outgoings: float
    months_of_cover: float | None  # None when there is no spending to cover
    lowest_balance: float
    lowest_month: int
    run_out_month: int | None
    end_balance: float
    rows: tuple[MonthRow, ...]
    mortgage_extra_per_month: float
    cancelled_per_month: float
    unknown_subscription_ids: tuple[str, ...]


def months_of_cover(cash: float, monthly_outgoings: float) -> float | None:
    """Cash / monthly outgoings, 1 decimal. None when costs are not known: outgoings under MIN_KNOWN_COSTS
    (ADR 0053 bug 5; shared by every tool)."""
    if monthly_outgoings < MIN_KNOWN_COSTS:
        return None
    return round(max(0.0, cash) / monthly_outgoings, 1)


def _mortgage_extra(snapshot: FinanceSnapshot, points: float) -> tuple[float, int]:
    """(extra payment per month, first month it applies) for a rate rise of `points`."""
    m = snapshot.mortgage
    if m is None or m.balance <= 0 or m.years_left <= 0:
        return 0.0, 1
    today = dates.parse(snapshot.as_of)
    now = monthly_payment(m.balance, m.rate_pct, m.years_left)
    risen = monthly_payment(m.balance, m.rate_pct + points, m.years_left)
    first = 1
    if m.rate_type == "fixed" and m.fixed_until is not None:
        end = dates.parse(m.fixed_until)
        months = (end.year - today.year) * 12 + (end.month - today.month)
        first = max(1, months if end.day == 1 else months + 1)
    return risen - now, first


def cash_flow_projection(
    snapshot: FinanceSnapshot, months: int, what_if: Sequence[JobLoss | RateRise | OneOffCost | Cancel] = ()
) -> Projection:
    if not 1 <= months <= MAX_MONTHS:
        raise ValueError(f"months must be 1..{MAX_MONTHS}")
    today = dates.parse(snapshot.as_of)
    start = round(liquid(snapshot), 2)
    income = 0.0
    inc = detect_salary(snapshot.transactions)
    if inc is not None:
        income = inc.monthly_net
    out = monthly_spend(snapshot, today)

    no_pay_until = 0
    extra = 0.0
    extra_from = 1
    one_offs: dict[int, float] = {}
    cancelled = 0.0
    unknown: list[str] = []
    subs = {s.id: s for s in detect_subscriptions(snapshot.transactions, today)}
    for w in what_if:
        if isinstance(w, JobLoss):
            no_pay_until = max(no_pay_until, w.months)
        elif isinstance(w, RateRise):
            e, f = _mortgage_extra(snapshot, w.points)
            extra += e
            extra_from = f
        elif isinstance(w, OneOffCost):
            one_offs[w.month] = one_offs.get(w.month, 0.0) + w.gbp
        else:
            for sid in dict.fromkeys(w.subscription_ids):
                if sid in subs:
                    cancelled += subs[sid].monthly_cost
                else:
                    unknown.append(sid)

    rows: list[MonthRow] = []
    bal = start
    first_day = dates.date(today.year, today.month, 1)
    for k in range(1, months + 1):
        inc_k = 0.0 if k <= no_pay_until else income
        out_k = max(0.0, out - cancelled) + (extra if k >= extra_from else 0.0) + one_offs.get(k, 0.0)
        bal = bal + inc_k - out_k
        rows.append(
            MonthRow(
                month=k,
                date=dates.iso(dates.add_months(first_day, k)),
                income=round(inc_k, 2),
                outgoings=round(out_k, 2),
                balance=round(bal, 2),
            )
        )
    low = min(rows, key=lambda r: (r.balance, r.month))
    run_out = next((r.month for r in rows if r.balance < 0), None)
    cover = months_of_cover(start, out)
    return Projection(
        start_balance=start,
        monthly_income=round(income, 2),
        monthly_outgoings=round(out, 2),
        months_of_cover=cover,
        lowest_balance=low.balance,
        lowest_month=low.month,
        run_out_month=run_out,
        end_balance=rows[-1].balance,
        rows=tuple(rows),
        mortgage_extra_per_month=round(extra, 2),
        cancelled_per_month=round(cancelled, 2),
        unknown_subscription_ids=tuple(unknown),
    )
