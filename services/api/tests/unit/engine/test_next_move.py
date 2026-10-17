from __future__ import annotations

from datetime import date

import pytest

from lifeline_contracts.finance import Account, MortgageDetails
from lifeline_contracts.macro import MacroTable
from lifeline_contracts.next_move import NextMoveResponse
from lifeline_engine.finance import monthly_payment
from lifeline_engine.money.text import unsupported_numbers
from lifeline_engine.next_move import (
    MOVE_TAG,
    build_context,
    candidates,
    confidence_label,
    mortgage_backtest,
    mortgage_paths,
    next_move,
    option_policy,
)
from lifeline_sim.concepts import concept_ids

from .finance_builders import homeowner, monthly, snapshot, tx

TODAY = date(2026, 10, 17)


def _all_moves(r: NextMoveResponse) -> list:  # type: ignore[type-arg]
    return [r.top, *r.runners_up]


@pytest.mark.parametrize(
    ("conf", "text"),
    [
        (0.7, "7 in 10 twins in similar past periods did better"),
        (1.0, "All twins in similar past periods did better"),
        (0.96, "More than 9 in 10 twins in similar past periods did better"),
        (0.0, "No twins in similar past periods did better"),
        (0.03, "Fewer than 1 in 10 twins in similar past periods did better"),
    ],
)
def test_confidence_label_never_10_in_10(conf: float, text: str) -> None:
    assert confidence_label(conf) == text
    assert "10 in 10" not in confidence_label(conf) and "0 in 10" not in confidence_label(conf)


def test_mortgage_paths_hand_case(fixture_macro: MacroTable) -> None:
    s = 2000
    p = mortgage_paths(fixture_macro, s, q2=5.0, q5=4.8, keep_now=6.0, tracker_now=5.0, horizon=5)
    r2 = [fixture_macro.value("mortgage_2y_fix", s + t) for t in range(5)]
    bank = [fixture_macro.value("bank_rate", s + t) for t in range(5)]
    assert p["fix_5y"] == [4.8] * 5
    assert p["fix_2y"][:2] == [5.0, 5.0]
    assert p["fix_2y"][2] == pytest.approx(max(0.0, 5.0 + r2[2] - r2[0]))
    assert p["fix_2y"][4] == pytest.approx(max(0.0, 5.0 + r2[4] - r2[0]))
    assert p["tracker"][3] == pytest.approx(max(0.0, 5.0 + bank[3] - bank[0]))  # no tracker series: Bank Rate + 1
    assert p["keep"][1] == pytest.approx(max(0.0, 6.0 + bank[1] - bank[0]))


def test_demo_homeowner_top_move(macro: MacroTable) -> None:
    r = next_move(homeowner(), macro, TODAY)
    assert r.top.kind == "fix_mortgage"
    assert r.top.days_left == 165 and r.top.deadline == "2027-03-31"
    assert r.top.headline == "Your deal ends in 165 days"
    assert r.top.testable and r.top.test_period is not None
    assert r.top.test_period.label == "2021-2023 rate shock (stress test)"
    assert r.backtest is not None and r.backtest.n > 0
    assert len(r.runners_up) <= 2
    assert r.meta.label == "Sample data"


def test_every_move_is_well_formed(macro: MacroTable) -> None:
    ids = set(concept_ids())
    for snap in (homeowner(), _renter(), _overspender()):
        r = next_move(snap, macro, TODAY)
        moves = _all_moves(r)
        assert len({m.id for m in moves}) == len(moves)
        for m in moves:
            assert len(m.evidence) == 3
            for e in m.evidence:
                assert unsupported_numbers(e.text, e.facts) == [], e.text
            assert m.concept_id in ids
            assert 0 <= m.confidence <= 1
            assert "10 in 10" not in m.confidence_label
            assert m.impact_per_year > 0
            assert 1 <= len(m.options) <= 4
            assert sum(o.is_recommended for o in m.options) == 1
            assert m.sources


