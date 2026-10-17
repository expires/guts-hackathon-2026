"""Energy sources: Octopus Energy products API (ENERGY_TARIFF) and the Carbon Intensity API."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, ClassVar

from lifeline_contracts.observation import Observation
from lifeline_data.base import Adapter, PayloadError, parse_number

OCTOPUS_PRODUCTS_URL = "https://api.octopus.energy/v1/products/"
# Flexible Octopus: the standard variable tariff. Its price follows the Ofgem price cap.
OCTOPUS_FLEXIBLE_PREFIX = "VAR-"
OCTOPUS_FLEXIBLE_NAME = "Flexible Octopus"
CARBON_REGIONAL_URL = "https://api.carbonintensity.org.uk/regional"

# Octopus GSP group -> region slug. Groups that straddle regions (_D Merseyside and North Wales,
# _H Southern, _P North Scotland) count only towards the GB average.
GSP_TO_REGION: dict[str, str] = {
    "_A": "east-of-england",
    "_B": "east-midlands",
    "_C": "london",
    "_E": "west-midlands",
    "_F": "north-east",
    "_G": "north-west",
    "_J": "south-east",
    "_K": "wales",
    "_L": "south-west",
    "_M": "yorkshire-and-the-humber",
    "_N": "scotland",
}

# Carbon Intensity region short name -> region slug. GB -> None. Sub-national DNO areas are skipped.
CARBON_TO_REGION: dict[str, str | None] = {
    "North West England": "north-west",
    "North East England": "north-east",
    "Yorkshire": "yorkshire-and-the-humber",
    "West Midlands": "west-midlands",
    "East Midlands": "east-midlands",
    "East England": "east-of-england",
    "South West England": "south-west",
    "South East England": "south-east",
    "London": "london",
    "Scotland": "scotland",
    "Wales": "wales",
    "GB": None,
}


def find_flexible_product(payload: str | dict[str, Any]) -> str:
    data = json.loads(payload) if isinstance(payload, str) else payload
    for item in data.get("results") or []:
        code = str(item.get("code", ""))
        if (
            item.get("display_name") == OCTOPUS_FLEXIBLE_NAME
            and code.startswith(OCTOPUS_FLEXIBLE_PREFIX)
            and item.get("direction", "IMPORT") == "IMPORT"
        ):
            return code
    raise PayloadError("octopus: Flexible Octopus product not found")


def parse_octopus_quotes(payload: str | dict[str, Any]) -> tuple[date, float, dict[str, float]]:
    """Product detail -> (date, GB mean annual dual-fuel cost in GBP, {region: GBP}).

    Uses Octopus's own `sample_quotes` (direct debit, single-rate electricity plus gas, VAT included,
    at Octopus's sample consumption).
    """
    data = json.loads(payload) if isinstance(payload, str) else payload
    quotes = data.get("sample_quotes")
    if not isinstance(quotes, dict) or not quotes:
        raise PayloadError("octopus: no sample quotes")
    per_gsp: dict[str, float] = {}
    for gsp, block in quotes.items():
        try:
            pence = block["direct_debit_monthly"]["dual_fuel_single_rate"]["annual_cost_inc_vat"]
        except (KeyError, TypeError):
            try:
                pence = block["varying"]["dual_fuel_single_rate"]["annual_cost_inc_vat"]
            except (KeyError, TypeError):
                continue
        per_gsp[gsp] = round(parse_number(pence) / 100.0, 2)
    if not per_gsp:
        raise PayloadError("octopus: no dual-fuel quotes")
    raw_day = str(data.get("tariffs_active_at") or "")
    try:
        day = datetime.fromisoformat(raw_day.replace("Z", "+00:00")).date()
    except ValueError as exc:
        raise PayloadError("octopus: bad tariffs_active_at") from exc
    gb = round(sum(per_gsp.values()) / len(per_gsp), 2)
    regional = {GSP_TO_REGION[g]: v for g, v in per_gsp.items() if g in GSP_TO_REGION}
    return day, gb, regional


def parse_carbon_regional(payload: str | dict[str, Any]) -> tuple[date, dict[str | None, float]]:
    data = json.loads(payload) if isinstance(payload, str) else payload
    try:
        block = data["data"][0]
        day = datetime.fromisoformat(str(block["from"]).replace("Z", "+00:00")).date()
        regions = block["regions"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise PayloadError("carbonintensity: unexpected shape") from exc
    out: dict[str | None, float] = {}
    for r in regions:
        name = r.get("shortname")
        if name in CARBON_TO_REGION:
            out[CARBON_TO_REGION[name]] = parse_number(r["intensity"]["forecast"])
    if not out:
        raise PayloadError("carbonintensity: no known regions")
    return day, out


class OctopusAdapter(Adapter):
    """ENERGY_TARIFF: typical annual dual-fuel bill on Flexible Octopus (tracks the price cap)."""

    source_id = "octopus"
    default_series: ClassVar[tuple[tuple[str, str | None], ...]] = (("dual-fuel-typical-bill", None),)
    bounds: ClassVar[dict[str, tuple[float, float]]] = {"dual-fuel-typical-bill": (300.0, 10_000.0)}

    async def fetch(self, series_id: str, region: str | None = None) -> list[Observation]:
        if series_id != "dual-fuel-typical-bill":
            raise PayloadError(f"octopus: unknown series {series_id}")
        listing = await self.get_text(OCTOPUS_PRODUCTS_URL, {"is_variable": "true", "brand": "OCTOPUS_ENERGY"})
        code = find_flexible_product(listing)
        detail = await self.get_text(f"{OCTOPUS_PRODUCTS_URL}{code}/")
        day, gb, regional = parse_octopus_quotes(detail)
        out = [self.obs(series_id, day, gb, "gbp")]
        out += [self.obs(series_id, day, v, "gbp", r) for r, v in sorted(regional.items())]
        return out


class CarbonIntensityAdapter(Adapter):
    source_id = "carbonintensity"
    default_series: ClassVar[tuple[tuple[str, str | None], ...]] = (("intensity", None),)
    bounds: ClassVar[dict[str, tuple[float, float]]] = {"intensity": (0.0, 1_000.0)}

    async def fetch(self, series_id: str, region: str | None = None) -> list[Observation]:
        day, values = parse_carbon_regional(await self.get_text(CARBON_REGIONAL_URL))
        return [self.obs("intensity", day, v, "gco2_per_kwh", r) for r, v in values.items()]
