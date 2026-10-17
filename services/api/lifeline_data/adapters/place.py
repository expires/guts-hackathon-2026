"""Place sources: Police UK (burglary counts) and the Environment Agency flood API (England).

Neither source publishes the annual rates that the MacroTable keys BURGLARY_RATE and FLOOD_RISK need.
These adapters emit honest raw counts under their own series ids. The two MacroKeys keep their
labelled mock values until a rate source exists.
"""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime
from typing import Any, ClassVar

from lifeline_contracts.observation import REGIONS, Observation
from lifeline_data.base import Adapter, FetchError, PayloadError, utcnow
from lifeline_data.prediction_inputs import REGION_POINTS

POLICE_DATES_URL = "https://data.police.uk/api/crimes-street-dates"
POLICE_BURGLARY_URL = "https://data.police.uk/api/crimes-street/burglary"
EA_FLOODS_URL = "https://environment.data.gov.uk/flood-monitoring/id/floods"

# data.police.uk covers England, Wales and Northern Ireland. No Scottish forces.
POLICE_REGIONS = tuple(r for r in REGIONS if r != "scotland")
ENGLAND_REGIONS = tuple(r for r in REGIONS if r not in ("scotland", "wales", "northern-ireland"))

# Environment Agency area name -> region slug (approximate: EA areas follow river catchments).
EA_AREA_TO_REGION: dict[str, str] = {
    "Yorkshire": "yorkshire-and-the-humber",
    "North East": "north-east",
    "Cumbria and Lancashire": "north-west",
    "Greater Manchester Merseyside and Cheshire": "north-west",
    "East Midlands": "east-midlands",
    "Lincolnshire and Northamptonshire": "east-midlands",
    "West Midlands": "west-midlands",
    "East Anglia": "east-of-england",
    "Hertfordshire and North London": "london",
    "Thames": "london",
    "Kent South London and East Sussex": "south-east",
    "Solent and South Downs": "south-east",
    "Wessex": "south-west",
    "Devon Cornwall and the Isles of Scilly": "south-west",
}


def parse_police_latest_month(payload: str | list[Any]) -> str:
    data = json.loads(payload) if isinstance(payload, str) else payload
    try:
        month = str(data[0]["date"])
        datetime.strptime(month, "%Y-%m")
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise PayloadError("police: bad availability payload") from exc
    return month


def parse_police_crimes(payload: str | list[Any]) -> int:
    data = json.loads(payload) if isinstance(payload, str) else payload
    if not isinstance(data, list):
        raise PayloadError("police: crimes payload is not a list")
    return sum(1 for c in data if isinstance(c, dict) and c.get("category") == "burglary")


def parse_ea_floods(payload: str | dict[str, Any]) -> dict[str | None, int]:
    """Active warnings and alerts (severity 1-3) per England region; None = all England."""
    data = json.loads(payload) if isinstance(payload, str) else payload
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise PayloadError("environmentagency: no items list")
    counts: dict[str | None, int] = {r: 0 for r in ENGLAND_REGIONS}
    counts[None] = 0
    for item in items:
        level = item.get("severityLevel")
        if not isinstance(level, int) or not 1 <= level <= 3:
            continue
        counts[None] += 1
        region = EA_AREA_TO_REGION.get(str(item.get("eaAreaName", "")))
        if region is not None:
            counts[region] += 1
    return counts


class PoliceAdapter(Adapter):
    """Burglaries in the latest published month within 1 mile of each region's main city point."""

    source_id = "police"
    default_series: ClassVar[tuple[tuple[str, str | None], ...]] = (("burglary-1mile", None),)
    bounds: ClassVar[dict[str, tuple[float, float]]] = {"burglary-1mile": (0.0, 10_000.0)}

    async def fetch(self, series_id: str, region: str | None = None) -> list[Observation]:
        if series_id != "burglary-1mile":
            raise PayloadError(f"police: unknown series {series_id}")
        month = parse_police_latest_month(await self.get_text(POLICE_DATES_URL))
        day = date.fromisoformat(f"{month}-01")
        regions = [region] if region in POLICE_REGIONS else list(POLICE_REGIONS)

        async def one(r: str) -> Observation:
            lat, lng = REGION_POINTS[r]
            text = await self.get_text(POLICE_BURGLARY_URL, {"lat": lat, "lng": lng, "date": month})
            return self.obs(series_id, day, float(parse_police_crimes(text)), "count", r)

        results = await asyncio.gather(*(one(r) for r in regions), return_exceptions=True)
        out = [r for r in results if isinstance(r, Observation)]
        if not out:
            first = next((r for r in results if isinstance(r, BaseException)), None)
            raise FetchError(f"police: all regions failed ({type(first).__name__})")
        return out


class EnvironmentAgencyAdapter(Adapter):
    source_id = "environmentagency"
    default_series: ClassVar[tuple[tuple[str, str | None], ...]] = (("flood-warnings", None),)
    bounds: ClassVar[dict[str, tuple[float, float]]] = {"flood-warnings": (0.0, 5_000.0)}

    async def fetch(self, series_id: str, region: str | None = None) -> list[Observation]:
        if series_id != "flood-warnings":
            raise PayloadError(f"environmentagency: unknown series {series_id}")
        counts = parse_ea_floods(await self.get_text(EA_FLOODS_URL))
        today = utcnow().date()
        return [self.obs(series_id, today, float(n), "count", r) for r, n in counts.items()]
