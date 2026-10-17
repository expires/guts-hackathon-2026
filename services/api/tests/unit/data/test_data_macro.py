"""MacroTable builders: mock coverage, realistic history, build from observations, Scotland fallback."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from lifeline_contracts.macro import MacroKey, MacroTable
from lifeline_contracts.observation import REGIONS, Observation
from lifeline_data.macro import KEY_SPECS, build_macro_table, mock_macro_table

YEARS = list(range(1990, 2027))


def _obs(source, series_id, day, value, region=None, status="live", unit="percent"):
    return Observation(
        series_id=series_id, source=source, date=day, value=value, unit=unit, region=region,
        fetched_at=datetime.now(UTC), status=status,
    )


def test_mock_covers_every_key_and_year():
    t = mock_macro_table()
    for key in MacroKey:
        assert t.years(key) == YEARS, key
        for year in YEARS:
            v = t.get(key, year)
            assert v.status == "mock"
            assert v.source == KEY_SPECS[key].source


def test_mock_regional_rows_follow_source_coverage():
    t = mock_macro_table()
    for key, spec in KEY_SPECS.items():
        for region in REGIONS:
            present = MacroTable.make_key(key, 2010, region) in t.values
            assert present == (region in spec.regions), (key, region)
    # Every regional key has all 12 regions when the source covers the UK.
    for key in (MacroKey.HOUSE_PRICE, MacroKey.MEDIAN_PAY, MacroKey.UNEMPLOYMENT, MacroKey.RENT_CHANGE):
        assert set(KEY_SPECS[key].regions) == set(REGIONS)


def test_mock_is_deterministic():
    assert mock_macro_table() == mock_macro_table()
    mock_macro_table.cache_clear()
    assert mock_macro_table().values == mock_macro_table().values


def test_mock_history_is_realistic():
    t = mock_macro_table()
    v = t.value
    assert v(MacroKey.BANK_RATE, 2021) < 0.5 and v(MacroKey.BANK_RATE, 2023) > 4
    assert 9 <= v(MacroKey.CPI_INFLATION, 2022) <= 11
    assert v(MacroKey.HOUSE_PRICE_CHANGE, 2008) < -10  # ADR 0014: December on December
    assert v(MacroKey.HOUSE_PRICE_CHANGE, 2008, "london") < -10
    assert v(MacroKey.BANK_RATE, 2008) == 2.0 and v(MacroKey.BANK_RATE, 2009) == 0.5
    assert v(MacroKey.HOUSE_PRICE, 2008) < v(MacroKey.HOUSE_PRICE, 2007)
    assert v(MacroKey.STOCK_RETURN, 2008) < -20
    assert v(MacroKey.ENERGY_PRICE_CHANGE, 2022) > 40
    assert v(MacroKey.HOUSE_PRICE, 2020, "london") > 2 * v(MacroKey.HOUSE_PRICE, 2020, "north-east")
    assert v(MacroKey.MEDIAN_PAY, 2020, "london") > v(MacroKey.MEDIAN_PAY, 2020, "wales")
    assert v(MacroKey.OWNER_OCCUPIED_SHARE, 2021, "london") < 50
    assert t.get(MacroKey.CRYPTO_RETURN, 2000).note is not None


def test_scotland_fallback_note():
    t = mock_macro_table()
    # Census tenure and Police UK exclude Scotland.
    for key in (MacroKey.OWNER_OCCUPIED_SHARE, MacroKey.BURGLARY_RATE, MacroKey.FLOOD_RISK):
        got = t.get(key, 2015, "scotland")
        assert got.note == "UK average used"
        assert got.value == t.value(key, 2015)
    # Land Registry covers Scotland: no note.
    assert t.get(MacroKey.HOUSE_PRICE, 2015, "scotland").note is None


def test_build_uses_year_end_for_levels_and_changes():
    obs = [
        _obs("boe", "IUMBEDR", date(2008, m, 1), v, status=s)
        for m, v, s in [(1, 5.5, "live"), (6, 5.0, "live"), (12, 2.0, "cached")]
    ]
    obs += [_obs("ons", "D7G7", date(2022, m, 1), v) for m, v in [(10, 11.1), (12, 10.5)]]
    obs += [_obs("ons", "D7G7", date(2026, m, 1), v) for m, v in [(7, 3.8), (8, 3.1)]]  # partial year
    t = build_macro_table(obs)
    got = t.get(MacroKey.BANK_RATE, 2008)
    assert got.value == 2.0 and got.status == "cached"
    assert t.value(MacroKey.CPI_INFLATION, 2022) == pytest.approx(10.5)
    assert t.value(MacroKey.CPI_INFLATION, 2026) == pytest.approx(3.1)
    assert t.get(MacroKey.BANK_RATE, 2009).status == "mock"  # gap filled from mock


def test_build_averages_annual_series():
    points = [(3, 7.0, "live"), (12, 8.0, "cached")]
    obs = [_obs("nomis", "NM_17_5", date(2010, m, 1), v, status=s) for m, v, s in points]
    got = build_macro_table(obs).get(MacroKey.UNEMPLOYMENT, 2010)
    assert got.value == pytest.approx(7.5) and got.status == "cached"


def test_build_regional_and_scotland_fallback():
    obs = [
        _obs("nomis", "NM_2072_1", date(2021, 3, 1), 45.2, "london"),
        _obs("nomis", "NM_2072_1", date(2021, 3, 1), 61.6, None),
    ]
    t = build_macro_table(obs)
    assert t.value(MacroKey.OWNER_OCCUPIED_SHARE, 2021, "london") == pytest.approx(45.2)
    scot = t.get(MacroKey.OWNER_OCCUPIED_SHARE, 2021, "scotland")
    assert scot.value == pytest.approx(61.6) and scot.note == "UK average used" and scot.status == "live"


def test_build_derives_house_price_change():
    obs = [
        _obs("landregistry", "ukhpi-average-price", date(2019, 6, 1), 200_000, "wales", unit="gbp"),
        _obs("landregistry", "ukhpi-average-price", date(2020, 6, 1), 210_000, "wales", unit="gbp"),
    ]
    t = build_macro_table(obs)
    assert t.value(MacroKey.HOUSE_PRICE_CHANGE, 2020, "wales") == pytest.approx(5.0)
    assert t.get(MacroKey.HOUSE_PRICE_CHANGE, 2020, "wales").status == "live"


def test_build_ignores_unknown_series_and_out_of_range_years():
    obs = [
        _obs("boe", "IUMBV37", date(2010, 1, 1), 3.0),  # 3-year fix: not mapped
        _obs("ons", "D7G7", date(1989, 1, 1), 5.2),
    ]
    t = build_macro_table(obs)
    assert t.years(MacroKey.CPI_INFLATION) == YEARS
    assert all(v.status == "mock" for v in t.values.values())


def test_contract_series_ids():
    assert KEY_SPECS[MacroKey.MORTGAGE_5Y_FIX].series_id == "IUMBV42"
    assert KEY_SPECS[MacroKey.MORTGAGE_2Y_FIX].series_id == "IUMBV34"
    assert KEY_SPECS[MacroKey.BANK_RATE].series_id == "IUMBEDR"
    assert KEY_SPECS[MacroKey.CPI_INFLATION].series_id == "D7G7"


def test_adr_0018_mock_keys_realistic():
    v = mock_macro_table().value
    assert all(0.0 <= v(MacroKey.SAVINGS_RATE, y) <= 0.6 for y in range(2014, 2022))
    assert 2.5 <= v(MacroKey.SAVINGS_RATE, 2023) <= 4.0
    assert all(15 <= v(MacroKey.CARD_RATE, y) <= 26 for y in range(1990, 2027))
    assert all(500 <= v(MacroKey.ENERGY_TARIFF, y) <= 1500 for y in range(1990, 2021))
    assert v(MacroKey.ENERGY_TARIFF, 2023) > 1.5 * v(MacroKey.ENERGY_TARIFF, 2020)
