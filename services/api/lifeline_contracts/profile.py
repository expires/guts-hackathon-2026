"""Your profile (GET /v1/profile/stats): what each connected source gives us, and the stats built from it.

Every number comes from the engine or from the connected data. A section that the data cannot support is
`available=false` with a plain-English `missing_hint`; nothing is invented. Amounts are the user's own and stay in
their own view (ADR 0052).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from lifeline_contracts.accounts import AssetClass, Holding
from lifeline_contracts.domain import IsoDate, IsoMonth
from lifeline_contracts.finance import AmountPart, CategorySpend, HabitScore

SourceId = Literal["monzo", "trading212", "statement", "manual", "sample"]
SectionId = Literal["habits", "spending", "net_worth", "investments"]


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProfileConnection(_M):
    """One way the user can give us data, and what it gave us."""

    id: SourceId
    title: str = Field(max_length=40, description="e.g. 'Monzo'")
    connected: bool
    data_status: Literal["live", "cached", "mock"] | None = Field(
        default=None, description="None when not connected. 'mock' is sample data"
    )
    label: str | None = Field(default=None, description="'Sample data' for the sample connection")
    last_synced: IsoDate | None = Field(default=None, description="Day of the newest data from this source")
    sample_id: str | None = Field(default=None, description="Which sample student is loaded (sample connection only)")
    provides: str | None = Field(
        default=None, max_length=120, description="Plain words, e.g. 'Transactions since 21 Jul 2026 (151)'"
    )


class SpendingSummary(_M):
    month: IsoMonth = Field(description="The month the top categories are for")
    partial: bool = Field(description="True when the month is not over or not fully covered by the data")
    months_used: int = Field(ge=0, description="Full months behind the monthly averages (0 when partial)")
    monthly_in: float | None = Field(default=None, ge=0, description="Average money in per month; None if unknown")
    monthly_out: float = Field(ge=0, description="Average spending per month (month so far when partial)")
    top_categories: list[CategorySpend] = Field(max_length=3)
    subscriptions_monthly: float = Field(ge=0)
    subscriptions_count: int = Field(ge=0)


class NetWorthSummary(_M):
    net_worth: float
    cash: float = Field(description="Current accounts and cash savings")
    investments: float = Field(ge=0, description="Stocks and shares accounts, never counted as cash")
    other: float = Field(description="Everything else (debts, property); 0 when nothing")
    parts: list[AmountPart] = Field(description="The calculation: each account that adds up to net worth")


class MixSlice(_M):
    asset_class: AssetClass
    label: str
    value: float = Field(ge=0)
    share_pct: float = Field(ge=0, le=100)


class InvestmentSummary(_M):
    total_value: float = Field(description="Whole Trading 212 account, including uninvested cash")
    invested_value: float | None = Field(default=None, ge=0, description="Sum of positions; None without positions")
    holdings_count: int = Field(ge=0)
    mix: list[MixSlice] = Field(default_factory=list, description="Share of invested value by asset class")
    top_holdings: list[Holding] = Field(
        default_factory=list, max_length=200, description="Every holding, biggest first"
    )
    note: str | None = Field(default=None, description="Plain words when positions could not be read")


class ProfileSection(_M):
    id: SectionId
    title: str = Field(max_length=40)
    available: bool
    sources: list[SourceId] = Field(default_factory=list, description="Where the data comes from")
    missing_hint: str | None = Field(default=None, description="Why it is unavailable and what to connect")
    habits: HabitScore | None = None
    spending: SpendingSummary | None = None
    net_worth: NetWorthSummary | None = None
    investments: InvestmentSummary | None = None


class ProfileStats(_M):
    connections: list[ProfileConnection] = Field(description="Always monzo, trading212, statement, manual, sample")
    sections: list[ProfileSection] = Field(description="Always habits, spending, net_worth, investments")
