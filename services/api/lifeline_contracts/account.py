"""Tier 2 (away plan): accounts, onboarding inputs, on-device connectors. BOSS-owned. ADR 0029.

Monzo and Trading212 connections are Yaffy's area (/v1/connections) and are NOT defined here.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from lifeline_contracts.domain import IsoDate, RegionSlug, ShortId
from lifeline_contracts.finance import Category, DebtItem, IncomeKind, IncomeSource, StudentLoanPlan, Transaction
from lifeline_contracts.observation import Status


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------- account ----------

FinanceInput = Literal["statement", "manual", "bank", "app_intent", "sample"]


class Me(_M):
    id: str
    display_name: str | None = None
    auth_provider: Literal["apple", "demo"]
    created_at: str
    has_finance_data: bool
    finance_inputs: list[FinanceInput]
    bank_name: str | None = Field(default=None, max_length=40, description="Connected bank, e.g. 'Monzo'")


# ---------- onboarding: statement upload ----------

StatementProvider = Literal["monzo", "revolut", "pdf", "unknown"]


class ImportStage(_M):
    name: Literal["read", "categorise", "find_bills", "build_profile", "next_move"]
    label: str
    done: bool


class ImportResult(_M):
    """Returned by POST /v1/finance/statements (multipart file). The client animates `stages`."""

    import_id: str
    status: Literal["done", "partial", "failed"]
    provider: StatementProvider
    transactions: int = Field(ge=0)
    first_date: IsoDate | None = None
    last_date: IsoDate | None = None
    months_covered: float = Field(ge=0)
    warnings: list[str] = Field(default_factory=list, max_length=20)
    stages: list[ImportStage]


# ---------- onboarding: sample statements (ADR 0047) ----------


class SampleStatement(_M):
    """A built-in synthetic student statement. Imported data is always labelled "Sample data"."""

    id: ShortId
    title: str = Field(max_length=40, description="e.g. 'Scholarship student'")
    description: str = Field(max_length=160)
    funding: list[IncomeKind] = Field(max_length=8)
    months: int = Field(ge=1, le=12)
    team: bool = Field(default=False, description="Team phone profile, hidden from the judge picker")


class SamplesResponse(_M):
    samples: list[SampleStatement]


# ---------- onboarding: manual entry ----------


class RegularCost(_M):
    name: str = Field(min_length=1, max_length=40)
    monthly_amount: float = Field(ge=0, le=100_000)
    category: Category = "bills"


class ManualFinanceInput(_M):
    postcode: str = Field(min_length=5, max_length=8, pattern=r"^[A-Za-z0-9 ]+$")
    housing: Literal["rent", "own", "mortgage", "parents"]
    monthly_rent: float | None = Field(default=None, ge=0, le=100_000)
    mortgage_balance: float | None = Field(default=None, ge=0, le=10_000_000)
    mortgage_rate_pct: float | None = Field(default=None, ge=0, le=30)
    mortgage_years_left: int | None = Field(default=None, ge=0, le=40)
    deal_end: IsoDate | None = None
    property_value: float | None = Field(default=None, ge=0, le=100_000_000)
    monthly_take_home: float = Field(ge=0, le=1_000_000)
    regular_costs: list[RegularCost] = Field(default_factory=list, max_length=30)
    savings: float = Field(default=0, ge=0, le=100_000_000)
    birth_year: int | None = Field(default=None, ge=1920, le=2010)
    # Student fields (ADR 0049). All optional so older clients still validate.
    is_student: bool | None = None
    age: int | None = Field(default=None, ge=16, le=100)
    income_sources: list[IncomeSource] = Field(default_factory=list, max_length=20)
    student_loan_plan: StudentLoanPlan | None = None
    debts: list[DebtItem] = Field(default_factory=list, max_length=20)


# ---------- connectors ----------


class ReversePostcode(_M):
    postcode: str
    region: RegionSlug
    town: str
    status: Status


class HealthSignal(_M):
    """From HealthKit on the device. Feeds the Life tab Health stat (ADR 0029)."""

    steps_per_day: float = Field(ge=0, le=100_000)
    sleep_hours: float = Field(ge=0, le=24)
    measured_days: int = Field(ge=1, le=366)
    source: Literal["healthkit"] = "healthkit"


class HealthSignalStored(_M):
    steps_per_day: float
    sleep_hours: float
    measured_days: int
    health_effect: int = Field(ge=-10, le=10, description="Points added to the Life Health stat at the next AGE")
    updated_at: str


class LogPaymentRequest(_M):
    """App Intent "Log a payment" (Shortcuts Wallet-tap automation)."""

    amount: float = Field(gt=0, le=100_000)
    merchant: str = Field(min_length=1, max_length=80)
    date: IsoDate | None = None
    category: Category | None = None


class LoggedPayment(_M):
    transaction: Transaction
    category: Category
