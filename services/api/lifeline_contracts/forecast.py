"""The forecast Next Move (PENNY_V3_BUILD.md B, ADR 0072). BOSS-owned.

"Will my money last until my next money arrives, and how much can I spend each week?"
Deterministic engine maths. Every block carries its source. The detailed breakdown adds up exactly; screens round.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from lifeline_contracts.domain import IsoDate, IsoMonth
from lifeline_contracts.finance import Category, FinanceMeta, Transaction

BufferPct = Literal[0, 5, 10, 15, 20]
ForecastState = Literal["on_track", "running_short", "no_next_money"]


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ForecastSource(_M):
    label: str = Field(max_length=120, description="e.g. 'Your statement', 'SAAS payment schedule', 'ONS CPI'")
    url: str | None = Field(default=None, max_length=500)


class ForecastAccount(_M):
    name: str = Field(max_length=80)
    kind: Literal["current", "savings", "credit", "overdraft", "other"]
    balance: float
    counted: bool = Field(description="True when it is in money now (current accounts; overdraft as negative)")


class ForecastBill(_M):
    name: str = Field(max_length=80)
    kind: Literal["bill", "subscription", "rent", "loan", "other"]
    amount: float = Field(ge=0)
    due_date: IsoDate


class NextMoney(_M):
    label: str = Field(max_length=80, description="e.g. 'Student Finance England loan', 'Pay from the bar job'")
    amount: float = Field(ge=0)
    date: IsoDate
    source: ForecastSource


class ForecastIncome(_M):
    """A smaller income expected before the main next money (e.g. weekly pay); added to money available."""

    label: str = Field(max_length=80)
    amount: float = Field(ge=0)
    date: IsoDate
    source: ForecastSource


class SpendWeek(_M):
    start: IsoDate
    end: IsoDate
    amount: float = Field(ge=0, description="Non-rent, non-bill spending in this week")


class TimelinePoint(_M):
    date: IsoDate
    kind: Literal["today", "bill", "next_money", "run_out"]
    label: str = Field(max_length=80)
    amount: float | None = None


class ForecastStep(_M):
    """One of the 4 steps on 'The maths': money now, bills before next money, buffer, next money and result."""

    id: Literal["money_now", "bills", "buffer", "result"]
    title: str = Field(max_length=80)
    amount: float
    text: str = Field(max_length=240, description="One plain sentence with the exact figures")
    sources: list[ForecastSource] = Field(default_factory=list, max_length=4)


class Suggestion(_M):
    kind: Literal["save_spare", "cut_category"]
    text: str = Field(max_length=200)
    amount: float = Field(ge=0, description="£ to put aside, or the category's weekly amount")
    category: Category | None = None
    rate_pct: float | None = Field(default=None, description="Bank of England easy-access rate (save_spare)")
    source: ForecastSource | None = None


class StressTest(_M):
    year: int = Field(description="2022")
    inflation_pct: float = Field(description="ONS CPI annual rate used")
    state: ForecastState
    per_week: float
    usual_weekly: float
    run_out_date: IsoDate | None = None
    text: str = Field(max_length=240)
    source: ForecastSource


class Forecast(_M):
    meta: FinanceMeta
    question: Literal["Will my money last until my next money arrives?"] = (
        "Will my money last until my next money arrives?"
    )
    state: ForecastState
    today: IsoDate
    headline: str = Field(
        max_length=120, description="'You'll make it to 2 November' or 'At this pace, you run out on 28 October'"
    )
    budget_line: str = Field(max_length=120, description="'You can spend £82 a week (about £12 a day)'")
    habit_line: str | None = Field(default=None, max_length=160)
    next_money: NextMoney | None = None
    money_now: float = Field(description="Current accounts only; overdraft negative; savings not counted")
    accounts: list[ForecastAccount]
    expected_income: list[ForecastIncome] = Field(
        default_factory=list, description="Smaller incomes due before next money; added to money available"
    )
    expected_income_total: float = Field(default=0, ge=0)
    bills: list[ForecastBill] = Field(description="Due from tomorrow to the day before next money")
    bills_total: float = Field(ge=0)
    buffer_pct: BufferPct
    buffer_amount: float = Field(ge=0)
    days: int = Field(ge=0, description="Tomorrow to the day before next money")
    per_day: float
    per_week: float
    budget_period: Literal["week", "until_next_money"] = Field(
        default="week",
        description="'until_next_money' when fewer than 14 days are left: screens show the total "
        "(money to spend until the date) and per day, not a weekly figure (ADR 0072)",
    )
    to_spend: float = Field(default=0, description="Money to spend until next money: per_day x days")
    usual_weekly: float = Field(ge=0, description="Average weekly non-rent, non-bill spending, last 4 weeks")
    usual_daily: float = Field(ge=0)
    usual_weeks: list[SpendWeek] = Field(max_length=4)
    cpi_adjusted: bool = Field(default=False, description="Gap over 6 weeks: usual spending raised by ONS CPI")
    cpi_note: str | None = Field(default=None, max_length=200)
    spare: float | None = Field(default=None, description="On track: (per week - usual) x weeks")
    run_out_date: IsoDate | None = Field(default=None, description="Running short")
    suggestion: Suggestion | None = None
    steps: list[ForecastStep] = Field(min_length=4, max_length=4)
    timeline: list[TimelinePoint]
    sources: list[ForecastSource]
    stress: StressTest | None = Field(default=None, description="Only when requested with stress=2022")


class ForecastSettings(_M):
    buffer_pct: BufferPct = 10


class CategoryWeek(_M):
    start: IsoDate
    end: IsoDate
    amount: float = Field(ge=0)


class CategoryDetail(_M):
    """Category screen: total, usual monthly amount, bars by week, every transaction."""

    meta: FinanceMeta
    category: Category
    label: str
    month: IsoMonth
    total: float = Field(ge=0)
    usual_monthly: float = Field(ge=0, description="Average of the full statement months before this one")
    weeks: list[CategoryWeek]
    transactions: list[Transaction]


class WhatIfChange(_M):
    """One change for a what-if rerun of the forecast (Penny's forecast_what_if tool)."""

    kind: Literal["one_off_cost", "extra_income", "move_payment", "recurring_cost_change"]
    amount: float | None = Field(default=None, description="£; for recurring_cost_change the new monthly amount")
    date: IsoDate | None = Field(default=None, description="Date of the cost or income, or the new payment date")
    label: str | None = Field(default=None, max_length=80, description="What it is, e.g. 'Concert ticket'")
    target: str | None = Field(default=None, max_length=80, description="Payment or bill it changes (move/recurring)")


class WhatIfResult(_M):
    changes: list[WhatIfChange]
    before: Forecast
    after: Forecast
    summary: str = Field(max_length=240, description="One plain sentence: new state, weekly amount, run-out date")
