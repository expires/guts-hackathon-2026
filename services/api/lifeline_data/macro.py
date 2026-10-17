"""MacroTable builders.

- `mock_macro_table()`: deterministic annual table for 1990-2026. Values are approximate real UK
  history (annual averages). Every value has `status="mock"` and `source` = the intended source id.
- `build_macro_table(observations)`: turns adapter Observations into annual MacroValues and fills
  every gap from the mock table, so the result always covers every MacroKey for 1990-2026.

Regional coverage follows the real sources. Where a source excludes a region (for example Census
NM_2072_1 and Police UK exclude Scotland), the table has no regional row. `MacroTable.get()` then
returns the UK value with note "UK average used".
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from functools import lru_cache

from lifeline_contracts.macro import MacroKey, MacroTable, MacroValue
from lifeline_contracts.observation import REGIONS, Observation, Status

FIRST_YEAR = 1990
LAST_YEAR = 2026
YEARS: tuple[int, ...] = tuple(range(FIRST_YEAR, LAST_YEAR + 1))


@dataclass(frozen=True)
class KeySpec:
    source: str
    series_id: str
    regions: tuple[str, ...]  # regions the source covers; empty = UK only
    unit: str


_ALL = REGIONS
_GB_NI_NO_SCOT = tuple(r for r in REGIONS if r != "scotland")
_E_AND_W = tuple(r for r in REGIONS if r not in ("scotland", "northern-ireland"))
_ENGLAND = tuple(r for r in REGIONS if r not in ("scotland", "northern-ireland", "wales"))

KEY_SPECS: dict[MacroKey, KeySpec] = {
    MacroKey.BANK_RATE: KeySpec("boe", "IUMBEDR", (), "percent"),
    MacroKey.MORTGAGE_2Y_FIX: KeySpec("boe", "IUMBV34", (), "percent"),
    MacroKey.MORTGAGE_5Y_FIX: KeySpec("boe", "IUMBV42", (), "percent"),
    MacroKey.CPI_INFLATION: KeySpec("ons", "D7G7", (), "percent"),
    MacroKey.HOUSE_PRICE: KeySpec("landregistry", "ukhpi-average-price", _ALL, "gbp"),
    MacroKey.HOUSE_PRICE_CHANGE: KeySpec("landregistry", "ukhpi-annual-change", _ALL, "percent"),
    MacroKey.MEDIAN_PAY: KeySpec("nomis", "NM_30_1", _ALL, "gbp"),
    MacroKey.UNEMPLOYMENT: KeySpec("nomis", "NM_17_5", _ALL, "percent"),
    MacroKey.OWNER_OCCUPIED_SHARE: KeySpec("nomis", "NM_2072_1", _E_AND_W, "percent"),
    MacroKey.GILT_10Y: KeySpec("fred", "IRLTLT01GBM156N", (), "percent"),
    MacroKey.STOCK_RETURN: KeySpec("yahoo", "^FTAS", (), "percent"),
    MacroKey.CRYPTO_RETURN: KeySpec("coingecko", "bitcoin", (), "percent"),
    MacroKey.GBP_USD: KeySpec("frankfurter", "GBPUSD", (), "rate"),
    MacroKey.ENERGY_PRICE_CHANGE: KeySpec("ons", "D7GT", (), "percent"),
    MacroKey.FUEL_PRICE_CHANGE: KeySpec("ons", "D7IO", (), "percent"),  # CPI annual rate 07.2.2 fuels
    MacroKey.RENT_CHANGE: KeySpec("ons", "PIPR", _ALL, "percent"),  # PIPR; IPHRP alias for 2006-2015
    MacroKey.BURGLARY_RATE: KeySpec("police", "burglary", _GB_NI_NO_SCOT, "per_1000_households"),
    MacroKey.FLOOD_RISK: KeySpec("environmentagency", "flood-risk", _ENGLAND, "percent"),
    MacroKey.SAVINGS_RATE: KeySpec("boe", "IUMB6VJ", (), "percent"),
    MacroKey.CARD_RATE: KeySpec("boe", "IUMCCTL", (), "percent"),
    MacroKey.ENERGY_TARIFF: KeySpec("octopus", "dual-fuel-typical-bill", (), "gbp"),
    MacroKey.MORTGAGE_SVR: KeySpec("boe", "IUMTLMV", (), "percent"),
    MacroKey.MORTGAGE_TRACKER: KeySpec("boe", "IUMBV48", (), "percent"),
}


def _series(values: list[float]) -> dict[int, float]:
    assert len(values) == len(YEARS), f"expected {len(YEARS)} values, got {len(values)}"
    return dict(zip(YEARS, values, strict=True))


# fmt: off
# 1990..2026 (37 values each). ADR 0014: levels are year-end values (December, or the latest month
# for 2026); change series are December on December. Bank Rate, mortgage fixes (1995+), CPI, energy CPI
# and UK HPI are real values recorded in October 2026. Other series are approximate history.
_BANK_RATE = _series([
    13.875, 10.375, 6.875, 5.375, 6.125, 6.375, 5.9375, 7.25, 6.25, 5.5,
    6, 4, 4, 3.75, 4.75, 4.5, 5, 5.5, 2, 0.5,
    0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.25, 0.5, 0.75, 0.75,
    0.1, 0.25, 3.5, 5.25, 4.75, 3.75, 3.75,
])
_MORTGAGE_2Y = _series([
    15.0, 11.5, 8.5, 7.0, 8.0, 7.99, 7.24, 7.13, 6.42, 6.52,
    6.03, 4.98, 4.62, 5.05, 5.07, 4.74, 5.15, 6.06, 4.77, 4.05,
    3.5, 3.22, 3.35, 2.4, 2.08, 1.9, 1.45, 1.57, 1.73, 1.42,
    1.86, 1.57, 5.43, 5.03, 4.6, 3.97, 5.13,
])
_MORTGAGE_5Y = _series([
    14.5, 11.8, 9.5, 7.8, 8.6, 8.13, 8.27, 7.4, 6.36, 6.92,
    6.2, 5.65, 5.1, 5.53, 5.37, 5, 5.49, 5.97, 5.28, 5.67,
    4.76, 4.06, 3.91, 3.34, 3.21, 2.75, 2.26, 2.07, 2.01, 1.67,
    2, 1.59, 5.05, 4.68, 4.37, 3.99, 4.98,
])
_CPI = _series([
    7.6, 7.2, 2.6, 2.4, 2.0, 3.0, 2.3, 1.7, 1.6, 1.1,
    0.8, 1.1, 1.7, 1.3, 1.7, 1.9, 3.0, 2.1, 3.1, 2.9,
    3.7, 4.2, 2.7, 2.0, 0.5, 0.2, 1.6, 3.0, 2.1, 1.3,
    0.6, 5.4, 10.5, 4.0, 2.5, 3.4, 3.1,
])
_HOUSE_PRICE_UK = _series([
    53337, 52908, 49018, 49768, 51517, 51367, 55164, 59511, 66757, 76001,
    86244, 90242, 115835, 125433, 138853, 147580, 162881, 174280, 148267, 154832,
    155405, 153880, 155534, 163942, 176561, 188767, 198513, 207568, 211621, 213521,
    228446, 245189, 263190, 256177, 263991, 268493, 272611,
])
_MEDIAN_PAY_UK = _series([
    12700, 13700, 14600, 15000, 15400, 16000, 16700, 17600, 18300, 19000,
    19800, 20800, 21600, 22300, 23000, 23700, 24300, 24900, 25600, 25900,
    26000, 26100, 26500, 27000, 27200, 27600, 28200, 28800, 29600, 30400,
    31000, 31300, 33000, 35000, 37400, 39000, 40200,
])
_UNEMPLOYMENT_UK = _series([
    6.9, 8.6, 9.8, 10.2, 9.4, 8.6, 8.1, 6.9, 6.2, 6.0,
    5.4, 5.0, 5.1, 5.0, 4.7, 4.8, 5.4, 5.3, 5.7, 7.6,
    7.9, 8.1, 8.0, 7.6, 6.2, 5.4, 4.9, 4.4, 4.1, 3.8,
    4.6, 4.5, 3.7, 4.0, 4.3, 4.8, 5.0,
])
_GILT_10Y = _series([
    10.6, 9.9, 8.6, 6.4, 8.6, 7.6, 7.5, 6.3, 4.4, 5.5,
    4.9, 5.0, 4.4, 4.8, 4.5, 4.1, 4.7, 4.5, 3.0, 4.0,
    3.4, 2.0, 1.8, 3.0, 1.8, 2.0, 1.2, 1.2, 1.3, 0.8,
    0.2, 1.0, 3.7, 3.5, 4.6, 4.5, 4.5,
])
_STOCK_RETURN = _series([
    -9.7, 20.8, 20.5, 28.4, -5.9, 23.0, 16.7, 23.6, 13.8, 24.2,
    -5.9, -13.3, -22.7, 20.9, 12.8, 22.0, 16.8, 5.3, -29.9, 30.1,
    14.5, -3.5, 12.3, 20.8, 1.2, 1.0, 16.8, 13.1, -9.5, 19.2,
    -9.8, 18.3, 0.3, 7.9, 9.5, 15.0, 6.0,
])
# Bitcoin. No liquid market before 2013: value 0.0 with a note.
_CRYPTO_START = 2013
_CRYPTO_RETURN = _series([
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 5500, -58, 35, 125, 1330, -73, 92,
    305, 60, -64, 155, 121, -5, 10,
])
_GBP_USD = _series([
    1.93, 1.87, 1.51, 1.48, 1.56, 1.55, 1.7, 1.65, 1.66, 1.62,
    1.49, 1.45, 1.61, 1.78, 1.92, 1.72, 1.96, 1.99, 1.44, 1.61,
    1.55, 1.55, 1.62, 1.65, 1.56, 1.47, 1.23, 1.35, 1.27, 1.32,
    1.37, 1.35, 1.21, 1.27, 1.25, 1.34, 1.34,
])
_ENERGY_CHANGE = _series([
    9.6, 6.2, -0.5, -1.4, 6.5, 0.8, -0.5, -5.3, -1.6, 1.4,
    -0.7, -0.2, 3.4, 2.6, 12.5, 13.7, 30.2, -7.0, 37.3, -6.1,
    1.6, 16.2, 4.6, 7.2, -2.1, -4.0, -1.1, 6.3, 8.1, -1.6,
    -8.5, 22.7, 88.7, -21.5, -6.8, 2.5, 6.0,
])
_FUEL_CHANGE = _series([
    12, 6, 4, 9, 5, 6, 6, 9, 7, 10,
    9, -5, -3, 4, 5, 9, 6, 10, -10, 20,
    12, 8, 2, -1, -10, -5, 8, 5, -2, 2,
    -5, 25, 15, -10, -4, -2, 1,
])
_RENT_CHANGE_UK = _series([
    9, 7, 5, 4, 3, 3, 4, 5, 5, 5,
    5, 5, 4, 2, 2, 2.5, 2.5, 2.8, 2.5, 0.8,
    0.3, 1.2, 1.4, 1.1, 1.4, 2.4, 2.4, 1.7, 1.0, 1.3,
    1.4, 1.2, 3.6, 6.0, 8.6, 6.0, 4.0,
])
_BURGLARY_UK = _series([
    50, 54, 58, 62, 63, 64, 60, 55, 50, 45,
    42, 39, 36, 33, 30, 29, 28, 27, 27, 26,
    25, 24, 22, 21, 19, 18, 17, 16, 15, 14,
    12, 11, 11, 10, 10, 10, 10,
])
# Instant-access household deposit rate, year-end. BoE IUMB6VJ from 2011 (real); 1990-2010 approximate
# (Bank Rate minus a margin).
_SAVINGS_RATE = _series([
    10.5, 7.5, 4.5, 3.0, 3.5, 4.0, 3.5, 4.5, 3.8, 3.0,
    3.6, 2.2, 2.2, 2.1, 2.8, 2.6, 2.9, 3.2, 1.5, 0.5,
    0.5, 1.52, 1.05, 0.81, 0.57, 0.48, 0.15, 0.21, 0.27, 0.41,
    0.06, 0.11, 1.2, 2.81, 2.59, 2.2, 2.06,
])
# Credit card rate, year-end. BoE IUMCCTL from 1995 (real); 1990-1994 approximate.
_CARD_RATE = _series([
    25.0, 24.0, 23.0, 22.5, 22.5, 23.01, 22.41, 22.77, 22.19, 19.48,
    18.9, 17.66, 15.69, 15.24, 16.05, 16.47, 15.68, 15.11, 16.05, 16.25,
    16.66, 17.29, 17.33, 18.14, 17.75, 17.93, 17.96, 17.95, 18.66, 20.77,
    20.9, 21.42, 22.48, 24.02, 24.65, 24.65, 24.71,
])
# Revert-to (standard variable) mortgage rate, year-end. BoE IUMTLMV from 1995 (real, recorded
# October 2026); 1990-1994 approximate SVR history.
_MORTGAGE_SVR = _series([
    15.4, 11.5, 9.0, 8.0, 8.4, 7.95, 7.01, 8.5, 8.0, 7.1,
    7.55, 5.67, 5.64, 5.59, 6.6, 6.35, 6.98, 7.68, 5.38, 3.97,
    3.91, 4.12, 4.35, 4.39, 4.48, 4.49, 4.23, 4.54, 4.4, 4.27,
    3.62, 3.61, 6.42, 7.92, 7.47, 6.77, 6.58,
])
# 2-year variable (tracker) rate, 75% LTV, year-end. BoE IUMBV48 from 1998 (real; the BoE reports 0
# before April 1998); 1990-1997 approximate as Bank Rate + 1.
_MORTGAGE_TRACKER = _series([
    14.88, 11.38, 7.88, 6.38, 7.13, 7.38, 6.94, 8.25, 7.06, 5.39,
    5.76, 4.15, 4.22, 3.88, 4.91, 4.61, 5.11, 5.75, 4.7, 3.31,
    2.96, 3.02, 3.44, 2.77, 1.6, 1.78, 1.48, 1.69, 1.7, 1.94,
    2.19, 1.65, 4.14, 5.69, 5.02, 4.19, 4.23,
])
# Typical dual-fuel bill in gbp, average of what a household paid in the year (Ofgem cap levels from
# 2019, including the Energy Price Guarantee of 2,500 from October 2022). Earlier years approximate.
_ENERGY_TARIFF = _series([
    560, 590, 600, 600, 640, 650, 640, 610, 590, 580,
    570, 580, 585, 600, 650, 760, 950, 960, 1250, 1150,
    1150, 1300, 1340, 1420, 1360, 1250, 1130, 1140, 1180, 1206,
    1118, 1149, 1930, 2227, 1726, 1766, 1740,
])
# fmt: on

# Regional shape parameters. Multipliers apply to the UK value; offsets are added (percentage points).
_HOUSE_MULT = {
    "north-east": 0.55, "north-west": 0.75, "yorkshire-and-the-humber": 0.73, "east-midlands": 0.85,
    "west-midlands": 0.88, "east-of-england": 1.20, "london": 1.85, "south-east": 1.35,
    "south-west": 1.15, "wales": 0.73, "scotland": 0.68, "northern-ireland": 0.63,
}
_PAY_MULT = {
    "north-east": 0.90, "north-west": 0.94, "yorkshire-and-the-humber": 0.92, "east-midlands": 0.93,
    "west-midlands": 0.94, "east-of-england": 1.00, "london": 1.30, "south-east": 1.06,
    "south-west": 0.94, "wales": 0.91, "scotland": 0.99, "northern-ireland": 0.91,
}
_UNEMP_OFFSET = {
    "north-east": 1.6, "north-west": 0.3, "yorkshire-and-the-humber": 0.5, "east-midlands": 0.0,
    "west-midlands": 0.7, "east-of-england": -0.6, "london": 0.8, "south-east": -0.8,
    "south-west": -1.0, "wales": 0.2, "scotland": 0.1, "northern-ireland": 0.0,
}
_OWNER_OFFSET = {
    "north-east": -3.0, "north-west": 1.0, "yorkshire-and-the-humber": -1.0, "east-midlands": 3.0,
    "west-midlands": 1.0, "east-of-england": 3.0, "london": -17.0, "south-east": 4.0,
    "south-west": 3.0, "wales": 4.0,
}
_RENT_OFFSET = {
    "north-east": -0.6, "north-west": 0.2, "yorkshire-and-the-humber": -0.1, "east-midlands": 0.1,
    "west-midlands": 0.2, "east-of-england": 0.0, "london": 0.5, "south-east": -0.1,
    "south-west": 0.1, "wales": 0.3, "scotland": 0.3, "northern-ireland": 0.2,
}
_BURGLARY_MULT = {
    "north-east": 1.00, "north-west": 1.15, "yorkshire-and-the-humber": 1.30, "east-midlands": 1.10,
    "west-midlands": 1.10, "east-of-england": 0.80, "london": 1.30, "south-east": 0.80,
    "south-west": 0.70, "wales": 0.70, "northern-ireland": 0.70,
}
_FLOOD_BASE = {
    "north-east": 0.6, "north-west": 0.9, "yorkshire-and-the-humber": 1.2, "east-midlands": 0.9,
    "west-midlands": 0.6, "east-of-england": 1.0, "london": 0.8, "south-east": 0.8, "south-west": 0.9,
}
_FLOOD_UK_BASE = 0.8
_FLOOD_TREND_PER_YEAR = 0.01


def _interp(points: dict[int, float], year: int) -> float:
    xs = sorted(points)
    if year <= xs[0]:
        return points[xs[0]]
    if year >= xs[-1]:
        return points[xs[-1]]
    for a, b in zip(xs, xs[1:], strict=False):
        if a <= year <= b:
            t = (year - a) / (b - a)
            return points[a] + t * (points[b] - points[a])
    raise AssertionError("unreachable")


def _house_mult(region: str, year: int) -> float:
    """London pulls away until 2016. Northern Ireland has a 2004-2008 bubble. Scotland lags."""
    base = _HOUSE_MULT[region]
    if region == "london":
        return _interp({1990: 1.45, 2016: 2.0, 2026: 1.85}, year)
    if region == "northern-ireland":
        return _interp({1990: 0.70, 2003: 0.65, 2007: 1.10, 2012: 0.60, 2026: base}, year)
    if region == "scotland":
        return _interp({1990: 0.85, 2008: 0.75, 2026: base}, year)
    if region in ("south-east", "east-of-england"):
        return _interp({1990: base - 0.05, 2016: base + 0.03, 2026: base}, year)
    return base


def _owner_uk(year: int) -> float:
    return _interp({1990: 67.5, 2003: 70.9, 2016: 63.5, 2021: 64.3, 2026: 64.5}, year)


def _regional_house_price(region: str | None, year: int) -> float:
    uk = _HOUSE_PRICE_UK[year]
    return uk if region is None else uk * _house_mult(region, year)


def _house_price_1989(region: str | None) -> float:
    # UK HPI December 1989.
    uk = 54841.0
    return uk if region is None else uk * _house_mult(region, FIRST_YEAR)


def _mock_value(key: MacroKey, year: int, region: str | None) -> tuple[float, str | None]:
    """Returns (value, note) for one cell."""
    note: str | None = None
    match key:
        case MacroKey.BANK_RATE:
            v = _BANK_RATE[year]
        case MacroKey.MORTGAGE_2Y_FIX:
            v = _MORTGAGE_2Y[year]
        case MacroKey.MORTGAGE_5Y_FIX:
            v = _MORTGAGE_5Y[year]
        case MacroKey.CPI_INFLATION:
            v = _CPI[year]
        case MacroKey.HOUSE_PRICE:
            v = round(_regional_house_price(region, year), -2)
        case MacroKey.HOUSE_PRICE_CHANGE:
            prev = _house_price_1989(region) if year == FIRST_YEAR else _regional_house_price(region, year - 1)
            v = round((_regional_house_price(region, year) / prev - 1.0) * 100.0, 1)
        case MacroKey.MEDIAN_PAY:
            v = round(_MEDIAN_PAY_UK[year] * (1.0 if region is None else _PAY_MULT[region]), -1)
        case MacroKey.UNEMPLOYMENT:
            v = round(max(1.5, _UNEMPLOYMENT_UK[year] + (0.0 if region is None else _UNEMP_OFFSET[region])), 1)
        case MacroKey.OWNER_OCCUPIED_SHARE:
            v = round(_owner_uk(year) + (0.0 if region is None else _OWNER_OFFSET[region]), 1)
        case MacroKey.GILT_10Y:
            v = _GILT_10Y[year]
        case MacroKey.STOCK_RETURN:
            v = _STOCK_RETURN[year]
        case MacroKey.CRYPTO_RETURN:
            v = float(_CRYPTO_RETURN[year])
            if year < _CRYPTO_START:
                note = "no liquid crypto market before 2013; 0 used"
        case MacroKey.GBP_USD:
            v = _GBP_USD[year]
        case MacroKey.ENERGY_PRICE_CHANGE:
            v = float(_ENERGY_CHANGE[year])
        case MacroKey.FUEL_PRICE_CHANGE:
            v = float(_FUEL_CHANGE[year])
        case MacroKey.RENT_CHANGE:
            v = round(_RENT_CHANGE_UK[year] + (0.0 if region is None else _RENT_OFFSET[region]), 1)
        case MacroKey.BURGLARY_RATE:
            v = round(_BURGLARY_UK[year] * (1.0 if region is None else _BURGLARY_MULT[region]), 1)
        case MacroKey.SAVINGS_RATE:
            v = _SAVINGS_RATE[year]
        case MacroKey.CARD_RATE:
            v = _CARD_RATE[year]
        case MacroKey.ENERGY_TARIFF:
            v = float(_ENERGY_TARIFF[year])
        case MacroKey.MORTGAGE_SVR:
            v = _MORTGAGE_SVR[year]
        case MacroKey.MORTGAGE_TRACKER:
            v = _MORTGAGE_TRACKER[year]
        case MacroKey.FLOOD_RISK:
            base = _FLOOD_UK_BASE if region is None else _FLOOD_BASE[region]
            v = round(base + _FLOOD_TREND_PER_YEAR * (year - FIRST_YEAR), 2)
    return float(v), note


def _make(
    key: MacroKey,
    year: int,
    region: str | None,
    value: float,
    status: Status,
    note: str | None,
    series_id: str | None = None,
) -> MacroValue:
    spec = KEY_SPECS[key]
    return MacroValue(
        key=key,
        year=year,
        region=region,
        value=value,
        source=spec.source,
        series_id=series_id or spec.series_id,
        status=status,
        note=note,
    )


@lru_cache(maxsize=1)
def mock_macro_table() -> MacroTable:
    """Deterministic MacroTable for 1990-2026, every MacroKey, UK plus covered regions. status='mock'."""
    values: dict[str, MacroValue] = {}
    for key in MacroKey:
        spec = KEY_SPECS[key]
        for year in YEARS:
            for region in (None, *spec.regions):
                value, note = _mock_value(key, year, region)
                values[MacroTable.make_key(key, year, region)] = _make(key, year, region, value, "mock", note)
    return MacroTable(values=values)


# --- build from observations -------------------------------------------------------------------

# (source, series_id) -> MacroKey, plus how to reduce monthly values to an annual one.
SERIES_TO_KEY: dict[tuple[str, str], MacroKey] = {
    (spec.source, spec.series_id): key for key, spec in KEY_SPECS.items()
}
# Older series that fill years the primary series does not cover. Lower priority than the primary.
SERIES_ALIASES: dict[tuple[str, str], MacroKey] = {("ons", "IPHRP"): MacroKey.RENT_CHANGE}
SERIES_TO_KEY.update(SERIES_ALIASES)

# Annual-by-nature series: published once a year, kept as published (averaged if several points).
AVERAGED_KEYS = frozenset({MacroKey.MEDIAN_PAY, MacroKey.UNEMPLOYMENT, MacroKey.OWNER_OCCUPIED_SHARE})

_STATUS_RANK: dict[str, int] = {"live": 2, "cached": 1, "mock": 0}


def _worst_status(statuses: Iterable[str]) -> Status:
    worst = min(statuses, key=lambda s: _STATUS_RANK[s])
    return worst  # type: ignore[return-value]


def _prefer_primary(group: list[Observation]) -> list[Observation]:
    """When a primary series and an alias cover the same cell: the series with the better status wins
    (live > cached > mock); on a tie the primary wins. A single series is returned unchanged."""
    primary = [o for o in group if (o.source, o.series_id) not in SERIES_ALIASES]
    alias = [o for o in group if (o.source, o.series_id) in SERIES_ALIASES]
    if not primary or not alias:
        return group
    best_p = max(_STATUS_RANK[o.status] for o in primary)
    best_a = max(_STATUS_RANK[o.status] for o in alias)
    return alias if best_a > best_p else primary


def build_macro_table(observations: Iterable[Observation], base: MacroTable | None = None) -> MacroTable:
    """Turn Observations into an annual MacroTable.

    - Observations are matched to a MacroKey by (source, series_id) using `KEY_SPECS`.
    - ADR 0014: for every key except `AVERAGED_KEYS`, the annual value is the latest observation in
      the year (December, or the latest month for the current year). Change series are y/y at source,
      so this gives December on December. `AVERAGED_KEYS` are averaged, with the worst input status
      (mock < cached < live). Years before 1990 are dropped.
    - Every cell with no observation is filled from `base` (default `mock_macro_table()`), so the
      result always covers every MacroKey for 1990-2026.
    - HOUSE_PRICE_CHANGE is derived from HOUSE_PRICE when the source gives only prices.
    """
    base = base if base is not None else mock_macro_table()
    last_year = max(LAST_YEAR, date.today().year)
    buckets: dict[tuple[MacroKey, int, str | None], list[Observation]] = defaultdict(list)
    for obs in observations:
        key = SERIES_TO_KEY.get((obs.source, obs.series_id))
        if key is None or not (FIRST_YEAR <= obs.date.year <= last_year):
            continue
        buckets[(key, obs.date.year, obs.region)].append(obs)

    values: dict[str, MacroValue] = dict(base.values)
    for (key, year, region), group in buckets.items():
        group = _prefer_primary(group)  # noqa: PLW2901
        if key in AVERAGED_KEYS:
            value = sum(o.value for o in group) / len(group)
            status = _worst_status(o.status for o in group)
        else:
            # Year-end value (latest observation in the year). Change series from the sources are
            # already y/y, so the December point is December on December.
            last = max(group, key=lambda o: o.date)
            value, status = last.value, last.status
        series_id = group[0].series_id  # the alias (e.g. IPHRP) when it supplied the value
        values[MacroTable.make_key(key, year, region)] = _make(
            key, year, region, round(value, 4), status, None, series_id
        )

    # Derive house price change from built prices where no direct change observation exists.
    for (key, year, region) in list(buckets):
        if key != MacroKey.HOUSE_PRICE:
            continue
        if (MacroKey.HOUSE_PRICE_CHANGE, year, region) in buckets:
            continue
        prev = values.get(MacroTable.make_key(MacroKey.HOUSE_PRICE, year - 1, region))
        cur = values[MacroTable.make_key(MacroKey.HOUSE_PRICE, year, region)]
        if prev is None or prev.value <= 0:
            continue
        change = round((cur.value / prev.value - 1.0) * 100.0, 2)
        status = _worst_status((cur.status, prev.status))
        values[MacroTable.make_key(MacroKey.HOUSE_PRICE_CHANGE, year, region)] = _make(
            MacroKey.HOUSE_PRICE_CHANGE, year, region, change, status, None
        )
    return MacroTable(values=values)
