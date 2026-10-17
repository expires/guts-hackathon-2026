"""Finance fixture personas (ADR 0016, ADR 0018). Offline, deterministic."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

import pytest

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
    assert snap.region == "yorkshire-and-the-humber" and snap.postcode == "LS6 1AN"
    h = snap.holder
    assert h is not None and h.name == "Priya Shah" and h.birth_year == 1992 and h.occupation == "Nurse"
    assert h.town == "Leeds" and h.postcode == "LS6 1AN" and h.region == "yorkshire-and-the-humber"
    assert FIXTURE_AS_OF.year - h.birth_year == 34
    m = snap.mortgage
    assert m is not None and m.balance == 180_000 and m.rate_type == "fixed" and m.years_left == 25
    assert m.fixed_until == "2027-03-31" and m.rate_pct == 4.42  # BoE IUMBV34, April 2025
    assert (date.fromisoformat(m.fixed_until) - FIXTURE_AS_OF).days == 165
    r, n = m.rate_pct / 100 / 12, 12 * m.years_left
    assert m.monthly_payment == pytest.approx(m.balance * r / (1 - (1 + r) ** -n), abs=0.01)
    assert 230_000 <= m.property_value <= 250_000
    assert snap.energy is not None and snap.energy.fixed_until is None
    info = persona_for_subject(DEMO_SUBJECT)
    assert info.housing == "mortgage" and 35_000 <= info.gross_salary <= 38_000
    assert not any(a.kind == "credit" for a in snap.accounts)


def test_demo_salary_and_two_subscriptions():
    snap = fixture_snapshot(DEMO_SUBJECT)
    salary = [t for t in snap.transactions if "SALARY" in t.description]
    assert 11 <= len(salary) <= 13 and all(2_200 < t.amount < 2_400 for t in salary)
    mortgage = [t.amount for t in snap.transactions if t.merchant == "Nationwide"]
    assert len(mortgage) == 12 and set(mortgage) == {-992.34}
    subs = defaultdict(list)
    for t in snap.transactions:
        if t.merchant in ("Netflix", "PureGym"):
            subs[t.merchant].append(t.amount)
    assert set(subs) == {"Netflix", "PureGym"}
    assert all(len(set(v)) == 1 for v in subs.values())  # no price rise
    assert round(-sum(v[-1] for v in subs.values())) == 38
    other = {"Spotify", "Disney+", "Amazon Prime", "iCloud"}
    assert not any(t.merchant in other for t in snap.transactions)


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


def test_all_presenter_devices_get_the_demo_persona():
    from lifeline_api.auth import demo_subject as api_demo_subject
    from lifeline_data.finance import DEMO_DEVICE_IDS

    assert tuple(f"demo-presenter-0{n}" for n in range(1, 6)) == DEMO_DEVICE_IDS
    for device in DEMO_DEVICE_IDS:
        subject = api_demo_subject(device)
        assert persona_id_for_subject(subject) == "homeowner-leeds"
        snap = fixture_snapshot(subject)
        assert snap.mortgage is not None and snap.mortgage.fixed_until == "2027-03-31"
        assert snap.holder is not None and snap.holder.name == "Priya Shah"
    assert persona_id_for_subject(api_demo_subject("demo-presenter-06")) in PERSONA_IDS  # not pinned
