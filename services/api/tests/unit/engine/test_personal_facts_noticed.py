"""ADR 0069 "3 things Penny noticed": 3 facts when the data allows, signed cash, plurals. Pure, no network."""

from __future__ import annotations

import pytest

from lifeline_contracts.finance import Account, FinanceSnapshot
from lifeline_engine.money.profile import PERSONAL_FACTS_SHOWN, personal_facts
from lifeline_engine.money.text import unsupported_numbers
from lifeline_sim.concepts import concept_ids

from .finance_builders import homeowner

STUDENTS = ("scholarship", "scottish", "commuter", "loan_england", "working", "mature", "international",
                "final_year", "rich", "graduate")


def _samples() -> list[FinanceSnapshot]:
    statements = pytest.importorskip("lifeline_data.statements")
    return [statements.load_sample(sid) for sid in STUDENTS]


def test_three_facts_for_every_sample_and_numbers_trace() -> None:
    ids = set(concept_ids())
    for snap in [homeowner(), *_samples()]:
        facts = personal_facts(snap)
        assert len(facts) >= PERSONAL_FACTS_SHOWN, (snap.persona, [f.text for f in facts])
        for f in facts:
            assert unsupported_numbers(f.text, f.facts) == [], f.text
            assert f.concept_id in ids
            assert "1 subscriptions" not in f.text and " 1 days" not in f.text and "—" not in f.text
        assert len({f.id for f in facts}) == len(facts)


def test_overdrawn_cash_is_negative_and_covers_zero_months() -> None:
    working = next(s for s in _samples() if s.persona == "working")
    cover = next(f for f in personal_facts(working) if f.id == "emergency_months")
    cash = sum(a.balance for a in working.accounts if a.kind == "current")
    assert cash < 0
    assert cover.facts["liquid"] == round(cash) < 0
    assert cover.facts["months"] == 0.0
    assert "in your overdraft" in cover.text and "covers 0 months" in cover.text


def test_one_subscription_is_singular() -> None:
    scholarship = next(s for s in _samples() if s.persona == "scholarship")
    sub = next(f for f in personal_facts(scholarship) if f.id == "subscriptions_total")
    assert sub.text.endswith("on 1 subscription.")


def test_positive_cash_keeps_old_wording() -> None:
    snap = homeowner()
    snap = snap.model_copy(update={"accounts": [*snap.accounts, Account(id="x", name="Saver", kind="savings",
                                                                        provider="B", balance=500.0)]})
    cover = [f for f in personal_facts(snap) if f.id == "emergency_months"]
    for f in cover:
        assert f.text.startswith("Your cash and savings cover") and f.facts["liquid"] >= 0
