from __future__ import annotations

import pytest

from lifeline_engine.tools import facts_table as ft


def test_official_values_2026_27() -> None:
    # Values checked on gov.uk on 2026-10-17 (see the URL on each entry).
    expected = {
        "isa_allowance": 20_000,
        "lisa_allowance": 4_000,
        "lisa_bonus_max": 1_000,
        "jisa_allowance": 9_000,
        "personal_allowance": 12_570,
        "personal_allowance_income_limit": 100_000,
        "basic_rate_band": 37_700,
        "higher_rate_band_top": 125_140,
        "basic_rate": 20,
        "higher_rate": 40,
        "additional_rate": 45,
        "scot_starter_band_top": 3_967,
        "scot_basic_band_top": 16_956,
        "scot_intermediate_band_top": 31_092,
        "scot_higher_band_top": 62_430,
        "scot_advanced_band_top": 125_140,
        "scot_top_rate": 48,
        "ni_primary_threshold": 12_570,
        "ni_upper_earnings_limit": 50_270,
        "ni_main_rate": 8,
        "ni_upper_rate": 2,
        "student_loan_plan1_threshold": 26_900,
        "student_loan_plan2_threshold": 29_385,
        "student_loan_plan4_threshold": 33_795,
        "student_loan_plan5_threshold": 25_000,
        "postgraduate_loan_threshold": 21_000,
        "student_loan_rate": 9,
        "postgraduate_loan_rate": 6,
    }
    for key, value in expected.items():
        assert ft.get(key).value == value, key


def test_every_entry_has_govuk_url_date_and_unique_id() -> None:
    ids = [f.id for f in ft.FACTS]
    assert len(ids) == len(set(ids))
    for f in ft.FACTS:
        assert f.url.startswith("https://www.gov.uk/")
        assert f.as_of == "2026-10-17" and f.tax_year == "2026/27"
        assert f.id.startswith("rule.")
        assert f.unit in ("gbp", "gbp_per_month", "gbp_per_year", "percent", "months", "years", "count", "date_year")


def test_consistency_between_tables() -> None:
    # Higher rate starts at personal allowance + basic band = £50,270 = NI upper earnings limit.
    assert ft.get("personal_allowance").value + ft.get("basic_rate_band").value == ft.get(
        "ni_upper_earnings_limit"
    ).value
    assert ft.get("ni_primary_threshold").value == ft.get("personal_allowance").value


def test_lookup() -> None:
    assert {f.topic for f in ft.lookup(topic="student_loan")} == {"student_loan"}
    assert [f.id for f in ft.lookup(ids=["isa_allowance", "rule.jisa_allowance", "nope"])] == [
        "rule.isa_allowance",
        "rule.jisa_allowance",
    ]
    assert len(ft.lookup()) == len(ft.FACTS)
    with pytest.raises(KeyError):
        ft.get("nope")
