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
        "student_loan_rate_plan1": 9,
        "student_loan_rate_plan5": 9,
        "lisa_min_open_age": 18,
        "lisa_bonus_rate": 25,
        "lisa_withdrawal_charge": 25,
        "lisa_first_home_price_limit": 450_000,
        "maintenance_instalments_england": 3,
        "council_tax_all_students_discount": 100,
        "railcard_16_25_price_1y": 35,
        "railcard_16_25_discount": 33.33,
        "saas_payment_months_term_time": 9,
        "saas_payment_months_full_year": 12,
    }
    for key, value in expected.items():
        assert ft.get(key).value == value, key


def test_every_entry_has_govuk_url_date_and_unique_id() -> None:
    ids = [f.id for f in ft.FACTS]
    assert len(ids) == len(set(ids))
    for f in ft.FACTS:
        assert f.url.startswith("https://www.gov.uk/") or f.url in ft.OFFICIAL_NON_GOVUK
        assert f.checked in ("2026-10-17", "2026-10-18")
        assert f.tax_year == ("2024/25" if f.id == "rule.hesa_non_uk_share_2024_25" else "2026/27")
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


def test_every_entry_has_checked_date_and_tool_exposes_it() -> None:
    import re

    from lifeline_engine.tools.wrappers import FactsTableInput, tool_facts_table

    for f in ft.FACTS:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", f.checked), f.id
    r = tool_facts_table(FactsTableInput(topic="travel"))
    entries = {e["id"]: e for e in r.result["entries"]}
    rail = ft.get("railcard_16_25_price_1y")
    assert entries[rail.id] == {"id": rail.id, "url": rail.url, "checked": rail.checked}
    assert not any(".entries." in f.id for f in r.facts)  # urls and dates are not turned into facts


def test_adr_0058_official_domain_and_checked_date() -> None:
    import re
    from urllib.parse import urlparse

    assert not hasattr(ft, "AS_OF")  # no global "checked" claim: each entry has its own date
    for f in ft.FACTS:
        u = urlparse(f.url)
        assert u.scheme == "https" and u.netloc in ft.OFFICIAL_DOMAINS, f.id
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", f.checked), f.id
    assert "rule.maintenance_payments_scotland" not in ft.BY_ID
    assert ft.get("saas_payment_months_term_time").unit == "months"
    assert ft.get("lisa_withdrawal_charge").url == "https://www.gov.uk/lifetime-isa/withdrawing-money-from-your-lifetime-isa"
    assert ft.get("council_tax_single_adult_discount").url == "https://www.gov.uk/council-tax/who-has-to-pay"


def test_hesa_non_uk_share() -> None:
    f = ft.get("hesa_non_uk_share_2024_25")
    assert f.value == round(685_565 / 2_863_180 * 100, 1) == 23.9
    assert f.unit == "percent" and f.checked == "2026-10-18"
    assert f.url == "https://www.hesa.ac.uk/data-and-analysis/sb273/figure-7"
    assert "www.hesa.ac.uk" in ft.OFFICIAL_DOMAINS


def test_learn_course_facts_2026_10_18() -> None:
    # ADR 0068: each value checked against its own official page on 2026-10-18.
    expected = {
        "boe_inflation_target": (2, "www.bankofengland.co.uk"),
        "boe_bank_rate": (3.75, "www.bankofengland.co.uk"),
        "fscs_deposit_limit": (120_000, "www.fscs.org.uk"),
        "ssp_weekly": (123.25, "www.gov.uk"),
        "national_living_wage": (12.71, "www.gov.uk"),
        "minimum_wage_18_20": (10.85, "www.gov.uk"),
        "redundancy_weekly_pay_cap": (751, "www.gov.uk"),
        "redundancy_pay_max": (22_530, "www.gov.uk"),
        "state_pension_full_weekly": (241.30, "www.gov.uk"),
        "state_pension_qualifying_years": (35, "www.gov.uk"),
        "auto_enrolment_total_min": (8, "www.gov.uk"),
        "auto_enrolment_employer_min": (3, "www.gov.uk"),
        "uc_standard_single_25_plus": (424.90, "www.gov.uk"),
        "uc_standard_single_under_25": (338.58, "www.gov.uk"),
        "tax_free_childcare_max": (2_000, "www.gov.uk"),
        "free_childcare_hours_england": (30, "www.gov.uk"),
        "ofgem_price_cap_typical_bill": (1_723, "www.ofgem.gov.uk"),
        "maintenance_loan_max_home_england": (9_118, "www.gov.uk"),
        "maintenance_loan_max_away_england": (10_830, "www.gov.uk"),
        "maintenance_loan_max_london_england": (14_135, "www.gov.uk"),
        "student_loan_interest_plan5": (4.1, "www.gov.uk"),
        "student_loan_interest_plan2_max": (6, "www.gov.uk"),
        "inheritance_tax_threshold": (325_000, "www.gov.uk"),
        "inheritance_tax_rate": (40, "www.gov.uk"),
        "sdlt_first_time_buyer_threshold": (300_000, "www.gov.uk"),
        "sdlt_first_time_buyer_max_price": (500_000, "www.gov.uk"),
    }
    from urllib.parse import urlparse

    for key, (value, host) in expected.items():
        f = ft.get(key)
        assert f.value == value, key
        assert urlparse(f.url).netloc == host and host in ft.OFFICIAL_DOMAINS, key
        assert f.checked == "2026-10-18", key
        assert f.topic in ft.TOPICS, key
    assert ft.get("auto_enrolment_employer_min").value < ft.get("auto_enrolment_total_min").value
    assert ft.get("sdlt_first_time_buyer_threshold").value < ft.get("sdlt_first_time_buyer_max_price").value
    assert (ft.get("maintenance_loan_max_home_england").value < ft.get("maintenance_loan_max_away_england").value
            < ft.get("maintenance_loan_max_london_england").value)


def test_consumer_facts_2026_10_18() -> None:
    expected = {
        "distance_cancel_days": (14, "www.gov.uk"),
        "fca_overdraft_simple_rate_year": (2020, "www.fca.org.uk"),
        "fca_bnpl_regulated_year": (2026, "www.fca.org.uk"),
        "fscs_general_insurance_share": (90, "www.fscs.org.uk"),
    }
    from urllib.parse import urlparse

    for key, (value, host) in expected.items():
        f = ft.get(key)
        assert f.value == value and f.checked == "2026-10-18", key
        assert urlparse(f.url).netloc == host and host in ft.OFFICIAL_DOMAINS and f.topic in ft.TOPICS, key
