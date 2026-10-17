"""Nomis API CSV: ASHE earnings (NM_30_1), APS unemployment (NM_17_5), Census 2021 tenure (NM_2072_1).

Geography TYPE480 = the 12 UK regions and countries. 2092957697 = United Kingdom.
2092957703 = England and Wales (Census tables cover England and Wales only).
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date
from typing import ClassVar

from lifeline_contracts.observation import Observation
from lifeline_data.base import Adapter, PayloadError, parse_number, utcnow
from lifeline_data.regions import region_from_code

NOMIS_BASE = "https://www.nomisweb.co.uk/api/v01/dataset"
SELECT = "date_name,date_code,geography_name,geography_code,obs_value"


@dataclass(frozen=True)
class NomisSeries:
    params: dict[str, str]
    unit: str
    month: int  # month used for the observation date of a yearly value
    dec_only: bool = False  # APS: keep only Jan-Dec windows (date code YYYY-12)


def _aps_dates() -> str:
    return ",".join(f"{y}-12" for y in range(2004, utcnow().year))


def nomis_series(series_id: str) -> NomisSeries:
    match series_id:
        case "NM_30_1":  # ASHE median gross annual pay, full-time workers, workplace-based
            return NomisSeries(
                {"geography": "TYPE480,2092957697", "date": "latestMINUS28-latest", "sex": "8", "item": "2",
                 "pay": "7", "measures": "20100"},
                "gbp", 4,
            )
        case "NM_17_5":  # APS unemployment rate, aged 16+
            return NomisSeries(
                {"geography": "TYPE480,2092957697", "date": _aps_dates(), "variable": "83", "measures": "20599"},
                "percent", 12, dec_only=True,
            )
        case "NM_2072_1":  # Census 2021 TS054 tenure, percent of households owned
            return NomisSeries(
                {"geography": "TYPE480,2092957703", "c2021_tenure_9": "1001", "measures": "20301"}, "percent", 3
            )
    raise PayloadError(f"nomis: unknown series {series_id}")


def parse_nomis_csv(text: str, month: int = 7, dec_only: bool = False) -> list[tuple[date, str | None, float]]:
    """Returns (date, region slug or None for UK / England and Wales, value)."""
    rows = list(csv.DictReader(io.StringIO(text.strip())))
    if not rows or "OBS_VALUE" not in rows[0]:
        raise PayloadError("nomis: empty or unexpected CSV")
    out: list[tuple[date, str | None, float]] = []
    for row in rows:
        code = (row.get("DATE_CODE") or row.get("DATE_NAME") or "").strip()
        if dec_only and not code.endswith("-12"):
            continue
        try:
            year = int(code[:4])
        except ValueError as exc:
            raise PayloadError(f"nomis: bad date {code!r}") from exc
        try:
            region = region_from_code(row["GEOGRAPHY_CODE"])
        except KeyError:
            continue  # geography we do not model
        out.append((date(year, month, 1), region, parse_number(row["OBS_VALUE"])))
    return out


class NomisAdapter(Adapter):
    source_id = "nomis"
    default_series: ClassVar[tuple[tuple[str, str | None], ...]] = (
        ("NM_30_1", None),
        ("NM_17_5", None),
        ("NM_2072_1", None),
    )
    bounds: ClassVar[dict[str, tuple[float, float]]] = {
        "NM_30_1": (1_000.0, 500_000.0),
        "NM_17_5": (0.0, 40.0),
        "NM_2072_1": (0.0, 100.0),
    }

    async def fetch(self, series_id: str, region: str | None = None) -> list[Observation]:
        spec = nomis_series(series_id)
        text = await self.get_text(f"{NOMIS_BASE}/{series_id}.data.csv", {**spec.params, "select": SELECT})
        rows = parse_nomis_csv(text, spec.month, spec.dec_only)
        return [self.obs(series_id, day, value, spec.unit, reg) for day, reg, value in rows]
