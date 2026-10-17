"""Money tab (personal finance) models. BOSS-owned. See ADR 0016.

Flow: transactions (labelled fixtures in Tier 1, TrueLayer sandbox in Tier 2, W1)
-> pure insight code in lifeline_engine.money (W2: categorise, detect subscriptions and bills,
budgets, goals, overview series, profile) -> /v1/finance/* (W4) -> Money tab (iOS).
No LLM in categorisation or detection.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from lifeline_contracts.domain import CharacterSpec, DecisionProfile
from lifeline_contracts.observation import Status

AccountKind = Literal["current", "savings", "credit", "isa", "pension", "mortgage", "loan"]
Cadence = Literal["weekly", "monthly", "quarterly", "yearly"]
Category = Literal[
    "groceries",
    "eating_out",
    "transport",
    "shopping",
    "entertainment",
    "bills",
    "housing",
    "subscriptions",
    "health",
    "travel",
    "personal_care",
    "education",
    "gifts",
    "transfers",
    "income",
    "savings",
    "cash",
    "fees",
    "other",
]


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------- canonical input (data layer) ----------


class Account(_M):
    id: str
    name: str
    kind: AccountKind
    provider: str
    balance: float = Field(description="gbp; negative for money owed")
    currency: Literal["GBP"] = "GBP"


class Transaction(_M):
    """One bank transaction. amount < 0 is money out."""

    id: str
    account_id: str
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    amount: float
    currency: Literal["GBP"] = "GBP"
    description: str = Field(max_length=200)
    merchant: str | None = Field(default=None, max_length=80)
    provider_category: str | None = Field(default=None, max_length=60, description="Bank's own label, if any")


class MortgageDetails(_M):
    balance: float = Field(ge=0)
    rate_pct: float = Field(ge=0, le=30)
    rate_type: Literal["fixed", "tracker", "variable"]
    fixed_until: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    years_left: int = Field(ge=0, le=40)
    property_value: float = Field(ge=0)
    monthly_payment: float = Field(ge=0)
    lender: str | None = None


class EnergyDetails(_M):
    supplier: str
    tariff: str
    monthly_cost: float = Field(ge=0)
    fixed_until: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class FinanceSnapshot(_M):
    """Everything the insight code needs. Produced by lifeline_data, consumed by lifeline_engine.money."""

    status: Status
    source: str = Field(description="'fixtures' or 'truelayer'")
    persona: str | None = Field(default=None, description="Fixture persona id when status is mock")
    as_of: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    accounts: list[Account]
    transactions: list[Transaction]
    mortgage: MortgageDetails | None = None
    energy: EnergyDetails | None = None


# ---------- API responses ----------


class FinanceMeta(_M):
    data_status: Status
    source: str
    as_of: str
    label: str | None = Field(default=None, description="'Sample data' when data_status is mock")


class Point(_M):
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    value: float


class FinanceOverview(_M):
    meta: FinanceMeta
    balance: float = Field(description="Sum of current and savings accounts")
    net_worth: float
    accounts: list[Account]
    balance_history: list[Point]
    net_worth_history: list[Point]


class CategorySpend(_M):
    category: Category
    label: str
    emoji: str
    amount: float = Field(ge=0)
    share: float = Field(ge=0, le=1)
    transactions: int = Field(ge=0)
    change_pct: float | None = Field(default=None, description="vs previous month, percent")


class SpendingResponse(_M):
    meta: FinanceMeta
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    total: float = Field(ge=0)
    categories: list[CategorySpend]


class PriceRise(_M):
    from_amount: float
    to_amount: float
    since: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class Subscription(_M):
    id: str
    merchant: str
    emoji: str
    category: Category
    amount: float = Field(ge=0, description="Latest charge")
    cadence: Cadence
    monthly_cost: float = Field(ge=0)
    next_payment: str | None = None
    price_rise: PriceRise | None = None


class SubscriptionsResponse(_M):
    meta: FinanceMeta
    monthly_total: float = Field(ge=0)
    count: int = Field(ge=0)
    items: list[Subscription]


class Bill(_M):
    id: str
    name: str
    emoji: str
    kind: Literal["bill", "subscription", "rent", "mortgage", "loan", "card"]
    amount: float = Field(ge=0)
    due_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    status: Literal["upcoming", "due_soon", "paid", "overdue"]


class BillsResponse(_M):
    meta: FinanceMeta
    total_next_30_days: float = Field(ge=0)
    items: list[Bill]


class Budget(_M):
    category: Category
    label: str
    emoji: str
    limit: float = Field(ge=0)
    spent: float = Field(ge=0)
    progress: float = Field(ge=0, description="spent / limit; can exceed 1")
    status: Literal["ok", "near", "over"]


class BudgetsResponse(_M):
    meta: FinanceMeta
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    items: list[Budget]


class BudgetLimit(_M):
    category: Category
    limit: float = Field(ge=0, le=1_000_000)


class UpdateBudgetsRequest(_M):
    items: list[BudgetLimit] = Field(min_length=1, max_length=30)


class SavingsGoal(_M):
    id: str
    name: str
    emoji: str
    target: float = Field(gt=0)
    saved: float = Field(ge=0)
    progress: float = Field(ge=0)
    target_date: str | None = None
    monthly_needed: float | None = Field(default=None, ge=0)


class GoalsResponse(_M):
    meta: FinanceMeta
    items: list[SavingsGoal]


class CreateGoalRequest(_M):
    name: str = Field(min_length=1, max_length=40)
    emoji: str = Field(default="🎯", max_length=8)
    target: float = Field(gt=0, le=10_000_000)
    saved: float = Field(default=0, ge=0, le=10_000_000)
    target_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class PersonalFact(_M):
    """A real-number sentence that a lesson can show. Every number comes from `facts`."""

    id: str
    concept_id: str
    text: str
    facts: dict[str, float]


class FinanceProfile(_M):
    """Bridge from the Money tab to 'Play yourself' and to the Real-life Decision."""

    meta: FinanceMeta
    profile: DecisionProfile
    character: CharacterSpec
    personal_facts: list[PersonalFact]


class LifeListItem(_M):
    id: str
    name: str
    emoji: str
    mode: str
    year: int
    age: int
    alive: bool
    index: float
    net_worth: float
    ribbons: int = Field(ge=0)


class LivesResponse(_M):
    lives: list[LifeListItem]


# ---------- spend prediction and "Guess my spend" (ADR 0017) ----------


class Reason(_M):
    """One feature contribution. effect is in GBP vs the baseline day; the effects of all features sum to
    predicted - baseline."""

    feature: str = Field(description="e.g. payday, weekend, rain, bank_holiday, recent_trend")
    label: str = Field(description="Plain English, e.g. 'It is Friday'")
    effect: float


class Weather(_M):
    summary: str
    temp_max_c: float
    rain_mm: float
    status: Status


class ModelInfo(_M):
    name: str = Field(description="e.g. 'ridge regression on log spend'")
    trained_on_days: int = Field(ge=0)
    mae: float = Field(ge=0, description="Backtest mean absolute error, GBP")
    baseline_mae: float = Field(ge=0, description="Day-of-week average baseline, GBP")
    interval_coverage: float = Field(ge=0, le=1, description="Share of backtest days inside the range")


class GuessState(_M):
    amount: float = Field(ge=0)
    made_at: str
    points: int | None = Field(default=None, ge=0, le=100, description="Set once the day's actual is known")
    beat_model: bool | None = None


class SpendPrediction(_M):
    meta: FinanceMeta
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    predicted: float = Field(ge=0)
    low: float = Field(ge=0, description="10th percentile")
    high: float = Field(ge=0, description="90th percentile")
    baseline: float = Field(ge=0, description="Typical day; reasons explain the gap from this")
    reasons: list[Reason] = Field(max_length=3, description="Top 3 by absolute effect")
    weather: Weather | None = None
    is_bank_holiday: bool
    days_to_payday: int | None = None
    guess: GuessState | None = Field(
        default=None,
        description="Present once the user has guessed. The client hides predicted, low, high and reasons until then.",
    )
    actual: float | None = Field(default=None, ge=0, description="Set when the day is over")
    model: ModelInfo


class GuessRequest(_M):
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    amount: float = Field(ge=0, le=100_000)


class GuessDay(_M):
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    guess: float = Field(ge=0)
    predicted: float = Field(ge=0)
    actual: float | None = None
    points: int | None = Field(default=None, ge=0, le=100)
    beat_model: bool | None = None


class GuessesResponse(_M):
    meta: FinanceMeta
    points_total: int = Field(ge=0)
    streak: int = Field(ge=0, description="Consecutive scored days with points >= 70")
    best_streak: int = Field(ge=0)
    items: list[GuessDay]


class BacktestDay(_M):
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    predicted: float
    low: float
    high: float
    actual: float
    baseline: float


class PredictionEvaluation(_M):
    meta: FinanceMeta
    method: str
    n_days: int = Field(ge=0)
    mae: float = Field(ge=0)
    baseline_mae: float = Field(ge=0)
    baseline: str
    interval_coverage: float = Field(ge=0, le=1)
    days: list[BacktestDay]
