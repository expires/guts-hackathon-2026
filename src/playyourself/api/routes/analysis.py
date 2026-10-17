"""Habit vector, backtest, scenarios, explain and period metadata."""

from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from playyourself.api.deps import get_returns, get_snapshot
from playyourself.api.envelope import Envelope, ok
from playyourself.decision.backtest import (
    BacktestRequest,
    LocalResult,
    Metrics,
    backtest,
)
from playyourself.decision.explain import Explanation, Kind, explain
from playyourself.decision.habits import HabitVector, habit_vector
from playyourself.decision.portfolio import isa_worst_drawdown
from playyourself.decision.returns import ASSETS, PERIODS, ReturnSeries
from playyourself.decision.scenarios import ScenarioResult, scenarios
from playyourself.decision.scoring import overall_score
from playyourself.domain.models import Snapshot
from playyourself.settings import Settings, get_settings

router = APIRouter(tags=["analysis"])

DEFAULT_CONTRIBUTION_PENCE = 10_000


class HabitVectorOut(HabitVector):
    overall_score: int | None


class Strategy(BaseModel):
    name: str | None = None
    weights: dict[str, float]
    technique: Literal["dca", "lump_sum"] = "dca"
    rebalance: Literal["none", "annual", "threshold"] = "annual"
    threshold_pp: float = 5.0
    period: str = "gfc_2008"


class BacktestIn(BaseModel):
    strategies: list[Strategy] = Field(min_length=1, max_length=6)
    monthly_contribution_pence: int | None = Field(default=None, gt=0)
    include_local: bool = True


class StrategyResult(BaseModel):
    name: str
    period: str
    technique: str
    months: list[str]
    index: list[float]  # TWR rebased to 100
    metrics: Metrics
    local: LocalResult | None = None  # LOCAL ONLY, pence; omitted when include_local is false


class BacktestOut(BaseModel):
    results: list[StrategyResult]
    contribution_source: Literal["request", "derived", "default"]
    monthly_contribution_pence: int | None = None  # LOCAL ONLY


class ScenarioIn(BaseModel):
    strategy: Strategy
    monthly_contribution_pence: int | None = Field(default=None, gt=0)


class ExplainIn(BaseModel):
    kind: Kind
    result: dict


class PeriodsOut(BaseModel):
    periods: dict[str, tuple[str, str]]
    assets: list[str]


def derive_contribution(snapshot: Snapshot) -> tuple[int, Literal["derived", "default"]]:
    """Mean monthly ISA contribution: savings transfers out over the last 6 months."""
    cutoff = snapshot.as_of - timedelta(days=183)
    total = sum(
        -t.amount_pence
        for t in snapshot.transactions
        if t.amount_pence < 0 and t.is_transfer and t.category == "savings" and t.ts >= cutoff
    )
    mean = round(total / 6)
    return (mean, "derived") if mean > 0 else (DEFAULT_CONTRIBUTION_PENCE, "default")


def _to_request(s: Strategy, contribution: int, settings: Settings) -> BacktestRequest:
    try:
        return BacktestRequest(
            weights=s.weights,
            technique=s.technique,
            rebalance=s.rebalance,
            threshold_pp=s.threshold_pp,
            period=s.period,
            monthly_contribution_pence=contribution,
            isa_allowance_pence=settings.isa_allowance_pence,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


def _contribution(
    given: int | None, snapshot: Snapshot
) -> tuple[int, Literal["request", "derived", "default"]]:
    if given is not None:
        return given, "request"
    return derive_contribution(snapshot)


@router.get("/habit-vector", response_model=Envelope[HabitVectorOut])
async def get_habit_vector(
    request: Request,
    snapshot: Snapshot = Depends(get_snapshot),
    returns: ReturnSeries = Depends(get_returns),
):
    """The only object that leaves the device: ratios and 0-100 scores, no amounts."""
    hv = habit_vector(snapshot, worst_drawdown=isa_worst_drawdown(snapshot, returns))
    out = HabitVectorOut(**hv.model_dump(), overall_score=overall_score(hv))
    return ok(out, request=request, snapshot=snapshot)


@router.post("/backtest", response_model=Envelope[BacktestOut])
async def post_backtest(
    body: BacktestIn,
    request: Request,
    snapshot: Snapshot = Depends(get_snapshot),
    returns: ReturnSeries = Depends(get_returns),
    settings: Settings = Depends(get_settings),
):
    """Replay your habits under each strategy. Index is TWR rebased to 100."""
    contribution, source = _contribution(body.monthly_contribution_pence, snapshot)
    results: list[StrategyResult] = []
    for i, s in enumerate(body.strategies):
        req = _to_request(s, contribution, settings)
        try:
            res = backtest(req, returns)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        results.append(
            StrategyResult(
                name=s.name or f"Strategy {i + 1}",
                period=s.period,
                technique=s.technique,
                months=res.months,
                index=res.index,
                metrics=res.metrics,
                local=res.local if body.include_local else None,
            )
        )
    out = BacktestOut(
        results=results,
        contribution_source=source,
        monthly_contribution_pence=contribution if body.include_local else None,
    )
    return ok(out, request=request, snapshot=snapshot)


@router.post("/scenarios", response_model=Envelope[ScenarioResult])
async def post_scenarios(
    body: ScenarioIn,
    request: Request,
    snapshot: Snapshot = Depends(get_snapshot),
    returns: ReturnSeries = Depends(get_returns),
    settings: Settings = Depends(get_settings),
):
    """Modelled scenarios from similar past periods. Not a forecast."""
    contribution, _ = _contribution(body.monthly_contribution_pence, snapshot)
    req = _to_request(body.strategy, contribution, settings)
    try:
        res = scenarios(req, returns)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return ok(res, request=request, snapshot=snapshot)


@router.post("/explain", response_model=Envelope[Explanation])
def post_explain(body: ExplainIn, request: Request, settings: Settings = Depends(get_settings)):
    """Plain-English explanation of a result. The AI only explains; it never computes."""
    return ok(explain(body.kind, body.result, settings=settings), request=request)


@router.get("/periods", response_model=Envelope[PeriodsOut])
async def get_periods(request: Request):
    return ok(PeriodsOut(periods=dict(PERIODS), assets=list(ASSETS)), request=request)
