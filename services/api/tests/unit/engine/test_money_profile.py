from __future__ import annotations

from datetime import date

import pytest

from lifeline_contracts.finance import Account
from lifeline_engine import money
from lifeline_engine.money.profile import gross_from_net, personal_facts, profile
from lifeline_engine.money.text import unsupported_numbers
from lifeline_sim.concepts import concept_ids

from .finance_builders import homeowner, snapshot, tx

TODAY = date(2026, 10, 17)


def test_gross_from_net_hand_case() -> None:
    # 38,000 gross: tax (38,000 - 12,570) x 20% = 5,086; NI 25,430 x 8% = 2,034.40; net 30,879.60
    assert gross_from_net(30_879.60) == 38_000
    assert gross_from_net(0) == 0


def test_overview_balance_net_worth_and_history() -> None:
    accounts = [
        Account(id="cur", name="Current", kind="current", provider="B", balance=1000.0),
        Account(id="sav", name="Saver", kind="savings", provider="B", balance=500.0),
        Account(id="card", name="Card", kind="credit", provider="B", balance=-200.0),
    ]
    txs = [tx("2026-10-16", -100.0, "TESCO", "Tesco"), tx("2026-10-01", 300.0, "ACME SALARY")]
    ov = money.overview(snapshot(txs, accounts))
    assert ov.balance == 1500.0
    assert ov.net_worth == 1300.0
    hist = {p.date: p.value for p in ov.balance_history}
    assert hist["2026-10-17"] == 1500.0
    assert hist["2026-10-10"] == 1600.0  # before the Tesco payment
    assert hist["2026-10-03"] == 1600.0
    assert ov.balance_history[0].date == "2026-09-26"  # first point at or before the earliest transaction
    assert ov.balance_history[0].value == 1300.0  # before the salary
    assert ov.meta.label == "Sample data"


def test_net_worth_adds_property() -> None:
    ov = money.overview(homeowner())
    assert ov.net_worth == pytest.approx(1200 + 6800 - 3400 - 180000 + 240000)


def test_profile_from_homeowner() -> None:
    prof, char = profile(homeowner(), TODAY)
    assert prof.housing == "mortgage" and char.housing == "mortgage"
    assert prof.region == "yorkshire-and-the-humber" and char.town == "Leeds"
    assert prof.mortgage_balance == 180000 and char.mortgage_balance == 180000
    assert prof.deal_ends_in_months == 6  # 165 days
    assert prof.savings == 6800 and prof.other_debt == 3400
    assert prof.annual_income == gross_from_net(2500 * 12)
    assert char.annual_income == prof.annual_income
    assert char.birth_year == TODAY.year - prof.age


def test_stocks_isa_is_not_cash_savings() -> None:
    accounts = [
        Account(id="cur", name="Current", kind="current", provider="B", balance=100.0),
        Account(id="isa", name="Vanguard Stocks and Shares ISA", kind="isa", provider="V", balance=8000.0),
        Account(id="cisa", name="Cash ISA", kind="isa", provider="V", balance=2000.0),
    ]
    prof, _ = profile(snapshot([], accounts), TODAY)
    assert prof.savings == 2000


def test_personal_facts_numbers_and_concepts() -> None:
    facts = personal_facts(homeowner())
    ids = set(concept_ids())
    assert {f.id for f in facts} >= {"subscriptions_total", "debt_total", "mortgage_rate"}
    for f in facts:
        assert f.concept_id in ids
        assert unsupported_numbers(f.text, f.facts) == [], f.text
    by_id = {f.id: f for f in facts}
    assert by_id["subscriptions_total"].text == "You spend £27 a month on 2 subscriptions."
    assert by_id["mortgage_rate"].text == "Your mortgage rate is 2.09% and your fixed deal ends in 165 days."


def test_profile_uses_holder() -> None:
    from lifeline_contracts.finance import AccountHolder

    snap = homeowner().model_copy(
        update={
            "holder": AccountHolder(
                name="Priya", birth_year=1988, occupation="Marketing manager", region="london", town="Camden",
                postcode="NW1 1AA",
            )
        }
    )
    prof, char = profile(snap, TODAY)
    assert prof.age == 38 and char.birth_year == 1988
    assert prof.region == "london" and char.town == "Camden" and prof.postcode == "NW1 1AA"
    assert char.name == "Priya" and char.occupation == "Marketing manager"