def test_ranking_order(macro: MacroTable) -> None:
    ctx = build_context(homeowner(), macro, TODAY)
    ranked = candidates(ctx)
    scores = [c.score for c in ranked]
    assert scores == sorted(scores, reverse=True)
    for c in ranked:
        m = c.move
        assert c.score == pytest.approx((m.impact_per_year + 0.5 * min(0, m.worst_case_per_year)) * m.confidence,
                                        rel=1e-3, abs=0.05)


def test_deterministic(macro: MacroTable) -> None:
    a = next_move(homeowner(), macro, TODAY, seed=3)
    b = next_move(homeowner(), macro, TODAY, seed=3)
    assert a == b


def test_option_policy_same_tag_key_for_every_option(macro: MacroTable) -> None:
    for snap in (homeowner(), _renter(), _overspender()):
        for m in _all_moves(next_move(snap, macro, TODAY)):
            keys = [set(option_policy(m, o.id)) for o in m.options]
            assert all(k == keys[0] for k in keys)
            assert MOVE_TAG[m.kind] in keys[0]
            assert {option_policy(m, o.id)[MOVE_TAG[m.kind]] for o in m.options} == {o.id for o in m.options}
    top = next_move(homeowner(), macro, TODAY).top
    assert option_policy(top, "keep") == {"mortgage_deal_end": "keep", "__deal_end_year": "2021"}
    with pytest.raises(ValueError):
        option_policy(top, "nope")


def test_debt_option_capped_at_debt(macro: MacroTable) -> None:
    snap = homeowner()
    accounts = [a if a.kind != "savings" else a.model_copy(update={"balance": 50_000.0}) for a in snap.accounts]
    snap = snap.model_copy(update={"accounts": accounts})
    debt = next(c.move for c in candidates(build_context(snap, macro, TODAY)) if c.move.kind == "pay_off_debt")
    assert debt.action == "Pay off £3,400 of card debt from savings"
    assert debt.evidence[0].facts["amount"] == 3400


def test_no_mortgage_move_when_deal_far_away(macro: MacroTable) -> None:
    snap = homeowner()
    assert snap.mortgage is not None
    far = snap.model_copy(update={"mortgage": snap.mortgage.model_copy(update={"fixed_until": "2029-01-01"})})
    kinds = {c.move.kind for c in candidates(build_context(far, macro, TODAY))}
    assert "fix_mortgage" not in kinds and "remortgage" not in kinds


def test_fallback_when_nothing_to_do(macro: MacroTable) -> None:
    accounts = [Account(id="cur", name="Current", kind="current", provider="B", balance=30_000.0)]
    snap = snapshot(monthly("2025-11-28", 11, 3000.0, "ACME SALARY"), accounts)
    r = next_move(snap, macro, TODAY)
    assert r.top.impact_per_year == 0 and not r.top.testable
    assert len(r.top.evidence) == 3 and r.runners_up == []


def test_mortgage_backtest(macro: MacroTable) -> None:
    bt = mortgage_backtest(macro, 2026)
    assert bt.n >= 20
    assert 0 <= bt.hit_rate <= 1 and 0 <= bt.baseline_hit_rate <= 1
    assert bt.baseline.startswith("Always fix for 2 years")


def test_payment_reference() -> None:
    assert round(monthly_payment(180_000, 4.98, 25), 2) == 1050.17


# ---------- hand-made personas ----------


def _renter():  # type: ignore[no-untyped-def]
    txs = [
        *monthly("2025-11-28", 11, 2800.0, "ACME SALARY"),
        *monthly("2025-11-01", 12, -1650.0, "J SMITH LETTINGS RENT"),
        *monthly("2025-11-30", 11, 12.0, "INTEREST PAID", None, "sav"),
    ]
    accounts = [
        Account(id="cur", name="Current", kind="current", provider="B", balance=2000.0),
        Account(id="sav", name="Saver", kind="savings", provider="B", balance=14000.0),
    ]
    return snapshot(txs, accounts, persona="renter-london")


