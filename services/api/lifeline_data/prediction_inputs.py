"""Prediction inputs (ADR 0017): UK bank holidays and daily weather by region.

- Bank holidays: gov.uk `bank-holidays.json`. Divisions: england-and-wales, scotland, northern-ireland.
  A recorded copy ships in `lifeline_data/fixtures/bank-holidays.json` for offline use.
- Weather: Open-Meteo daily max temperature and precipitation at one reference point per region
  (the main city of the region). The mock weather here is deterministic per (region, date) and is
  labelled `status="mock"`.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

from lifeline_data.base import PayloadError

BANK_HOLIDAYS_URL = "https://www.gov.uk/bank-holidays.json"
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"

DIVISIONS = ("england-and-wales", "scotland", "northern-ireland")

# Region slug -> (latitude, longitude) of the region's main city. None = UK (Birmingham, near the centre).
REGION_POINTS: dict[str | None, tuple[float, float]] = {
    "north-east": (54.9783, -1.6178),  # Newcastle upon Tyne
    "north-west": (53.4808, -2.2426),  # Manchester
    "yorkshire-and-the-humber": (53.8008, -1.5491),  # Leeds
    "east-midlands": (52.9548, -1.1581),  # Nottingham
    "west-midlands": (52.4862, -1.8904),  # Birmingham
    "east-of-england": (52.2053, 0.1218),  # Cambridge
    "london": (51.5072, -0.1276),
    "south-east": (51.4543, -0.9781),  # Reading
    "south-west": (51.4545, -2.5879),  # Bristol
    "wales": (51.4816, -3.1791),  # Cardiff
    "scotland": (55.8642, -4.2518),  # Glasgow
    "northern-ireland": (54.5973, -5.9301),  # Belfast
    None: (52.4862, -1.8904),
}


def division_for_region(region: str | None) -> str:
    """gov.uk division for a region slug. England regions and None map to england-and-wales."""
    if region == "scotland":
        return "scotland"
    if region == "northern-ireland":
        return "northern-ireland"
    return "england-and-wales"


def parse_bank_holidays(payload: str | dict[str, Any]) -> dict[str, set[date]]:
    """Parse gov.uk bank-holidays.json into {division: {dates}}. Rejects a payload with no events."""
    data = json.loads(payload) if isinstance(payload, str) else payload
    if not isinstance(data, dict):
        raise PayloadError("bankholidays: not an object")
    out: dict[str, set[date]] = {}
    for key, block in data.items():
        if not isinstance(block, dict):
            continue
        division = str(block.get("division") or key)
        days: set[date] = set()
        for event in block.get("events") or []:
            try:
                day = date.fromisoformat(str(event["date"]))
            except (KeyError, TypeError, ValueError) as exc:
                raise PayloadError(f"bankholidays: bad event {event!r}") from exc
            if not (date(1990, 1, 1) <= day <= date(2100, 1, 1)):
                raise PayloadError(f"bankholidays: date out of range {day}")
            days.add(day)
        if days:
            out[division] = days
    if not any(d in out for d in DIVISIONS):
        raise PayloadError("bankholidays: no known division with events")
    return out


@lru_cache(maxsize=1)
def fixture_bank_holidays() -> dict[str, frozenset[date]]:
    """Recorded gov.uk payload (2019-2028). Used offline and as the last fallback."""
    parsed = parse_bank_holidays((FIXTURE_DIR / "bank-holidays.json").read_text())
    return {k: frozenset(v) for k, v in parsed.items()}


def fixture_holidays_for(region: str | None) -> set[date]:
    return set(fixture_bank_holidays().get(division_for_region(region), frozenset()))


def is_working_day(day: date, holidays: set[date] | frozenset[date]) -> bool:
    return day.weekday() < 5 and day not in holidays


# --- mock weather ---------------------------------------------------------------------------

# (mean annual max temp C, seasonal amplitude C, wet-day probability, mean rain on a wet day mm)
_CLIMATE: dict[str | None, tuple[float, float, float, float]] = {
    "north-east": (12.6, 6.4, 0.42, 4.2),
    "north-west": (13.4, 6.6, 0.52, 5.0),
    "yorkshire-and-the-humber": (13.6, 6.9, 0.45, 4.3),
    "east-midlands": (14.2, 7.2, 0.42, 4.0),
    "west-midlands": (14.0, 7.1, 0.45, 4.3),
    "east-of-england": (14.8, 7.4, 0.38, 3.8),
    "london": (15.5, 7.6, 0.40, 4.0),
    "south-east": (15.0, 7.3, 0.42, 4.4),
    "south-west": (14.6, 6.5, 0.50, 5.0),
    "wales": (14.0, 6.2, 0.55, 5.6),
    "scotland": (12.3, 6.3, 0.55, 5.2),
    "northern-ireland": (12.8, 5.8, 0.55, 4.6),
    None: (14.0, 7.0, 0.45, 4.4),
}


def _unit_rng(*parts: object) -> random.Random:
    """Process-stable RNG (Python's hash() is salted per process; sha256 is not)."""
    seed = int.from_bytes(hashlib.sha256("|".join(map(str, parts)).encode()).digest()[:8], "big")
    return random.Random(seed)  # noqa: S311 - simulation, not crypto


def mock_weather_day(region: str | None, day: date) -> dict[str, Any]:
    """Deterministic plausible UK weather for one day. status='mock'."""
    mean, amp, wet_p, wet_mm = _CLIMATE.get(region, _CLIMATE[None])
    rng = _unit_rng("weather", region or "uk", day.isoformat())
    # Warmest around 20 July (day 201), coldest around 20 January.
    season = math.cos(2 * math.pi * (day.timetuple().tm_yday - 201) / 365.25)
    temp = mean + amp * season + rng.gauss(0, 2.4)
    wet = rng.random() < wet_p + 0.08 * (-season)  # wetter in winter
    rain = round(rng.expovariate(1 / wet_mm), 1) if wet else 0.0
    return {"date": day, "temp_max_c": round(temp, 1), "rain_mm": rain, "status": "mock"}


def mock_daily_weather(region: str | None, start: date, end: date) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    day = start
    while day <= end:
        out.append(mock_weather_day(region, day))
        day += timedelta(days=1)
    return out
