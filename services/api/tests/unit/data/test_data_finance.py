"""Finance fixture personas (ADR 0016, ADR 0018). Offline, deterministic."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from lifeline_contracts.finance import FinanceSnapshot
from lifeline_data.finance import (
    DEMO_DEVICE_ID,
    DEMO_SUBJECT,
    FIXTURE_AS_OF,
    PERSONA_IDS,
    demo_subject,
    fixture_snapshot,
    persona_for_subject,
    persona_id_for_subject,
)
from lifeline_data.hub import DataHub


def test_demo_subject_matches_api_rule():
    from lifeline_api.auth import demo_subject as api_demo_subject

    assert api_demo_subject(DEMO_DEVICE_ID) == DEMO_SUBJECT == demo_subject(DEMO_DEVICE_ID)
    assert persona_id_for_subject(DEMO_SUBJECT) == "homeowner-leeds"


def test_demo_persona_next_move_facts():
    snap = fixture_snapshot(DEMO_SUBJECT)
    assert snap.status == "mock" and snap.source == "fixtures" and snap.persona == "homeowner-leeds"
    assert snap.as_of == "2026-10-17"
    m = snap.mortgage
    assert m is not None and m.balance == 180_000 and m.rate_type == "fixed"
    assert m.fixed_until == "2027-03-31"
    assert (date.fromisoformat(m.fixed_until) - FIXTURE_AS_OF).days == 165
    assert 230_000 <= m.property_value <= 250_000
    assert snap.energy is not None and snap.energy.fixed_until is None
    info = persona_for_subject(DEMO_SUBJECT)
    assert info.town == "Leeds" and info.region == "yorkshire-and-the-humber" and info.gross_salary == 38_000
    assert len(info.unused_subscriptions) == 2
    card = next(a for a in snap.accounts if a.kind == "credit")
    assert card.balance < -3_000


def test_demo_salary_and_netflix_rise():
    snap = fixture_snapshot(DEMO_SUBJECT)
    salary = [t for t in snap.transactions if "SALARY" in t.description]
    assert 11 <= len(salary) <= 13 and all(2_300 < t.amount < 2_600 for t in salary)
    netflix = [t.amount for t in snap.transactions if t.merchant == "Netflix"]
    assert netflix[0] == -12.99 and netflix[-1] == -13.99
    assert abs(13.99 / 12.99 - 1) < 0.10  # stays inside the "amount within 10%" detection rule
    for name in persona_for_subject(DEMO_SUBJECT).unused_subscriptions:
        assert any(t.merchant == name for t in snap.transactions)


def test_every_persona_valid_and_twelve_months():
    assert len(PERSONA_IDS) >= 4
    for pid in PERSONA_IDS:
        snap = fixture_snapshot(f"persona:{pid}")
        FinanceSnapshot.model_validate(snap.model_dump())
        dates = sorted(t.date for t in snap.transactions)
        assert dates[-1] <= "2026-10-17" and dates[0] >= "2025-10-18"
        months = {d[:7] for d in dates}
        assert len(months) >= 12
        assert len({t.id for t in snap.transactions}) == len(snap.transactions)
        account_ids = {a.id for a in snap.accounts}
        assert all(t.account_id in account_ids for t in snap.transactions)
        assert snap.energy is not None
        assert any(t.provider_category == "PURCHASE" for t in snap.transactions)


def test_deterministic_and_copy():
    a = fixture_snapshot("user_abc")
    b = fixture_snapshot("user_abc")
    assert a == b and a is not b
    a.transactions.clear()
    assert fixture_snapshot("user_abc").transactions


def test_hash_mapping_spreads_subjects():
    seen = {persona_id_for_subject(f"user_{i}") for i in range(200)}
    assert seen == set(PERSONA_IDS)


def test_spend_responds_to_weekday():
    snap = fixture_snapshot("persona:homeowner-leeds")
    by_wd: dict[int, float] = defaultdict(float)
    for t in snap.transactions:
        if t.provider_category == "PURCHASE" and t.amount < 0:
            by_wd[date.fromisoformat(t.date).weekday()] += -t.amount
    assert by_wd[5] > by_wd[0]  # Saturday above Monday


async def test_hub_finance_snapshot_offline(settings):
    hub = DataHub(settings, env={})
    snap = await hub.finance_snapshot(DEMO_SUBJECT)
    assert snap.persona == "homeowner-leeds" and snap.mortgage is not None
    await hub.aclose()
