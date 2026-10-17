"""Fixtures for sim tests.

Uses `lifeline_data.macro.mock_macro_table()` (W1) when it exists. Otherwise builds a local
table with approximate UK history, enough to exercise every template.
"""

from __future__ import annotations

import pytest

from lifeline_contracts.macro import MacroKey, MacroTable, MacroValue

# Approximate UK annual values. Local fixture only: shape matters, not exact numbers.
_BANK = {
    2005: 4.7,
    2006: 4.6,
    2007: 5.5,
    2008: 4.7,
    2009: 0.6,
    2016: 0.4,
    2020: 0.2,
    2021: 0.1,
    2022: 1.5,
    2023: 4.7,
    2024: 5.1,
    2025: 4.3,
    2026: 3.8,
}
_CPI = {
    2005: 2.1,
    2006: 2.3,
    2007: 2.3,
    2008: 3.6,
    2009: 2.2,
    2010: 3.3,
    2011: 4.5,
    2012: 2.8,
    2020: 0.9,
    2021: 2.6,
    2022: 9.1,
    2023: 7.3,
    2024: 2.5,
    2025: 3.4,
    2026: 2.6,
}
_STOCK = {2007: 7.0, 2008: -28.0, 2009: 27.0, 2011: -2.0, 2015: 1.0, 2018: -9.0, 2020: -11.0, 2022: 4.0}
_HPC = {2007: 6.0, 2008: -9.0, 2009: -3.0, 2010: 2.0, 2022: 9.0, 2023: -1.5}
_UNEMP = {2008: 5.7, 2009: 7.6, 2010: 7.9, 2011: 8.1, 2012: 8.0, 2013: 7.6, 2020: 4.6, 2021: 4.5}
_ENERGY = {2008: 25.0, 2022: 60.0, 2023: 20.0}
_FUEL = {2008: 14.0, 2011: 15.0, 2022: 25.0}
_CRYPTO = {
    2013: 5000.0,
    2014: -58.0,
    2015: 35.0,
    2016: 125.0,
    2017: 1300.0,
    2018: -73.0,
    2019: 95.0,
    2020: 300.0,
    2021: 60.0,
    2022: -64.0,
    2023: 155.0,
    2024: 120.0,
}

REGIONS = ("yorkshire-and-the-humber", "london", "scotland", "north-west", "west-midlands", "south-west")
_PRICE_MULT = {
    "london": 1.9,
    "yorkshire-and-the-humber": 0.7,
    "scotland": 0.7,
    "north-west": 0.75,
    "west-midlands": 0.8,
    "south-west": 1.1,
}


def _series(d: dict[int, float], default: float, y: int) -> float:
    return d.get(y, default)


def _uk_values(y: int) -> dict[MacroKey, float]:
    bank = _series(_BANK, 0.5 if 2009 <= y <= 2021 else 4.5, y)
    return {
        MacroKey.BANK_RATE: bank,
        MacroKey.MORTGAGE_2Y_FIX: bank + 1.6,
        MacroKey.MORTGAGE_5Y_FIX: bank + 1.9,
        MacroKey.CPI_INFLATION: _series(_CPI, 2.0, y),
        MacroKey.HOUSE_PRICE: 70_000 * 1.055 ** (y - 1995),
        MacroKey.HOUSE_PRICE_CHANGE: _series(_HPC, 4.5, y),
        MacroKey.MEDIAN_PAY: 18_000 * 1.03 ** (y - 1995),
        MacroKey.UNEMPLOYMENT: _series(_UNEMP, 5.0, y),
        MacroKey.OWNER_OCCUPIED_SHARE: 64.0,
        MacroKey.GILT_10Y: max(bank + 0.8, 1.0),
        MacroKey.STOCK_RETURN: _series(_STOCK, 7.0, y),
        MacroKey.GBP_USD: 1.5,
        MacroKey.ENERGY_PRICE_CHANGE: _series(_ENERGY, 3.0, y),
        MacroKey.FUEL_PRICE_CHANGE: _series(_FUEL, 2.0, y),
        MacroKey.RENT_CHANGE: 2.5 if y < 2022 else 6.0,
        MacroKey.BURGLARY_RATE: 12.0 if y < 2012 else 7.0,
        MacroKey.FLOOD_RISK: 1.0,
    }


def local_macro_table() -> MacroTable:
    values: dict[str, MacroValue] = {}

    def put(key: MacroKey, year: int, region: str | None, value: float) -> None:
        mv = MacroValue(
            key=key, year=year, region=region, value=value, source="fixture", series_id=key.value, status="mock"
        )
        values[MacroTable.make_key(key, year, region)] = mv

    for y in range(1990, 2027):
        for key, v in _uk_values(y).items():
            put(key, y, None, v)
        if y >= 2013:
            put(MacroKey.CRYPTO_RETURN, y, None, _series(_CRYPTO, 30.0, y))
        for r in REGIONS:
            if r == "scotland":
                continue  # Scotland falls back to UK values, like the real data
            m = _PRICE_MULT[r]
            put(MacroKey.HOUSE_PRICE, y, r, 70_000 * m * 1.055 ** (y - 1995))
            put(MacroKey.MEDIAN_PAY, y, r, 18_000 * (0.9 + 0.2 * (m > 1)) * 1.03 ** (y - 1995))
            put(MacroKey.UNEMPLOYMENT, y, r, _series(_UNEMP, 5.0, y) + (0.8 if m < 1 else -0.3))
    return MacroTable(values=values)


def _load_table() -> MacroTable:
    try:
        from lifeline_data.macro import mock_macro_table  # type: ignore[import-not-found,unused-ignore]
    except ImportError:
        return local_macro_table()
    table: MacroTable = mock_macro_table()
    return table


_TABLE: MacroTable | None = None


@pytest.fixture(scope="session")
def macro() -> MacroTable:
    global _TABLE
    if _TABLE is None:
        _TABLE = _load_table()
    return _TABLE


@pytest.fixture(scope="session")
def local_macro() -> MacroTable:
    return local_macro_table()
