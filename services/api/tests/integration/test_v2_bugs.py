"""ADR 0053 phone-test bugs on W4's side: entered-data totals with parts (2), no invented dates (3),
the profile line matches onboarding (7)."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from tests.integration.conftest import sign_in

STUDENT: dict[str, Any] = {
    "postcode": "LS6 1AN",
    "housing": "parents",
    "monthly_take_home": 600,
    "is_student": True,
    "age": 19,
    "regular_costs": [{"name": "Spotify", "monthly_amount": 11.99, "category": "subscriptions"},
                      {"name": "Phone", "monthly_amount": 15}],
    "savings": 400,
    "debts": [{"id": "d1", "kind": "bnpl", "balance": 120}, {"id": "d2", "kind": "overdraft", "balance": 250}],
    "student_loan_plan": "plan_5",
}


async def _student(client: httpx.AsyncClient, device: str, **over: Any) -> dict[str, str]:
    auth = await sign_in(client, device)
    r = await client.put("/v1/finance/manual", json={**STUDENT, **over}, headers=auth)
    assert r.status_code == 200, r.text
    return auth


async def test_totals_come_from_entered_data_with_parts(client: httpx.AsyncClient) -> None:
    auth = await _student(client, "v2-bugs-device-01")
    ov = (await client.get("/v1/finance/overview", headers=auth)).json()
    assert ov["balance"] == pytest.approx(sum(p["amount"] for p in ov["balance_parts"]))
    assert ov["net_worth"] == pytest.approx(sum(p["amount"] for p in ov["net_worth_parts"]))
    labels = [p["label"] for p in ov["net_worth_parts"]]
    assert "Current account (balance not entered)" not in labels, "no invented balance is shown"
    assert ov["balance"] == pytest.approx(400 - 250), "savings minus the overdraft you entered"
    assert ov["net_worth"] == pytest.approx(400 - 250 - 120)
    assert any("Buy now, pay later" in lbl for lbl in labels)


async def test_mortgage_parts_include_home_value(client: httpx.AsyncClient) -> None:
    auth = await _student(client, "v2-bugs-device-02", housing="mortgage", is_student=False, mortgage_balance=100000,
                          mortgage_rate_pct=4.5, mortgage_years_left=20, property_value=150000, debts=[])
    ov = (await client.get("/v1/finance/overview", headers=auth)).json()
    parts = {p["label"]: p["amount"] for p in ov["net_worth_parts"]}
    assert parts["Home value you entered"] == 150000 and parts["Mortgage (entered by you)"] == -100000
    assert ov["net_worth"] == pytest.approx(sum(parts.values()))


async def test_no_invented_payday_or_due_dates(client: httpx.AsyncClient) -> None:
    auth = await _student(client, "v2-bugs-device-03")
    pred = (await client.get("/v1/finance/prediction", headers=auth))
    if pred.status_code == 200:
        body = pred.json()
        assert "days_to_payday" not in body and all(r["feature"] != "payday" for r in body["reasons"])
    bills = (await client.get("/v1/finance/bills", headers=auth)).json()
    assert all(b["name"].lower() not in ("spotify", "phone") for b in bills["items"]), "due dates would be guesses"
    subs = (await client.get("/v1/finance/subscriptions", headers=auth)).json()
    assert all("next_payment" not in s for s in subs["items"] if s["merchant"].lower() == "spotify")
    home = (await client.get("/v1/finance/home", headers=auth)).json()
    assert all(b["name"].lower() not in ("spotify", "phone") for b in home.get("coming_up", []))


async def test_payday_shown_when_an_income_date_is_known(client: httpx.AsyncClient) -> None:
    from lifeline_api.onboarding import payday_known
    from lifeline_contracts.finance import FinanceSnapshot, IncomeSource

    snap = FinanceSnapshot(status="live", source="manual", as_of="2026-10-17", accounts=[], transactions=[])
    assert not payday_known(snap)
    dated = snap.model_copy(update={"income_sources": [IncomeSource(id="i1", kind="maintenance_loan", amount=1500,
                                                                    schedule="termly", next_date="2027-01-12")]})
    assert payday_known(dated)


async def test_profile_line_matches_onboarding(client: httpx.AsyncClient) -> None:
    auth = await _student(client, "v2-bugs-device-04")
    prof = (await client.get("/v1/finance/profile", headers=auth)).json()
    assert prof["profile"]["age"] == 19 and prof["profile"]["housing"] == "parents"
    assert prof["character"]["occupation"] == "Student" and prof["character"]["housing"] == "parents"
    assert prof["is_student"] is True
    from lifeline_api.main import app

    sub = (await client.get("/v1/me", headers=auth)).json()["id"]
    snap = await app.state.lifeline.hub.get_user_snapshot(sub)
    assert snap.is_student is True and snap.age == 19 and snap.student_loan_plan == "plan_5"
    assert snap.monthly_costs == pytest.approx(26.99) and len(snap.debts) == 2
