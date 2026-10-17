"""MacroTable: the pure, annual view of the world that the engine and sim consume.

Flow: adapters (W1) -> Observations -> `lifeline_data.macro.build_macro_table()` -> MacroTable
-> engine (W2) and sim (W3). Engine and sim never touch the network. Same table + same seed
gives the same life.

Lookup rule: `get(key, year, region)` returns the regional value if present. Otherwise it
returns the UK value with note "UK average used". If the year is outside the table, it
returns the nearest year with note "nearest year used".
"""

from __future__ import annotations

from enum import StrEnum
from functools import cached_property

from pydantic import BaseModel, ConfigDict

from lifeline_contracts.observation import Status


class MacroKey(StrEnum):
    """Canonical annual series. Units in comments. Rates are percent (4.5 means 4.5%)."""

    BANK_RATE = "bank_rate"  # percent, annual average. BoE IUMBEDR
    MORTGAGE_2Y_FIX = "mortgage_2y_fix"  # percent. BoE IUMBV34
    MORTGAGE_5Y_FIX = "mortgage_5y_fix"  # percent. BoE IUMBV42
    CPI_INFLATION = "cpi_inflation"  # percent y/y. ONS D7G7
    HOUSE_PRICE = "house_price"  # gbp average price, regional. Land Registry UK HPI
    HOUSE_PRICE_CHANGE = "house_price_change"  # percent y/y, regional. Land Registry UK HPI
    MEDIAN_PAY = "median_pay"  # gbp annual gross, regional. Nomis ASHE NM_30_1
    UNEMPLOYMENT = "unemployment"  # percent, regional. Nomis APS NM_17_5
    OWNER_OCCUPIED_SHARE = "owner_occupied_share"  # percent, regional. Nomis Census NM_2072_1
    GILT_10Y = "gilt_10y"  # percent. FRED IRLTLT01GBM156N
    STOCK_RETURN = "stock_return"  # percent y/y total-ish return, FTSE proxy. Yahoo
    CRYPTO_RETURN = "crypto_return"  # percent y/y. CoinGecko (2013+)
    GBP_USD = "gbp_usd"  # rate. Frankfurter
    ENERGY_PRICE_CHANGE = "energy_price_change"  # percent y/y. ONS CPI energy / Octopus
    FUEL_PRICE_CHANGE = "fuel_price_change"  # percent y/y. ONS
    RENT_CHANGE = "rent_change"  # percent y/y, regional. ONS PIPR / IPHRP
    BURGLARY_RATE = "burglary_rate"  # per 1000 households per year, regional. Police UK
    FLOOD_RISK = "flood_risk"  # percent annual chance, regional. Environment Agency
    SAVINGS_RATE = "savings_rate"  # percent, instant-access deposit rate. BoE quoted household rates (ADR 0018)
    CARD_RATE = "card_rate"  # percent, credit card rate. BoE quoted household rates (ADR 0018)
    ENERGY_TARIFF = "energy_tariff"  # gbp per year, typical dual-fuel bill. Octopus / price cap (ADR 0018)


class MacroValue(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: MacroKey
    year: int
    region: str | None
    value: float
    source: str
    series_id: str
    status: Status
    note: str | None = None  # e.g. "UK average used"


class MacroTable(BaseModel):
    """Immutable annual table. Key string format: f"{key}|{year}|{region or 'uk'}"."""

    model_config = ConfigDict(frozen=True)

    values: dict[str, MacroValue]

    @staticmethod
    def make_key(key: MacroKey | str, year: int, region: str | None) -> str:
        return f"{MacroKey(key).value}|{year}|{region or 'uk'}"

    @cached_property
    def _years_index(self) -> dict[MacroKey, list[int]]:
        idx: dict[MacroKey, set[int]] = {}
        for v in self.values.values():
            idx.setdefault(v.key, set()).add(v.year)
        return {k: sorted(ys) for k, ys in idx.items()}

    def years(self, key: MacroKey | str) -> list[int]:
        return list(self._years_index.get(MacroKey(key), []))

    def get(self, key: MacroKey | str, year: int, region: str | None = None) -> MacroValue:
        key = MacroKey(key)
        years = self.years(key)
        if not years:
            raise KeyError(f"no data for {key}")
        note: str | None = None
        if year < years[0] or year > years[-1] or year not in self._years_index[key]:
            year = min(years, key=lambda y: (abs(y - year), y))
            note = "nearest year used"
        if region is not None:
            hit = self.values.get(self.make_key(key, year, region))
            if hit is not None:
                return hit if note is None else hit.model_copy(update={"note": note})
        uk = self.values.get(self.make_key(key, year, None))
        if uk is None:
            raise KeyError(f"no UK value for {key} {year}")
        if region is not None:
            note = "UK average used" if note is None else f"UK average used; {note}"
        return uk if note is None else uk.model_copy(update={"note": note})

    def value(self, key: MacroKey | str, year: int, region: str | None = None) -> float:
        return self.get(key, year, region).value
