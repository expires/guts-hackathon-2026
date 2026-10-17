"""Habits and ISA replay (ADR 0018). The return series is SYNTHETIC and every response says so
(`data_status: mock`, `label`). The ISA mix comes from the caller's own holdings, never from another subject's.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from lifeline_api import money
from lifeline_api.auth import Subject
from lifeline_api.errors import ApiError
from lifeline_api.sim_bridge import call_pure
from lifeline_contracts.finance import FinanceSnapshot
from lifeline_contracts.habits import HabitFactors
from lifeline_contracts.investing import (
    ASSETS,
    IsaBacktestQuery,
    IsaBacktestResponse,
    IsaPeriod,
    IsaPeriodsResponse,
    IsaScenariosQuery,
    IsaScenariosResult,
)
from lifeline_engine.isa_scenarios import isa_scenarios
from lifeline_engine.money.habits import DEFAULT_WORST_DRAWDOWN, habit_factors, monthly_saving
from lifeline_eval.isa_backtest import PERIOD_LABELS, PERIODS, isa_compare, weights_from_holdings, worst_drawdown_for

router = APIRouter(tags=["investing"])

DEFAULT_MONTHLY_CONTRIBUTION = 100.0


def _habits(snap: FinanceSnapshot) -> HabitFactors:
    weights = weights_from_holdings(snap.holdings)
    worst = worst_drawdown_for(weights, money.returns()) if weights else DEFAULT_WORST_DRAWDOWN
    return habit_factors(snap, money.today(snap), worst_drawdown=worst)


def _contribution(snap: FinanceSnapshot, requested: float | None) -> tuple[float, str]:
    """(gbp per month, source). Request wins, then the mean of the last 6 months of savings moves, then 100."""
    if requested is not None:
        return requested, "request"
    derived = monthly_saving(snap.transactions, money.today(snap))
    if derived is not None and derived > 0:
        return derived, "derived"
    return DEFAULT_MONTHLY_CONTRIBUTION, "default"


def _check_periods(*periods: str) -> None:
    for p in periods:
        if p not in PERIODS:
            raise ApiError(422, "validation_error", f"period: unknown period {p!r}. Use one of {sorted(PERIODS)}")


@router.get("/v1/finance/habits", response_model=HabitFactors, response_model_exclude_none=True)
async def get_habits(request: Request, sub: Subject) -> HabitFactors:
    snap = await money.snapshot(request.app.state.lifeline, sub)
    return await call_pure(_habits, snap)


@router.get("/v1/finance/isa/periods", response_model=IsaPeriodsResponse, response_model_exclude_none=True)
async def get_isa_periods(sub: Subject) -> IsaPeriodsResponse:
    series = money.returns()
    return IsaPeriodsResponse(
        periods=[
            IsaPeriod(id=pid, label=PERIOD_LABELS[pid][0].upper() + PERIOD_LABELS[pid][1:], start=a, end=b)
            for pid, (a, b) in PERIODS.items()
        ],
        assets=list(ASSETS),
        label=series.label,
        data_status=series.data_status,
    )


@router.post("/v1/finance/isa/backtest", response_model=IsaBacktestResponse, response_model_exclude_none=True)
async def post_isa_backtest(body: IsaBacktestQuery, request: Request, sub: Subject) -> IsaBacktestResponse:
    _check_periods(*(s.period for s in body.strategies))
    snap = await money.snapshot(request.app.state.lifeline, sub)
    amount, source = _contribution(snap, body.monthly_contribution)
    series = money.returns()
    reqs = [s.to_request(amount) for s in body.strategies]
    try:
        results = await call_pure(isa_compare, reqs, series)
    except ValueError as exc:
        raise ApiError(422, "validation_error", str(exc)) from None
    return IsaBacktestResponse(
        results=results,
        monthly_contribution=amount,
        contribution_source=source,  # type: ignore[arg-type]
        label=series.label,
        data_status=series.data_status,
    )


@router.post("/v1/finance/isa/scenarios", response_model=IsaScenariosResult, response_model_exclude_none=True)
async def post_isa_scenarios(body: IsaScenariosQuery, request: Request, sub: Subject) -> IsaScenariosResult:
    _check_periods(body.strategy.period)
    snap = await money.snapshot(request.app.state.lifeline, sub)
    amount, _ = _contribution(snap, body.monthly_contribution)
    req = body.strategy.to_request(amount)
    try:
        result: IsaScenariosResult = await call_pure(
            isa_scenarios, req, money.returns(), None, 8, body.horizon_months
        )
    except ValueError as exc:
        raise ApiError(422, "validation_error", str(exc)) from None
    return result
