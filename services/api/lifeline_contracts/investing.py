"""ISA investing models: monthly return series, backtest and modelled scenarios. See ADR 0018.

All money is GBP floats. Index series are time-weighted and rebased to 100.
The default return series is SYNTHETIC (data_status "mock") and must be labelled as such in the UI.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ASSETS: tuple[str, ...] = ("global_equity", "uk_equity", "gilts", "cash")
SCENARIO_LABEL = "Modelled scenarios from similar past periods. Not a forecast. Not financial advice."
RETURNS_LABEL = "Synthetic illustrative returns"


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReturnSeries(_M):
    """Monthly simple returns, one row per month, one column per asset."""

    months: list[str] = Field(description="YYYY-MM, oldest first")
    assets: list[str]
    returns: list[list[float]] = Field(description="returns[i][j] is asset j in month i")
    label: str = RETURNS_LABEL
    data_status: Literal["mock"] = "mock"

    @model_validator(mode="after")
    def _shape(self) -> ReturnSeries:
        if len(self.returns) != len(self.months) or any(len(r) != len(self.assets) for r in self.returns):
            raise ValueError("returns must be len(months) x len(assets)")
        return self


class IsaBacktestRequest(_M):
    weights: dict[str, float]
    technique: Literal["dca", "lump_sum"] = "dca"
    rebalance: Literal["none", "annual", "threshold"] = "annual"
    threshold_pp: float = Field(default=5.0, ge=0)
    period: str = "gfc_2008"
    monthly_contribution: float = Field(gt=0, description="gbp per month")
    isa_allowance: float = Field(default=20_000.0, ge=0, description="gbp per tax year")

    @model_validator(mode="after")
    def _valid_weights(self) -> IsaBacktestRequest:
        bad = set(self.weights) - set(ASSETS)
        if bad:
            raise ValueError(f"unknown assets: {sorted(bad)}")
        if any(v < 0 for v in self.weights.values()):
            raise ValueError("weights must be non-negative")
        if abs(sum(self.weights.values()) - 1.0) > 1e-6:
            raise ValueError("weights must sum to 1")
        return self


class IsaBacktestMetrics(_M):
    """Computed on the time-weighted index."""

    cagr: float
    volatility: float = Field(description="annualised")
    max_drawdown: float = Field(description="positive fraction")
    months_to_recover: int | None = Field(default=None, description="trough to new peak; null if never recovered")
    worst_12m: float


class IsaBacktestResult(_M):
    period: str
    label: str = Field(description="Plain English name of the replay period")
    months: list[str] = Field(description="months[0] is the month before the start (index 100)")
    index: list[float]
    metrics: IsaBacktestMetrics
    contributed: float = Field(description="gbp")
    final_value: float = Field(description="gbp")
    money_weighted_return: float | None = Field(default=None, description="annual; null if undefined")
    data_status: Literal["mock"] = "mock"
    data_label: str = RETURNS_LABEL


class ScenarioPath(_M):
    start_month: str = Field(description="The analog month; the strategy runs over the months after it")
    index: list[float] = Field(description="Rebased to 100, horizon + 1 points")


class ScenarioFan(_M):
    p10: list[float]
    p50: list[float]
    p90: list[float]


class IsaScenariosResult(_M):
    paths: list[ScenarioPath]
    fan: ScenarioFan
    horizon_months: int = Field(ge=1)
    label: str = Field(default=SCENARIO_LABEL, description="Always shown with the chart")
    data_status: Literal["mock"] = "mock"
    data_label: str = RETURNS_LABEL

    @model_validator(mode="after")
    def _label_required(self) -> IsaScenariosResult:
        if self.label != SCENARIO_LABEL:
            raise ValueError("scenario label cannot be changed")
        return self


# ---------- HTTP request and response wrappers ----------


class IsaStrategy(_M):
    """One mix to replay. Same rules as IsaBacktestRequest, without the contribution."""

    weights: dict[str, float]
    technique: Literal["dca", "lump_sum"] = "dca"
    rebalance: Literal["none", "annual", "threshold"] = "annual"
    threshold_pp: float = Field(default=5.0, ge=0)
    period: str = "gfc_2008"
    isa_allowance: float = Field(default=20_000.0, ge=0, description="gbp per tax year")

    @model_validator(mode="after")
    def _valid_weights(self) -> IsaStrategy:
        bad = set(self.weights) - set(ASSETS)
        if bad:
            raise ValueError(f"unknown assets: {sorted(bad)}")
        if any(v < 0 for v in self.weights.values()):
            raise ValueError("weights must be non-negative")
        if abs(sum(self.weights.values()) - 1.0) > 1e-6:
            raise ValueError("weights must sum to 1")
        return self

    def to_request(self, monthly_contribution: float) -> IsaBacktestRequest:
        return IsaBacktestRequest(monthly_contribution=monthly_contribution, **self.model_dump())


class IsaBacktestQuery(_M):
    """POST /v1/finance/isa/backtest. Leave monthly_contribution out to use the user's own habit."""

    strategies: list[IsaStrategy] = Field(min_length=1, max_length=4)
    monthly_contribution: float | None = Field(default=None, gt=0, le=1_000_000, description="gbp per month")


class IsaBacktestResponse(_M):
    results: list[IsaBacktestResult]
    monthly_contribution: float = Field(description="gbp per month used for every strategy")
    contribution_source: Literal["request", "derived", "default"] = Field(
        description="request: sent by the client. derived: mean of the last 6 months of ISA and savings transfers. "
        "default: not enough history, 100 used"
    )
    label: str = RETURNS_LABEL
    data_status: Literal["mock"] = "mock"


class IsaScenariosQuery(_M):
    """POST /v1/finance/isa/scenarios."""

    strategy: IsaStrategy
    monthly_contribution: float | None = Field(default=None, gt=0, le=1_000_000, description="gbp per month")
    horizon_months: int = Field(default=36, ge=6, le=60)


class IsaPeriod(_M):
    id: str
    label: str = Field(description="Plain English name of the period")
    start: str = Field(pattern=r"^\d{4}-\d{2}$")
    end: str = Field(pattern=r"^\d{4}-\d{2}$")


class IsaPeriodsResponse(_M):
    periods: list[IsaPeriod]
    assets: list[str]
    label: str = RETURNS_LABEL
    data_status: Literal["mock"] = "mock"
