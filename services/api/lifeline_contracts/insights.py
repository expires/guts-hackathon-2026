"""Spending insights models (Money tab, Insights screen). GBP floats, like the rest of the finance contracts.

Window: the last `window_months` complete calendar months. If the user has fewer months of history than
requested, the months available are used (at least 2) and `note` says so.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from lifeline_contracts.domain import IsoDate, IsoMonth
from lifeline_contracts.finance import Category, FinanceMeta


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InsightMonth(_M):
    month: IsoMonth
    income: float = Field(ge=0)
    spend: float = Field(ge=0)
    net: float = Field(description="income minus spend")


class InsightCategory(_M):
    category: Category
    label: str
    emoji: str
    amount: float = Field(ge=0)
    share: float = Field(ge=0, le=1)
    monthly_average: float = Field(ge=0)
    change_pct: float | None = Field(
        default=None, description="vs the previous window of the same length, percent; null with no prior data"
    )


class CategorySeries(_M):
    category: Category
    label: str
    emoji: str
    values: list[float] = Field(description="Spend per month, aligned with category_months")


class InsightMerchant(_M):
    merchant: str
    category: Category
    emoji: str
    amount: float = Field(ge=0)
    count: int = Field(ge=1)


class InsightSubscription(_M):
    merchant: str
    emoji: str
    monthly_cost: float = Field(ge=0)
    annual_cost: float = Field(ge=0)


class InsightSubscriptions(_M):
    monthly_total: float = Field(ge=0)
    annual_total: float = Field(ge=0)
    items: list[InsightSubscription]


class UnusualPayment(_M):
    id: str
    date: IsoDate
    merchant: str
    category: Category
    emoji: str
    amount: float = Field(ge=0)
    typical: float = Field(ge=0, description="Median payment in this category")


class WeekdaySpend(_M):
    weekday: str = Field(description="Monday to Sunday")
    amount: float = Field(ge=0)


class SpendingPatterns(_M):
    weekend_share: float | None = Field(default=None, ge=0, le=1, description="Share of treat spending on Sat and Sun")
    weekday_share: float | None = Field(default=None, ge=0, le=1)
    average_daily_spend: float = Field(ge=0)
    biggest_weekday: str | None = None
    biggest_day: IsoDate | None = None
    biggest_day_amount: float | None = Field(default=None, ge=0)
    by_weekday: list[WeekdaySpend]


class SpendingInsights(_M):
    meta: FinanceMeta
    window_months: int = Field(ge=0, description="Months actually used")
    requested_months: int = Field(ge=1)
    start_month: IsoMonth | None = None
    end_month: IsoMonth | None = None
    note: str | None = Field(default=None, description="Set when fewer months were available than requested")
    total_income: float = Field(ge=0)
    total_spend: float = Field(ge=0)
    monthly: list[InsightMonth]
    categories: list[InsightCategory]
    category_months: list[IsoMonth]
    category_by_month: list[CategorySeries]
    top_merchants: list[InsightMerchant]
    subscriptions: InsightSubscriptions
    unusual: list[UnusualPayment]
    patterns: SpendingPatterns
    insights: list[str] = Field(description="Plain English facts, no advice")
