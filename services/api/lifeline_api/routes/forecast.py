"""The forecast Next Move (PENNY_V3_BUILD.md B, ADR 0072).

- GET /v1/forecast: FinanceSnapshot (W1) + MacroTable (W1, CPI and the BoE easy-access rate) + the stored buffer %
  -> lifeline_engine.forecast.compute (W2). `buffer_pct` previews another buffer without storing it. `stress=2022`
  adds the 2022 prices test. `language`: the forecast text is English for now (numbers never change).
- PUT /v1/forecast/settings: stores the buffer % per user (doc "forecast_settings").
409 no_finance_data without the user's own data.
"""

from __future__ import annotations

import logging
from typing import Annotated, cast

from fastapi import APIRouter, Query, Request

from lifeline_api import macro, money
from lifeline_api.auth import Subject
from lifeline_api.errors import ApiError
from lifeline_api.sim_bridge import call_pure
from lifeline_api.state import AppState, get_state
from lifeline_api.store import StoreUnavailable
from lifeline_contracts.forecast import BufferPct, Forecast, ForecastSettings
from lifeline_engine import forecast as forecast_engine

log = logging.getLogger(__name__)

router = APIRouter(tags=["next-move"])

DOC_FORECAST_SETTINGS = "forecast_settings"

async def stored_settings(state: AppState, sub: str) -> ForecastSettings:
    """The user's forecast settings; the defaults when none are stored, the doc is stale or the store is down."""
    try:
        doc = await state.store.get_doc(sub, DOC_FORECAST_SETTINGS)
    except StoreUnavailable:
        log.info("forecast settings unavailable: store down, default buffer used")
        return ForecastSettings()
    try:
        return ForecastSettings.model_validate(doc) if doc else ForecastSettings()
    except ValueError:
        return ForecastSettings()


async def compute_forecast(state: AppState, sub: str, buffer_pct: BufferPct | None = None,
                           stress: int | None = None) -> Forecast:
    """The caller's forecast. Also used by Penny's forecast tool."""
    snap = await money.snapshot(state, sub)
    pct = buffer_pct if buffer_pct is not None else (await stored_settings(state, sub)).buffer_pct
    table, _ = await macro.table_fast(state)
    today = money.today(snap)
    inp = forecast_engine.macro_inputs(table, today)
    result: Forecast = await call_pure(
        forecast_engine.compute, snap, today, pct, inp.cpi, inp.inflation_2022, inp.boe_easy_access_rate, stress,
        sources=inp,
    )
    return result.model_copy(update={"meta": money.meta(snap)})


@router.get("/v1/forecast", response_model=Forecast, response_model_exclude_none=True)
async def get_forecast(
    request: Request,
    sub: Subject,
    buffer_pct: Annotated[int | None, Query()] = None,
    stress: Annotated[int | None, Query()] = None,
    language: str = "en",
) -> Forecast:
    """`language`: accepted for the 8 app languages; the forecast text is English for now (unknown -> English)."""
    if buffer_pct is not None and buffer_pct not in forecast_engine.BUFFER_OPTIONS:
        raise ApiError(422, "validation_error", "buffer_pct: pick 0, 5, 10, 15 or 20")
    if stress is not None and stress != forecast_engine.STRESS_YEAR:
        raise ApiError(422, "validation_error", "stress: only 2022 is available")
    return await compute_forecast(get_state(request), sub, cast(BufferPct | None, buffer_pct), stress)


@router.put("/v1/forecast/settings", response_model=ForecastSettings)
async def set_forecast_settings(body: ForecastSettings, request: Request, sub: Subject) -> ForecastSettings:
    state = get_state(request)
    await state.store.put_doc(sub, DOC_FORECAST_SETTINGS, body.model_dump(mode="json"))
    return body
