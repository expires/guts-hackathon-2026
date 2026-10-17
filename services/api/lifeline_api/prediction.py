"""Inputs for the spend prediction (ADR 0017): bank holidays and daily weather for the user's region (W1),
then the pure model in lifeline_engine.money.predict (W2). The backtest is cached per subject and snapshot day."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, cast

from lifeline_api import money
from lifeline_api.sim_bridge import call_pure
from lifeline_api.state import AppState
from lifeline_contracts.finance import FinanceSnapshot
from lifeline_contracts.observation import Status
from lifeline_engine.money import predict

# Days after the snapshot's as_of day that may be predicted (weather forecast range).
FORECAST_DAYS = 7


@dataclass(frozen=True)
class Inputs:
    snap: FinanceSnapshot
    holidays: frozenset[date]
    weather: dict[date, tuple[float, float]]
    weather_status: dict[date, Status]
    first_day: date
    last_day: date


async def inputs(state: AppState, sub: str) -> Inputs:
    snap = await money.snapshot(state, sub)
    as_of = money.today(snap)
    first = min((date.fromisoformat(t.date) for t in snap.transactions), default=as_of)
    last = as_of + timedelta(days=FORECAST_DAYS)
    key = ("predict-inputs", sub, money.fingerprint(snap))
    hit = state.memo.get(key)
    if hit is not None:
        return cast(Inputs, hit)
    profile, _ = await call_pure(money.engine_profile, snap, money.hints(state, sub, snap))
    hub: Any = state.hub  # bank_holidays and daily_weather are on lifeline_data.hub.DataHub (ADR 0017)
    holidays: set[date] = await hub.bank_holidays(profile.region)
    rows: list[dict[str, Any]] = await hub.daily_weather(profile.region, first, last, today=as_of)
    weather = {r["date"]: (float(r["temp_max_c"]), float(r["rain_mm"])) for r in rows}
    status: dict[date, Status] = {r["date"]: r["status"] for r in rows}
    out = Inputs(snap, frozenset(holidays), weather, status, first, last)
    state.memo[key] = out
    return out


async def backtest(state: AppState, sub: str, inp: Inputs) -> predict.Backtest:
    key = ("predict-backtest", sub, money.fingerprint(inp.snap))
    hit = state.memo.get(key)
    if hit is None:
        hit = await call_pure(predict.backtest, inp.snap, inp.holidays, inp.weather)
        state.memo[key] = hit
    return cast(predict.Backtest, hit)


def earliest_day(inp: Inputs) -> date:
    """The model needs this many complete days of history before the predicted day."""
    return inp.first_day + timedelta(days=predict.MIN_TRAIN_DAYS)


def actual_spend(inp: Inputs, day: date) -> float | None:
    """Spend for a complete day (before as_of). None while the day is not over."""
    if day >= money.today(inp.snap):
        return None
    return round(predict.daily_spend(inp.snap.transactions, day, day).get(day, 0.0), 2)