def _overspender():  # type: ignore[no-untyped-def]
    txs = [
        *monthly("2025-11-28", 11, 1800.0, "ACME SALARY"),
        *monthly("2025-11-01", 12, -925.0, "CLIFTON LETTINGS RENT"),
        *monthly("2025-11-20", 11, -140.0, "INTEREST CHARGED", None, "card"),
        *[tx(f"2026-{m:02d}-1{d}", -150.0, "ASOS", "ASOS") for m in range(1, 10) for d in range(5)],
    ]
    accounts = [
        Account(id="cur", name="Current", kind="current", provider="B", balance=-300.0),
        Account(id="card", name="Card", kind="credit", provider="V", balance=-4800.0),
    ]
    return snapshot(txs, accounts, persona="overspender-bristol")


def test_overspender_gets_debt_move(macro: MacroTable) -> None:
    kinds = [m.kind for m in _all_moves(next_move(_overspender(), macro, TODAY))]
    assert "pay_off_debt" in kinds


def test_renter_gets_savings_move(macro: MacroTable) -> None:
    r = next_move(_renter(), macro, TODAY)
    assert r.top.kind == "move_savings"
    assert r.top.test_period is not None and (r.top.test_period.start, r.top.test_period.end) == (2009, 2011)
    assert r.backtest is None


def test_remortgage_when_on_variable(macro: MacroTable) -> None:
    snap = homeowner()
    m = MortgageDetails(balance=150000, rate_pct=7.5, rate_type="variable", years_left=20, property_value=250000,
                        monthly_payment=1200)
    kinds = {c.move.kind for c in candidates(build_context(snap.model_copy(update={"mortgage": m}), macro, TODAY))}
    assert "remortgage" in kinds


def test_fixture_personas_from_data_layer(macro: MacroTable) -> None:
    finance = pytest.importorskip("lifeline_data.finance")
    for pid in ("homeowner-leeds", "renter-saver-london", "subscription-creep-manchester", "overspender-bristol"):
        snap = finance.fixture_snapshot(f"persona:{pid}")
        r = next_move(snap, macro, date.fromisoformat(snap.as_of))
        for m in _all_moves(r):
            for e in m.evidence:
                assert unsupported_numbers(e.text, e.facts) == []
    demo = next_move(finance.fixture_snapshot("persona:homeowner-leeds"), macro, TODAY)
    assert demo.top.kind == "fix_mortgage" and demo.top.days_left == 165


def test_period_spans_merge() -> None:
    from lifeline_engine.next_move import period_spans, spans_text

    assert period_spans([2007, 2005, 2006, 2017, 2018], 5) == [(2005, 2011), (2017, 2022)]
    assert period_spans([2001, 2010], 1) == [(2001, 2001), (2010, 2010)]
    text, facts = spans_text([2017, 2005], 3)
    assert text == "2005-2007, 2017-2019"
    assert unsupported_numbers(text, facts) == []


def test_stress_period_in_worst_case_and_evidence(macro: MacroTable) -> None:
    from lifeline_engine.next_move import STRESS

    for snap in (homeowner(), _renter(), _overspender()):
        for m in _all_moves(next_move(snap, macro, TODAY)):
            stress = STRESS.get(m.kind)
            if stress is None:
                continue
            assert m.test_period is not None and m.test_period.start == stress.start
            assert m.test_period.label.endswith("(stress test)")
            assert "similar past" in m.evidence[1].text
            assert m.evidence[2].facts["stress_start"] == stress.start
            stressed = m.evidence[2].facts["stress"]
            sign = -1 if "more." in m.evidence[2].text.split(",")[0] or " less" in m.evidence[2].text else 1
            if m.kind != "build_emergency_fund":
                assert m.worst_case_per_year <= sign * stressed + 0.5
            assert m.worst_case_per_year <= m.impact_per_year + 1e-6


