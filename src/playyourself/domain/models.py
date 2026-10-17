"""Domain models. Money is integer pence, GBP only."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Strict int: rejects floats and numeric strings.
Pence = Annotated[int, Field(strict=True)]

Currency = Literal["GBP"]
AssetClass = Literal["equity", "bond", "cash", "property", "commodity", "other"]
BalanceKind = Literal["current", "pot", "isa_cash"]

CATEGORIES = frozenset(
    {
        "general",
        "eating_out",
        "expenses",
        "transport",
        "cash",
        "bills",
        "entertainment",
        "shopping",
        "holidays",
        "groceries",
        "personal_care",
        "family",
        "charity",
        "finances",
        "income",
        "savings",
    }
)
DISCRETIONARY_CATEGORIES = frozenset(
    {"eating_out", "entertainment", "shopping", "holidays", "personal_care"}
)


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class Transaction(_Frozen):
    id: str
    ts: datetime
    amount_pence: Pence  # negative = outflow
    currency: Currency = "GBP"
    merchant: str
    category: str
    is_transfer: bool = False

    @field_validator("ts")
    @classmethod
    def _tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("ts must be timezone-aware")
        return v


class Holding(_Frozen):
    instrument_id: str
    name: str
    quantity: float
    value_pence: Annotated[int, Field(strict=True, ge=0)]
    currency: Currency = "GBP"
    asset_class: AssetClass
    region: str | None = None


class Balance(_Frozen):
    account_id: str
    kind: BalanceKind
    value_pence: Pence
    currency: Currency = "GBP"


class SourceStatus(_Frozen):
    name: str
    ok: bool
    stale: bool = False
    as_of: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None
    dropped: int = 0
    mode: str | None = None  # "demo" | "live"


class Snapshot(_Frozen):
    balances: list[Balance] = Field(default_factory=list)
    transactions: list[Transaction] = Field(default_factory=list)
    holdings: list[Holding] = Field(default_factory=list)
    sources: dict[str, SourceStatus] = Field(default_factory=dict)
    as_of: datetime

    @property
    def liquid_cash_pence(self) -> int:
        return sum(b.value_pence for b in self.balances)

    @property
    def isa_value_pence(self) -> int:
        return sum(h.value_pence for h in self.holdings) + sum(
            b.value_pence for b in self.balances if b.kind == "isa_cash"
        )

    @property
    def stale(self) -> bool:
        return any(s.stale for s in self.sources.values())
