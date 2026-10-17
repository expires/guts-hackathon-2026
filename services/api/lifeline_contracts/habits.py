"""Money habit factors: ratios, months and 0-100 scores only. No money amounts leave the device."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FactorId = Literal[
    "savings_rate",
    "runway_months",
    "spend_stability",
    "discretionary_share",
    "subscription_creep",
    "isa_concentration",
    "shock_resilience",
]


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HabitFactor(_M):
    id: FactorId
    label: str = Field(description="Plain English name")
    explainer: str = Field(description="One line, plain English")
    raw: float | None = Field(
        default=None, description="Ratio or months, rounded to 3 decimals; null if not computable"
    )
    score: int | None = Field(default=None, ge=0, le=100, description="0-100, higher is better")
    reason: str | None = Field(default=None, description="Why raw is null")


class HabitWindow(_M):
    months: int = Field(ge=1)
    end: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class HabitFactors(_M):
    version: Literal["hf-1"] = "hf-1"
    window: HabitWindow
    factors: list[HabitFactor]
    overall: int | None = Field(default=None, ge=0, le=100, description="Mean of the factor scores; null if none")