def test_choose_by_regret_hand_case() -> None:
    from lifeline_engine.next_move import choose_by_regret

    # Two matched periods, two options. A: +100, +100 (mean 100). B: +300, -50 (mean 125).
    # Without stress: regret(A) = max(300-100, 0) = 200 -> 100 - 100 = 0; regret(B) = max(0, 150) = 150
    # -> 125 - 75 = 50. B wins.
    best, scores = choose_by_regret(("A", "B"), {"A": [100.0, 100.0], "B": [300.0, -50.0]})
    assert best == "B"
    assert scores == {"A": 0.0, "B": 50.0}
    # Stress period: A +80, B -400. regret(B) = 480 -> 125 - 240 = -115; regret(A) still 200 -> 0. A wins.
    best, scores = choose_by_regret(("A", "B"), {"A": [100.0, 100.0], "B": [300.0, -50.0]}, {"A": 80.0, "B": -400.0})
    assert best == "A"
    assert scores == {"A": 0.0, "B": -115.0}


@pytest.mark.parametrize(
    ("share", "text"),
    [
        (0.6, "In 6 of 10 similar cases this was the best choice"),
        (1.0, "In all similar cases this was the best choice"),
        (0.97, "In more than 9 of 10 similar cases this was the best choice"),
        (0.0, "In no similar cases this was the best choice"),
        (0.02, "In fewer than 1 of 10 similar cases this was the best choice"),
    ],
)
def test_best_choice_label(share: float, text: str) -> None:
    from lifeline_engine.wording import best_choice_label

    assert best_choice_label(share) == text


def test_mortgage_confidence_is_best_choice_share(macro: MacroTable) -> None:
    top = next_move(homeowner(), macro, TODAY).top
    assert top.confidence_label.endswith("similar cases this was the best choice")
    assert 0 < top.confidence <= 1


def test_best_constant_rule() -> None:
    from lifeline_engine.next_move import best_constant_rule

    assert best_constant_rule(["tracker", "fix_2y", "tracker", "fix_5y"], ("fix_5y", "fix_2y", "tracker")) == (
        "tracker",
        0.5,
    )
    assert best_constant_rule(["fix_2y", "fix_5y"], ("fix_5y", "fix_2y")) == ("fix_5y", 0.5)  # tie: option order


def test_backtest_reports_best_constant_rule(macro: MacroTable) -> None:
    bt = mortgage_backtest(macro, 2026)
    assert "Best constant rule: always" in bt.method
    assert bt.baseline.startswith("Always fix for 2 years (best constant rule: always")


def test_scenario_covers_whole_test_period(macro: MacroTable) -> None:
    from lifeline_engine.next_move import scenario_years

    top = next_move(homeowner(), macro, TODAY).top
    assert top.test_period is not None and (top.test_period.start, top.test_period.end) == (2021, 2023)
    # The sim runs events from start_year + 1 to end_year, and the deal ends in the first event year.
    assert scenario_years(top) == (2020, 2023)
    assert option_policy(top, top.options[0].id)["__deal_end_year"] == "2021"
    e3 = top.evidence[2]
    assert "Test it replays" not in e3.text.split(".")[0]
    assert e3.text.endswith("Test it replays your whole life in those years, so its totals can differ.")
    assert "Fix for 5 years" in e3.text or "Fix for 2 years" in e3.text or "Take a tracker" in e3.text
    assert unsupported_numbers(e3.text, e3.facts) == []


def test_mortgage_stress_window_is_test_period(fixture_macro: MacroTable) -> None:
    from lifeline_engine.decision import mortgage_interest
    from lifeline_engine.next_move import rank_mortgage

    r = rank_mortgage(fixture_macro, [2000], [180_000], 180_000, 25, 5.0, 4.8, 6.0, 5.0, stress_start=2010,
                      stress_horizon=3)
    paths = mortgage_paths(fixture_macro, 2010, 5.0, 4.8, 6.0, 5.0, 3)
    keep = mortgage_interest(180_000, 25, paths["keep"])
    assert r.stress["fix_5y"] == pytest.approx((keep - mortgage_interest(180_000, 25, paths["fix_5y"])) / 3)


