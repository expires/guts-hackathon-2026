"""Engine test fixtures.

Uses W1's `lifeline_data.macro.mock_macro_table()` when it exists. Otherwise builds a small,
deterministic MacroTable (1990..2025) from lifeline_contracts.macro only.
"""

from __future__ import annotations

import math

import pytest

from lifeline_contracts.macro import MacroKey, MacroTable, MacroValue
from lifeline_contracts.observation import REGIONS

YEARS = range(1990, 2026)


def _uk(key: MacroKey, year: int) -> float:
    t = year - 1990
    match key:
        case MacroKey.BANK_RATE:
            return max(0.1, 6.0 + 4.0 * math.cos(t / 5.0) - 0.12 * t)
        case MacroKey.MORTGAGE_2Y_FIX:
            return _uk(MacroKey.BANK_RATE, year) + 1.5
        case MacroKey.MORTGAGE_5Y_FIX:
            return _uk(MacroKey.BANK_RATE, year) + 1.9 - 0.3 * math.sin(t / 3.0)
        case MacroKey.CPI_INFLATION:
            return 2.5 + 2.0 * math.sin(t / 4.0)
        case MacroKey.HOUSE_PRICE:
            return 60_000 * 1.05**t
        case MacroKey.HOUSE_PRICE_CHANGE:
            return 5.0 + 6.0 * math.sin(t / 3.5)
        case MacroKey.MEDIAN_PAY:
            return 14_000 * 1.03**t
        case MacroKey.UNEMPLOYMENT:
            return 6.0 + 2.0 * math.cos(t / 4.5)
        case MacroKey.OWNER_OCCUPIED_SHARE:
            return 64.0
        case MacroKey.STOCK_RETURN:
            return 7.0 + 15.0 * math.sin(t * 1.3)
        case _:
            return 1.0


def _regional(key: MacroKey, i: int, uk: float) -> float:
    if key == MacroKey.OWNER_OCCUPIED_SHARE:
        return 50.0 + 2.0 * i
    return uk * (0.85 + 0.03 * i)


def build_fixture_macro() -> MacroTable:
    values: dict[str, MacroValue] = {}
    keys = [
        MacroKey.BANK_RATE,
        MacroKey.MORTGAGE_2Y_FIX,
        MacroKey.MORTGAGE_5Y_FIX,
        MacroKey.CPI_INFLATION,
        MacroKey.HOUSE_PRICE,
        MacroKey.HOUSE_PRICE_CHANGE,
        MacroKey.MEDIAN_PAY,
        MacroKey.UNEMPLOYMENT,
        MacroKey.OWNER_OCCUPIED_SHARE,
        MacroKey.STOCK_RETURN,
    ]
    regional = {MacroKey.HOUSE_PRICE, MacroKey.MEDIAN_PAY, MacroKey.UNEMPLOYMENT, MacroKey.OWNER_OCCUPIED_SHARE}
    for key in keys:
        for year in YEARS:
            uk = _uk(key, year)
            values[MacroTable.make_key(key, year, None)] = MacroValue(
                key=key, year=year, region=None, value=uk, source="fixture", series_id=key.value, status="mock"
            )
            if key in regional:
                for i, region in enumerate(REGIONS):
                    values[MacroTable.make_key(key, year, region)] = MacroValue(
                        key=key,
                        year=year,
                        region=region,
                        value=_regional(key, i, uk),
                        source="fixture",
                        series_id=key.value,
                        status="mock",
                    )
    return MacroTable(values=values)


def _load_macro() -> MacroTable:
    try:
        from lifeline_data.macro import mock_macro_table  # type: ignore[import-not-found,unused-ignore]
    except ImportError:
        return build_fixture_macro()
    table = mock_macro_table()
    assert isinstance(table, MacroTable)
    return table


@pytest.fixture(scope="session")
def macro() -> MacroTable:
    return _load_macro()


@pytest.fixture(scope="session")
def fixture_macro() -> MacroTable:
    """Always the local fixture table, for tests that need known values."""
    return build_fixture_macro()


@pytest.fixture(scope="session")
def empty_macro() -> MacroTable:
    return MacroTable(values={})
