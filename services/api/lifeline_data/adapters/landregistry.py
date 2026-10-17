"""HM Land Registry UK House Price Index, linked-data JSON list endpoint.

One request per region per page (page size 200 months). Regions include Scotland and Northern Ireland.
Series ids: `ukhpi-average-price` (gbp) and `ukhpi-annual-change` (percent y/y). Both come from the
same payload.
"""

from __future__ import annotations

import asyncio
import json
from datetime import date
from typing import Any, ClassVar

from lifeline_contracts.observation import REGIONS, Observation
from lifeline_data.base import Adapter, PayloadError, parse_number

LR_LIST_URL = "https://landregistry.data.gov.uk/data/ukhpi.json"
LR_REGION_URI = "http://landregistry.data.gov.uk/id/region/{slug}"
UK_SLUG = "united-kingdom"
SERIES_FIELDS = {
    "ukhpi-average-price": ("averagePrice", "gbp"),
    "ukhpi-annual-change": ("percentageAnnualChange", "percent"),
}
PAGE_SIZE = 200
MAX_PAGES = 5


def parse_ukhpi_items(payload: str | dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    """Returns (items, next page URL or None)."""
    data = json.loads(payload) if isinstance(payload, str) else payload
    try:
        result = data["result"]
    except (KeyError, TypeError) as exc:
        raise PayloadError("landregistry: no result") from exc
    if "items" in result:
        return list(result["items"]), result.get("next")
    if "primaryTopic" in result:  # single-month resource
        return [result["primaryTopic"]], None
    raise PayloadError("landregistry: no items")


def items_to_points(items: list[dict[str, Any]], field: str) -> list[tuple[date, float]]:
    out: list[tuple[date, float]] = []
    for item in items:
        raw = item.get(field)
        if raw is None:
            continue  # early months have no annual change
        month = str(item.get("refMonth") or "")
        if isinstance(item.get("refMonth"), dict):
            month = str(item["refMonth"].get("_value", ""))
        try:
            year, mon = int(month[:4]), int(month[5:7])
        except ValueError as exc:
            raise PayloadError(f"landregistry: bad month {month!r}") from exc
        out.append((date(year, mon, 1), parse_number(raw)))
    return out


class LandRegistryAdapter(Adapter):
    source_id = "landregistry"
    default_series: ClassVar[tuple[tuple[str, str | None], ...]] = (
        ("ukhpi-average-price", None),
        ("ukhpi-annual-change", None),
    )
    bounds: ClassVar[dict[str, tuple[float, float]]] = {
        "ukhpi-average-price": (5_000.0, 5_000_000.0),
        "ukhpi-annual-change": (-60.0, 100.0),
    }
    min_month = "1990-01"

    async def _region_items(self, slug: str) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "refRegion": LR_REGION_URI.format(slug=slug),
            "min-refMonth": self.min_month,
            "_pageSize": str(PAGE_SIZE),
            "_sort": "refMonth",
            "_properties": "averagePrice,percentageAnnualChange,refMonth",
        }
        items: list[dict[str, Any]] = []
        for page in range(MAX_PAGES):
            batch, nxt = parse_ukhpi_items(await self.get_text(LR_LIST_URL, {**params, "_page": str(page)}))
            items.extend(batch)
            if not nxt or len(batch) < PAGE_SIZE:
                break
        return items

    async def fetch(self, series_id: str, region: str | None = None) -> list[Observation]:
        if series_id not in SERIES_FIELDS:
            raise PayloadError(f"landregistry: unknown series {series_id}")
        field, unit = SERIES_FIELDS[series_id]
        regions: list[str | None] = [region] if region is not None else [None, *REGIONS]
        sem = asyncio.Semaphore(4)

        async def one(reg: str | None) -> list[Observation]:
            async with sem:
                items = await self._region_items(reg or UK_SLUG)
            return [self.obs(series_id, day, value, unit, reg) for day, value in items_to_points(items, field)]

        results = await asyncio.gather(*(one(r) for r in regions))
        return [o for batch in results for o in batch]
