from __future__ import annotations

import pytest

from lifeline_contracts.domain import CharacterSpec, Decision, DecisionProfile
from lifeline_contracts.macro import MacroTable
from lifeline_engine import api
from lifeline_engine.decision import (
    DISCLAIMER,
    Scenario,
    choose_question,
    evidence_sentence,
    mortgage_interest,
    mortgage_rate_path,
    rank_options,
)

MORTGAGE = DecisionProfile(
    age=34,
    region="london",
    annual_income=40_000,
    savings=8_000,
    housing="mortgage",
    mortgage_balance=200_000,
    mortgage_years_left=25,
    deal_ends_in_months=2,
)
RENTER = DecisionProfile(age=24, region="wales", annual_income=22_000, savings=3_000, other_debt=2_000, housing="rent")


def test_mortgage_interest_one_year_6pct() -> None:
    # 100,000 over 1 year at 6%: payment 8,606.64 a month, interest 12 * 8,606.64 - 100,000 = 3,279.72.
    assert mortgage_interest(100_000, 1, [6.0]) == pytest.approx(3_279.72, abs=0.01)


def test_mortgage_interest_constant_rate_matches_single_annuity() -> None:
    # Re-pricing each year at the same rate must equal one 25-year annuity.
    from lifeline_engine.finance import monthly_payment, remaining_balance

    expected = 5 * 12 * monthly_payment(180_000, 4.98, 25) - (180_000 - remaining_balance(180_000, 4.98, 25, 60))
    assert mortgage_interest(180_000, 25, [4.98] * 5) == pytest.approx(expected, rel=1e-9)


def test_mortgage_interest_zero_rate() -> None:
    assert mortgage_interest(120_000, 25, [0.0] * 5) == pytest.approx(0.0, abs=1e-6)


def test_fix_paths_hold_rate(fixture_macro: MacroTable) -> None:
    p2 = mortgage_rate_path(fixture_macro, "fix_2y", 2000)
    p5 = mortgage_rate_path(fixture_macro, "fix_5y", 2000)
    assert p2[0] == p2[1] and p2[2] == p2[3]
    assert len(set(p5)) == 1


def test_rank_prefers_cheaper_option(fixture_macro: MacroTable) -> None:
    r = rank_options("mortgage", fixture_macro, ["fix_2y", "fix_5y"], [2000], [Scenario(180_000, 25)])
    cost2 = mortgage_interest(180_000, 25, mortgage_rate_path(fixture_macro, "fix_2y", 2000))
    cost5 = mortgage_interest(180_000, 25, mortgage_rate_path(fixture_macro, "fix_5y", 2000))
    assert r.options[0] == ("fix_2y" if cost2 < cost5 else "fix_5y")


def test_choose_question() -> None:
    assert choose_question(MORTGAGE) == "mortgage"
    assert choose_question(RENTER) == "savings"


def test_evidence_sentence() -> None:
    assert evidence_sentence(0.7) == "7 in 10 twins in similar past periods did better."


@pytest.mark.parametrize("profile", [MORTGAGE, RENTER])
def test_decide_valid_and_deterministic(profile: DecisionProfile, macro: MacroTable) -> None:
    a = api.decide(profile, macro, 2025)
    b = api.decide(profile, macro, 2025)
    assert a == b
    Decision.model_validate(a.model_dump())
    assert a.disclaimer == DISCLAIMER
    assert a.evidence.twins_count > 0
    assert a.evidence.periods
    assert "—" not in a.headline + a.evidence.sentence + " ".join(a.reasons)
    # Matched periods end before the as-of year: no look-ahead.
    assert all(int(p.split("-")[1]) < 2025 for p in a.evidence.periods)


def test_decide_on_empty_table(empty_macro: MacroTable) -> None:
    d = api.decide(MORTGAGE, empty_macro, 2025)
    assert d.evidence.periods == []
    assert d.evidence.success_rate == 0.0


def test_api_random_character(macro: MacroTable) -> None:
    assert isinstance(api.random_character(42, macro), CharacterSpec)


def test_evidence_sentence_caps() -> None:
    assert evidence_sentence(1.0) == "All twins in similar past periods did better."
    assert evidence_sentence(0.97) == "More than 9 in 10 twins in similar past periods did better."
    assert "10 in 10" not in evidence_sentence(0.999)


def test_three_year_fix_option(fixture_macro: MacroTable) -> None:
    from lifeline_engine.decision import fix_3y_rate, options_for

    assert "fix_3y" in options_for("mortgage")
    r2 = fixture_macro.value("mortgage_2y_fix", 2005)
    r5 = fixture_macro.value("mortgage_5y_fix", 2005)
    assert fix_3y_rate(fixture_macro, 2005) == pytest.approx(r2 + (r5 - r2) / 3)
    path = mortgage_rate_path(fixture_macro, "fix_3y", 2005, horizon=5)
    assert path[:3] == [fix_3y_rate(fixture_macro, 2005)] * 3
    assert path[3:] == [fix_3y_rate(fixture_macro, 2008)] * 2


def test_debt_option_capped_at_debt(fixture_macro: MacroTable) -> None:
    from lifeline_engine.decision import outcome

    # £10,000 of savings and £2,000 of debt: only £2,000 earns the debt rate, £8,000 stays in savings.
    capped = outcome("savings", fixture_macro, "pay_debt", 2000, Scenario(10_000, 0, debt=2_000))
    save = outcome("savings", fixture_macro, "save", 2000, Scenario(10_000, 0))
    all_debt = outcome("savings", fixture_macro, "pay_debt", 2000, Scenario(2_000, 0, debt=2_000))
    assert capped == pytest.approx(0.2 * all_debt + 0.8 * save)
