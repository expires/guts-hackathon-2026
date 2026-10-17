"""Prediction inputs (ADR 0017): gov.uk bank holidays and Open-Meteo daily weather."""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any, ClassVar

from lifeline_contracts.observation import Observation
from lifeline_data.base import Adapter, PayloadError, parse_number
from lifeline_data.prediction_inputs import BANK_HOLIDAYS_URL, REGION_POINTS, parse_bank_holidays

OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
DAILY_VARS = "temperature_2m_max,precipitation_sum"
# The archive (ERA5) lags real time by a few days. Newer days come from the forecast API.
ARCHIVE_LAG_DAYS = 5
FORECAST_MAX_DAYS = 15
FORECAST_MAX_PAST_DAYS = 92

DIVISION_REGION: dict[str, str | None] = {
    "england-and-wales": None,
    "scotland": "scotland",
    "northern-ireland": "northern-ireland",
}

WeatherDays = dict[date, tuple[float, float]]


def parse_open_meteo_daily(payload: str | dict[str, Any]) -> WeatherDays:
    """{date: (temp_max_c, rain_mm)}. Days with a null value are skipped (the caller fills them)."""
    data = json.loads(payload) if isinstance(payload, str) else payload
    try:
        daily = data["daily"]
        days, temps, rains = daily["time"], daily["temperature_2m_max"], daily["precipitation_sum"]
    except (KeyError, TypeError) as exc:
        raise PayloadError("openmeteo: unexpected shape") from exc
    out: WeatherDays = {}
    for raw_day, t, r in zip(days, temps, rains, strict=False):
        if t is None or r is None:
            continue
        temp, rain = parse_number(t), parse_number(r)
        if not (-40.0 <= temp <= 45.0) or not (0.0 <= rain <= 400.0):
            raise PayloadError(f"openmeteo: value out of range on {raw_day}")
        out[date.fromisoformat(str(raw_day))] = (temp, rain)
    return out


class BankHolidaysAdapter(Adapter):
    source_id = "bankholidays"
    default_series: ClassVar[tuple[tuple[str, str | None], ...]] = (("england-and-wales", None),)

    async def holidays(self) -> dict[str, set[date]]:
        return parse_bank_holidays(await self.get_text(BANK_HOLIDAYS_URL))

    async def fetch(self, series_id: str, region: str | None = None) -> list[Observation]:
        days = (await self.holidays()).get(series_id)
        if not days:
            raise PayloadError(f"bankholidays: unknown division {series_id}")
        r = DIVISION_REGION.get(series_id)
        return [self.obs(series_id, d, 1.0, "flag", r) for d in sorted(days)]


class OpenMeteoAdapter(Adapter):
    source_id = "openmeteo"
    default_series: ClassVar[tuple[tuple[str, str | None], ...]] = (("temperature_2m_max", None),)
    bounds: ClassVar[dict[str, tuple[float, float]]] = {
        "temperature_2m_max": (-40.0, 45.0),
        "precipitation_sum": (0.0, 400.0),
    }

    def _params(self, region: str | None) -> dict[str, Any]:
        lat, lon = REGION_POINTS.get(region, REGION_POINTS[None])
        return {"latitude": lat, "longitude": lon, "daily": DAILY_VARS, "timezone": "Europe/London"}

    async def archive(self, region: str | None, start: date, end: date) -> WeatherDays:
        params = self._params(region) | {"start_date": start.isoformat(), "end_date": end.isoformat()}
        return parse_open_meteo_daily(await self.get_text(OPEN_METEO_ARCHIVE_URL, params))

    async def forecast(self, region: str | None, start: date, end: date) -> WeatherDays:
        params = self._params(region) | {"start_date": start.isoformat(), "end_date": end.isoformat()}
        return parse_open_meteo_daily(await self.get_text(OPEN_METEO_FORECAST_URL, params))

    async def daily(self, region: str | None, start: date, end: date, today: date) -> WeatherDays:
        """Archive for older days, forecast for recent days and up to 15 days ahead. Raises on failure."""
        out: WeatherDays = {}
        split = today - timedelta(days=ARCHIVE_LAG_DAYS)
        if start < split:
            out.update(await self.archive(region, start, min(end, split - timedelta(days=1))))
        f_start = max(start, split, today - timedelta(days=FORECAST_MAX_PAST_DAYS))
        f_end = min(end, today + timedelta(days=FORECAST_MAX_DAYS))
        if f_start <= f_end:
            for d, v in (await self.forecast(region, f_start, f_end)).items():
                out.setdefault(d, v)
        if not out:
            raise PayloadError("openmeteo: no days returned")
        return out

    async def fetch(self, series_id: str, region: str | None = None) -> list[Observation]:
        """Last 31 days plus 3 forecast days at the region's point."""
        if series_id not in self.bounds:
            raise PayloadError(f"openmeteo: unknown series {series_id}")
        params = self._params(region) | {"past_days": 31, "forecast_days": 3}
        days = parse_open_meteo_daily(await self.get_text(OPEN_METEO_FORECAST_URL, params))
        idx, unit = (0, "celsius") if series_id == "temperature_2m_max" else (1, "mm")
        return [self.obs(series_id, d, v[idx], unit, region) for d, v in sorted(days.items())]
