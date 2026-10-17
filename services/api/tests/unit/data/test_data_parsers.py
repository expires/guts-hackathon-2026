"""Parse each recorded fixture."""

from __future__ import annotations

import json
from datetime import date

import pytest

from lifeline_contracts.observation import REGIONS
from lifeline_data.adapters.boe import parse_boe_csv
from lifeline_data.adapters.landregistry import items_to_points, parse_ukhpi_items
from lifeline_data.adapters.nomis import parse_nomis_csv
from lifeline_data.adapters.ons import parse_iphrp_csv, parse_ons_json
from lifeline_data.adapters.postcodes import normalise_postcode, parse_postcode_result
from lifeline_data.base import PayloadError


def test_boe_csv(fixture_text):
    rows = parse_boe_csv(fixture_text("boe_iadb.csv"))
    codes = {r[0] for r in rows}
    assert codes == {"IUMBEDR", "IUMBV34", "IUMBV42", "IUMB6VJ", "IUMCCTL"}
    bank = {d: v for c, d, v in rows if c == "IUMBEDR"}
    assert bank[date(1990, 1, 31)] == pytest.approx(14.875)
    # 2009 cut to 0.5
    assert min(v for d, v in bank.items() if d.year == 2009) == pytest.approx(0.5)
    # blank cells before 1995 are skipped, not zero
    assert not any(c == "IUMBV34" and d.year == 1990 for c, d, _ in rows)


def test_boe_bad_header(fixture_text):
    with pytest.raises(PayloadError):
        parse_boe_csv("<html>blocked</html>")


def test_ons_json(fixture_text):
    points = parse_ons_json(fixture_text("ons_d7g7.json"))
    by_date = dict(points)
    assert by_date[date(2022, 10, 1)] == pytest.approx(11.1)  # CPI peak
    assert all(d.year in (2022, 2026) for d, _ in points)


def test_ons_falls_back_to_years():
    points = parse_ons_json({"months": [], "quarters": [], "years": [{"date": "2020", "value": "0.9"}]})
    assert points == [(date(2020, 7, 1), 0.9)]


def test_nomis_ashe(fixture_text):
    rows = parse_nomis_csv(fixture_text("nomis_ashe.csv"), month=4)
    regions = {r for _, r, _ in rows}
    assert regions == {None, *REGIONS}
    london = [v for d, r, v in rows if r == "london" and d.year == 2025]
    assert london == [46414.0]


def test_nomis_aps_dec_only(fixture_text):
    rows = parse_nomis_csv(fixture_text("nomis_aps.csv"), month=12, dec_only=True)
    assert {d.year for d, _, _ in rows} == {2024, 2025}
    assert all(0 < v < 20 for _, _, v in rows)


def test_nomis_census_england_and_wales_only(fixture_text):
    rows = parse_nomis_csv(fixture_text("nomis_census.csv"), month=3)
    regions = {r for _, r, _ in rows}
    assert "scotland" not in regions and "northern-ireland" not in regions
    assert None in regions  # England and Wales total
    assert dict((r, v) for _, r, v in rows)["london"] == pytest.approx(45.2)


def test_landregistry_items(fixture_text):
    items, nxt = parse_ukhpi_items(fixture_text("landregistry_london.json"))
    assert nxt is None
    prices = items_to_points(items, "averagePrice")
    changes = items_to_points(items, "percentageAnnualChange")
    assert prices[0][0] == date(2024, 1, 1)
    assert all(400_000 < v < 700_000 for _, v in prices)
    assert all(-20 < v < 20 for _, v in changes)


def test_postcodes(fixture_text):
    assert parse_postcode_result(fixture_text("postcodes_sw1a1aa.json")) == {
        "region": "london",
        "town": "Westminster",
        "postcode": "SW1A 1AA",
    }
    scot = parse_postcode_result(fixture_text("postcodes_eh11yz.json"))
    assert scot is not None and scot["region"] == "scotland"
    with pytest.raises(PayloadError):  # 200 with no result is a bad payload (V3 F4)
        parse_postcode_result(json.loads(fixture_text("postcodes_404.json")))
    with pytest.raises(PayloadError):
        parse_postcode_result({"status": 200})


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("sw1a1aa", "SW1A 1AA"), (" EH1  1YZ ", "EH1 1YZ"), ("M1 1AE", "M1 1AE"), ("nope", None), ("12345", None)],
)
def test_normalise_postcode(raw, expected):
    assert normalise_postcode(raw) == expected


def test_iphrp_csv(fixture_text):
    rows = parse_iphrp_csv(fixture_text("ons_iphrp.csv"))
    dec08 = {r: v for d, r, v in rows if d == date(2008, 12, 1)}
    assert dec08["yorkshire-and-the-humber"] == pytest.approx(1.9)
    assert dec08["london"] == pytest.approx(4.3)
    assert "scotland" not in dec08  # blank in 2008: skipped, not zero