def test_action_equals_recommended_label_all_personas(macro: MacroTable) -> None:
    snaps = [homeowner(), _renter(), _overspender()]
    finance = None
    try:
        from lifeline_data import finance as finance_mod

        finance = finance_mod
    except ImportError:
        pass
    if finance is not None:
        snaps += [
            finance.fixture_snapshot(f"persona:{p}")
            for p in ("homeowner-leeds", "renter-saver-london", "subscription-creep-manchester", "overspender-bristol")
        ]
    for snap in snaps:
        for m in _all_moves(next_move(snap, macro, date.fromisoformat(snap.as_of))):
            rec = [o for o in m.options if o.is_recommended]
            assert len(rec) == 1 and rec[0].label == m.action, (m.id, m.action, rec[0].label)


def test_budget_headline_number_in_facts(macro: MacroTable) -> None:
    finance = pytest.importorskip("lifeline_data.finance")
    for p in ("homeowner-leeds", "subscription-creep-manchester"):
        snap = finance.fixture_snapshot(f"persona:{p}")
        for m in _all_moves(next_move(snap, macro, TODAY)):
            facts = {k: v for e in m.evidence for k, v in e.facts.items()}
            assert unsupported_numbers(m.headline, facts) == [], m.headline


def test_todays_rates_comparison_hand_case() -> None:
    from lifeline_engine.next_move import todays_rates_comparison

    # £180,000 over 25 years: 5.13% -> £1,065.94/month, 4.98% -> £1,050.17/month. Gap 15.77 x 12 = £189.
    text, facts = todays_rates_comparison(180_000, 25, 5.13, 4.98, 4.23)
    p2 = monthly_payment(180_000, 5.13, 25) * 12
    p5 = monthly_payment(180_000, 4.98, 25) * 12
    pt = monthly_payment(180_000, 4.23, 25) * 12
    assert round(monthly_payment(180_000, 4.98, 25), 2) == 1050.17
    assert facts["gap_5y_vs_2y"] == round(p2 - p5) == 189
    assert facts["gap_tracker_vs_2y"] == round(p2 - pt)
    assert text.startswith("At today's rates on £180,000 over 25 years, a 5-year fix (4.98%) costs £189 a year less")
    assert unsupported_numbers(text, facts) == []


def test_mortgage_evidence_has_todays_comparison(macro: MacroTable) -> None:
    top = next_move(homeowner(), macro, TODAY).top
    assert len(top.evidence) == 3
    assert "At today's rates on £180,000 over 23 years" in top.evidence[0].text
    assert top.evidence[0].source is not None and top.evidence[0].source.series_id


@pytest.mark.parametrize(("ratio", "weight"), [(0.25, 0.5), (0.30, 0.5), (0.375, 1.0), (0.45, 1.5), (0.5, 1.5)])
def test_regret_weight_hand_cases(ratio: float, weight: float) -> None:
    from lifeline_engine.next_move import regret_weight

    # Linear between (0.30, 0.5) and (0.45, 1.5): 0.375 is halfway, so 1.0.
    assert regret_weight(ratio) == pytest.approx(weight)
    assert regret_weight(None) == 1.5


def test_affordability_hand_case() -> None:
    from lifeline_engine.next_move import affordability

    # £180,000, 25 years at 6.58% + 3.0 = 9.58%: payment from finance.monthly_payment.
    snap = snapshot(monthly("2026-01-28", 9, 2500.0, "ACME SALARY"))
    a = affordability(180_000, 25, 6.58, snap)
    pay = monthly_payment(180_000, 9.58, 25)
    assert a.stressed_payment == pytest.approx(pay)
    assert a.ratio == pytest.approx(pay / 2500.0)
    assert a.facts["stressed_payment"] == round(pay)
    assert unsupported_numbers(a.text, a.facts) == []


def test_choose_by_regret_weight() -> None:
    from lifeline_engine.next_move import choose_by_regret

    m = {"A": [100.0, 100.0], "B": [300.0, -50.0]}
    # weight 0.5: A 0 vs B 50 -> B. weight 1.5: A 100 - 300 = -200, B 125 - 225 = -100 -> B. weight 0.1: B.
    assert choose_by_regret(("A", "B"), m, None, 0.5)[0] == "B"
    assert choose_by_regret(("A", "B"), m, {"A": 80.0, "B": -400.0}, 1.5)[1] == {"A": -200.0, "B": -595.0}
