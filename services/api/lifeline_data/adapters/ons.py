"""ONS time series JSON, e.g. /economy/inflationandpriceindices/timeseries/d7g7/mm23/data."""

from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime
from typing import Any, ClassVar

from lifeline_contracts.observation import Observation
from lifeline_data.base import Adapter, PayloadError, parse_number
from lifeline_data.regions import region_from_code

ONS_BASE = "https://www.ons.gov.uk"
ONS_API = "https://api.beta.ons.gov.uk/v1"
# Index of Private Housing Rental Prices: regional y/y rent change, Jan 2006 to Dec 2023. ONS replaced it
# with PIPR in 2024; later years come from the mock table until a PIPR adapter exists.
IPHRP_DATASET = "index-private-housing-rental-prices"

# CDID -> (topic path, dataset id, unit)
ONS_SERIES: dict[str, tuple[str, str, str]] = {
    "D7G7": ("economy/inflationandpriceindices", "mm23", "percent"),  # CPI annual rate, all items
    "D7GT": ("economy/inflationandpriceindices", "mm23", "percent"),  # CPI annual rate 04.5 energy
}

_MONTH_NAMES = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
_MONTHS = {m: i for i, m in enumerate(_MONTH_NAMES, 1)}


def _parse_date(raw: str) -> date:
    parts = raw.strip().upper().split()
    try:
        if len(parts) == 1:
            return date(int(parts[0]), 7, 1)
        if len(parts) == 2 and parts[1] in _MONTHS:
            return date(int(parts[0]), _MONTHS[parts[1]], 1)
        if len(parts) == 2 and parts[1] in ("Q1", "Q2", "Q3", "Q4"):
            return date(int(parts[0]), (int(parts[1][1]) - 1) * 3 + 2, 1)
    except ValueError as exc:
        raise PayloadError(f"ons: bad date {raw!r}") from exc
    raise PayloadError(f"ons: bad date {raw!r}")


def parse_ons_json(payload: str | dict[str, Any]) -> list[tuple[date, float]]:
    """Use monthly points when present, else quarterly, else annual. Returns (date, value)."""
    data = json.loads(payload) if isinstance(payload, str) else payload
    if not isinstance(data, dict):
        raise PayloadError("ons: payload is not an object")
    for freq in ("months", "quarters", "years"):
        points = data.get(freq) or []
        if points:
            return [
                (_parse_date(p["date"]), parse_number(p["value"]))
                for p in points
                if str(p.get("value", "")).strip()
            ]
    raise PayloadError("ons: no data points")


def parse_iphrp_csv(text: str) -> list[tuple[date, str | None, float]]:
    """IPHRP v4 CSV. Returns (month, region slug or None for UK, y/y percent). Blank cells are skipped."""
    reader = csv.reader(io.StringIO(text.strip()))
    header = next(reader, None)
    if not header or not header[0].startswith("v4_"):
        raise PayloadError("ons: unexpected IPHRP header")
    out: list[tuple[date, str | None, float]] = []
    for row in reader:
        if len(row) < 7 or row[6] != "year-on-year-change" or not row[0].strip():
            continue
        try:
            region = region_from_code(row[4])
        except KeyError:
            continue  # England, Great Britain
        try:
            day = datetime.strptime(row[2], "%b-%y").date()
        except ValueError as exc:
            raise PayloadError(f"ons: bad IPHRP month {row[2]!r}") from exc
        out.append((day, region, parse_number(row[0])))
    return out


class OnsAdapter(Adapter):
    source_id = "ons"
    default_series: ClassVar[tuple[tuple[str, str | None], ...]] = (("D7G7", None), ("D7GT", None), ("IPHRP", None))
    bounds: ClassVar[dict[str, tuple[float, float]]] = {
        "D7G7": (-5.0, 30.0),
        "D7GT": (-60.0, 200.0),
        "IPHRP": (-30.0, 50.0),
    }

    async def _fetch_iphrp(self) -> list[Observation]:
        meta = json.loads(await self.get_text(f"{ONS_API}/datasets/{IPHRP_DATASET}"))
        version = json.loads(await self.get_text(meta["links"]["latest_version"]["href"]))
        text = await self.get_text(version["downloads"]["csv"]["href"])
        return [self.obs("IPHRP", day, value, "percent", region) for day, region, value in parse_iphrp_csv(text)]

    async def fetch(self, series_id: str, region: str | None = None) -> list[Observation]:
        cdid = series_id.upper()
        if cdid == "IPHRP":
            return await self._fetch_iphrp()
        if cdid not in ONS_SERIES:
            raise PayloadError(f"ons: unknown series {series_id}")
        topic, dataset, unit = ONS_SERIES[cdid]
        url = f"{ONS_BASE}/{topic}/timeseries/{cdid.lower()}/{dataset}/data"
        text = await self.get_text(url)
        return [self.obs(cdid, day, value, unit) for day, value in parse_ons_json(text)]
