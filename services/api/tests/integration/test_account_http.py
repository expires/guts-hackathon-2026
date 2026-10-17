"""Accounts and onboarding through the HTTP API (ADR 0029)."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from lifeline_api.onboarding import health_effect
from lifeline_contracts.account import HealthSignal
from tests.integration.conftest import sign_in

MANUAL_MORTGAGE: dict[str, Any] = {
    "postcode": "LS6 1AN",
    "housing": "mortgage",
    "mortgage_balance": 180000,
    "mortgage_rate_pct": 1.89,
    "mortgage_years_left": 22,
    "deal_end": "2027-03-31",
    "property_value": 240000,
    "monthly_take_home": 2600,
    "regular_costs": [{"name": "Netflix", "monthly_amount": 12.99, "category": "subscriptions"},
                      {"name": "Council tax", "monthly_amount": 160}],
    "savings": 6000,
    "birth_year": 1986,
}


@pytest.fixture
async def live(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATA_MODE", "live")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "test-only-encryption-key-for-user-data")
    from lifeline_api.main import app

    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app), httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_me_and_logout(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "account-device-01")
    me = (await client.get("/v1/me", headers=auth)).json()
    assert me["auth_provider"] == "demo" and me["id"].startswith("demo_") and me["finance_inputs"] == []
    assert me["has_finance_data"] is False, "sample data in demo mode is not the user's own data"
    assert (await client.post("/v1/auth/logout", headers=auth)).status_code == 204
    r = await client.get("/v1/me", headers=auth)
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthorized"
    again = await sign_in(client, "account-device-01")
    assert (await client.get("/v1/me", headers=again)).json()["created_at"] == me["created_at"]


async def _make_records(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    life = await client.post("/v1/lives", json={"mode": "preset", "preset_id": "nurse-leeds", "start_year": 2006},
                             headers=auth)
    assert life.status_code == 201
    nm = (await client.get("/v1/next-move", headers=auth)).json()
    assert (await client.post("/v1/plan", json={"move_id": nm["top"]["id"]}, headers=auth)).status_code == 201
    assert (await client.post("/v1/finance/goals", json={"name": "Trip", "target": 900}, headers=auth)).status_code \
        == 201
    await client.put("/v1/finance/budgets", json={"items": [{"category": "groceries", "limit": 250}]}, headers=auth)
    assert (await client.post("/v1/finance/guesses", json={"date": "2026-10-10", "amount": 20}, headers=auth)
            ).status_code == 201
    assert (await client.put("/v1/me/health", json={"steps_per_day": 9000, "sleep_hours": 8, "measured_days": 30},
                             headers=auth)).status_code == 200


async def _is_empty(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    assert (await client.get("/v1/lives", headers=auth)).json()["lives"] == []
    assert (await client.get("/v1/plan", headers=auth)).json()["items"] == []
    assert (await client.get("/v1/finance/goals", headers=auth)).json()["items"] == []
    assert (await client.get("/v1/finance/budgets", headers=auth)).json()["items"] == []
    assert (await client.get("/v1/finance/guesses", headers=auth)).json()["items"] == []


async def test_delete_account_removes_everything(client: httpx.AsyncClient) -> None:
    from lifeline_api.main import app

    auth = await sign_in(client, "account-device-02")
    sub = (await client.get("/v1/me", headers=auth)).json()["id"]
    await _make_records(client, auth)
    store = app.state.lifeline.store
    assert await store.list_docs(sub, "") and await store.list_by_owner(sub)
    assert (await client.delete("/v1/me", headers=auth)).status_code == 204
    assert set(await store.list_docs(sub, "")) == {"revoked_before"} and await store.list_by_owner(sub) == []
    assert (await client.get("/v1/me", headers=auth)).status_code == 401, "the token is revoked"
    fresh = await sign_in(client, "account-device-02")
    await _is_empty(client, fresh)


async def test_reset_keeps_account_and_token(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "account-device-03")
    before = (await client.get("/v1/me", headers=auth)).json()
    await _make_records(client, auth)
    await client.put("/v1/finance/manual", json=MANUAL_MORTGAGE, headers=auth)
    r = await client.post("/v1/me/reset", headers=auth)
    assert r.status_code == 200 and r.json()["created_at"] == before["created_at"] and r.json()["finance_inputs"] == []
    await _is_empty(client, auth)


async def test_manual_entry_unlocks_live_mode(live: httpx.AsyncClient) -> None:
    auth = await sign_in(live, "account-device-04")
    assert (await live.get("/v1/next-move", headers=auth)).status_code == 409
    assert (await live.get("/v1/me", headers=auth)).json()["has_finance_data"] is False
    bad = {**MANUAL_MORTGAGE, "mortgage_rate_pct": None}
    r = await live.put("/v1/finance/manual", json=bad, headers=auth)
    assert r.status_code == 422 and "mortgage_rate_pct" in r.json()["error"]["message"]

    r = await live.put("/v1/finance/manual", json=MANUAL_MORTGAGE, headers=auth)
    assert r.status_code == 200, r.text
    prof = r.json()
    assert prof["meta"]["data_status"] == "live" and prof["meta"]["source"] == "manual" and "label" not in prof["meta"]
    assert prof["profile"]["housing"] == "mortgage" and prof["profile"]["mortgage_balance"] == 180000
    me = (await live.get("/v1/me", headers=auth)).json()
    assert me["has_finance_data"] is True and me["finance_inputs"] == ["manual"]
    nm = await live.get("/v1/next-move", headers=auth)
    assert nm.status_code == 200, nm.text
    subs = (await live.get("/v1/finance/subscriptions", headers=auth)).json()
    assert subs["meta"]["data_status"] == "live"
    other = await sign_in(live, "account-device-05")
    assert (await live.get("/v1/next-move", headers=other)).status_code == 409, "data is per user"


async def test_manual_entry_overrides_sample_data(client: httpx.AsyncClient) -> None:
    """Demo mode: the user's own entry replaces the sample persona, and drives the next move."""
    auth = await sign_in(client, "account-device-08")
    assert (await client.put("/v1/finance/manual", json=MANUAL_MORTGAGE, headers=auth)).status_code == 200
    nm = (await client.get("/v1/next-move", headers=auth)).json()
    assert nm["meta"]["source"] == "manual"
    moves = [nm["top"], *nm["runners_up"]]
    fix = next(m for m in moves if m["kind"] == "fix_mortgage")
    assert fix["deadline"] == "2027-03-31"
    prof = (await client.get("/v1/finance/profile", headers=auth)).json()
    assert prof["character"]["town"] == "Leeds" and prof["profile"]["age"] == 40


async def test_log_payment(live: httpx.AsyncClient) -> None:
    auth = await sign_in(live, "account-device-06")
    r = await live.post("/v1/finance/transactions", json={"amount": 3.45, "merchant": "Pret A Manger"}, headers=auth)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["transaction"]["amount"] == -3.45 and body["category"] == "eating_out"
    r = await live.post("/v1/finance/transactions",
                        json={"amount": 20, "merchant": "Tesco", "category": "groceries", "date": "2026-10-16"},
                        headers=auth)
    assert r.json()["category"] == "groceries"
    me = (await live.get("/v1/me", headers=auth)).json()
    assert me["has_finance_data"] and me["finance_inputs"] == ["app_intent"]
    r = await live.post("/v1/finance/transactions", json={"amount": 1, "merchant": "X", "date": "2099-01-01"},
                        headers=auth)
    assert r.status_code == 422


async def test_health_signal_is_stored_and_bounded(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "account-device-07")
    r = await client.put("/v1/me/health", json={"steps_per_day": 12000, "sleep_hours": 8, "measured_days": 30},
                         headers=auth)
    assert r.status_code == 200 and r.json()["health_effect"] == 8
    cases = [(100_000, 8, 30, 10), (0, 2, 30, -10), (8000, 7.5, 30, 4), (3000, 6.5, 3, -2)]
    for steps, sleep, days, want in cases:
        assert health_effect(HealthSignal(steps_per_day=steps, sleep_hours=sleep, measured_days=days)) == want


# ---------- Sign in with Apple ----------

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _jwks() -> dict[str, Any]:
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(KEY.public_key(), as_dict=True)
    return {"keys": [{**jwk, "kid": "fixture-kid", "alg": "RS256", "use": "sig"}]}


def _apple_token(key: Any = KEY, kid: str = "fixture-kid", **over: Any) -> str:
    from lifeline_api.main import app

    now = int(time.time())
    claims = {"iss": "https://appleid.apple.com", "aud": app.state.lifeline.settings.apple_bundle_id,
              "sub": "001234.apple-user.0001", "iat": now, "exp": now + 600, **over}
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": kid})


async def test_sign_in_with_apple(client: httpx.AsyncClient) -> None:
    from lifeline_api.main import app

    app.state.lifeline.apple.set_keys(_jwks())
    r = await client.post("/v1/auth/apple", json={"identity_token": _apple_token()})
    assert r.status_code == 200, r.text
    auth = {"Authorization": f"Bearer {r.json()['access_token']}"}
    me = (await client.get("/v1/me", headers=auth)).json()
    assert me["auth_provider"] == "apple" and me["id"].startswith("apple_") and "001234" not in me["id"]
    again = await client.post("/v1/auth/apple", json={"identity_token": _apple_token()})
    assert (await client.get("/v1/me", headers={"Authorization": f"Bearer {again.json()['access_token']}"})
            ).json()["id"] == me["id"], "same Apple user, same account"

    now = int(time.time())
    bad = [
        _apple_token(aud="com.someone.else"),
        _apple_token(iss="https://evil.example"),
        _apple_token(exp=now - 10, iat=now - 700),
        _apple_token(key=OTHER_KEY),
        _apple_token(kid="unknown-kid"),
        "not-a-real-token",
    ]
    for token in bad:
        r = await client.post("/v1/auth/apple", json={"identity_token": token})
        assert r.status_code == 401 and r.json()["error"]["code"] == "unauthorized", token[:20]


FIXTURES = __import__("pathlib").Path(__file__).resolve().parents[1] / "fixtures" / "data"


@pytest.mark.parametrize("name,provider", [("statement_monzo_sample.csv", "monzo"),
                                           ("statement_revolut_sample.csv", "revolut")])
async def test_statement_upload_unlocks_live_mode(live: httpx.AsyncClient, name: str, provider: str) -> None:
    auth = await sign_in(live, f"statement-{provider}-01")
    content = (FIXTURES / name).read_bytes()
    r = await live.post("/v1/finance/statements", files={"file": (name, content, "text/csv")}, headers=auth)
    assert r.status_code == 201, r.text
    res = r.json()
    assert res["provider"] == provider and res["status"] in ("done", "partial") and res["transactions"] > 0
    assert [s["name"] for s in res["stages"]] == ["read", "categorise", "find_bills", "build_profile", "next_move"]
    assert all(s["done"] for s in res["stages"][:4])
    me = (await live.get("/v1/me", headers=auth)).json()
    assert me["has_finance_data"] and me["finance_inputs"] == ["statement"]
    spending = await live.get("/v1/finance/spending", headers=auth)
    assert spending.status_code == 200 and spending.json()["meta"]["source"] == "statement"


async def test_statement_upload_rejects_bad_files(live: httpx.AsyncClient) -> None:
    auth = await sign_in(live, "statement-bad-01")
    r = await live.post("/v1/finance/statements", files={"file": ("x.csv", b"hello,world\n1,2\n", "text/csv")},
                        headers=auth)
    assert r.status_code == 201 and r.json()["status"] == "failed" and r.json()["warnings"]
    assert r.json()["stages"][0]["done"] is False
    assert (await live.get("/v1/next-move", headers=auth)).status_code == 409, "a failed import stores nothing"
    r = await live.post("/v1/finance/statements", data={"provider": "monzo"}, files={}, headers=auth)
    assert r.status_code == 422


async def test_inputs_merge_into_one_snapshot(live: httpx.AsyncClient) -> None:
    """Manual entry + statement + logged payment: one snapshot, nothing counted twice."""
    from lifeline_api.main import app

    auth = await sign_in(live, "merge-device-01")
    sub = (await live.get("/v1/me", headers=auth)).json()["id"]
    hub = app.state.lifeline.hub
    assert (await live.put("/v1/finance/manual", json=MANUAL_MORTGAGE, headers=auth)).status_code == 200
    content = (FIXTURES / "statement_monzo_sample.csv").read_bytes()
    r = await live.post("/v1/finance/statements", files={"file": ("m.csv", content, "text/csv")}, headers=auth)
    assert r.status_code == 201
    snap = await hub.get_user_snapshot(sub)
    assert snap.source == "statement" and snap.mortgage is not None and snap.holder is not None
    assert not any(t.provider_category == "user_entered" for t in snap.transactions), "synthetic rows replaced"
    assert {"acc_savings", "acc_mortgage"} <= {a.id for a in snap.accounts}
    n_bank = len(snap.transactions)

    r = await live.post("/v1/finance/transactions", json={"amount": 4, "merchant": "Greggs", "date": "2099-01-01"},
                        headers=auth)
    assert r.status_code == 422
    r = await live.post("/v1/finance/transactions", json={"amount": 4, "merchant": "Greggs"}, headers=auth)
    assert r.status_code == 201
    again = {**MANUAL_MORTGAGE, "savings": 9000}
    assert (await live.put("/v1/finance/manual", json=again, headers=auth)).status_code == 200
    snap = await hub.get_user_snapshot(sub)
    assert len(snap.transactions) == n_bank + 1, "manual entry keeps bank rows and the logged payment"
    assert next(a for a in snap.accounts if a.id == "acc_savings").balance == 9000
    me = (await live.get("/v1/me", headers=auth)).json()
    assert sorted(me["finance_inputs"]) == ["app_intent", "manual", "statement"]


async def test_demo_rewind_pass(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "store-device-01")
    life = (await client.post("/v1/lives", json={"mode": "preset", "preset_id": "nurse-leeds", "start_year": 2006,
                                                 "seed": 424242}, headers=auth)).json()
    decision = None
    for _ in range(6):
        for ev in life["pending_events"]:
            ch = next((x for x in ev["choices"] if x.get("is_default")), ev["choices"][0])
            life = (await client.post(f"/v1/lives/{life['id']}/choices",
                                      json={"event_id": ev["id"], "choice_id": ch["id"]}, headers=auth)).json()["life"]
        life = (await client.post(f"/v1/lives/{life['id']}/age", headers=auth)).json()["life"]
        decision = decision or next((h["decision_id"] for h in life["history"] if h.get("decision_id")), None)
    assert decision
    assert (await client.post(f"/v1/lives/{life['id']}/rewind", json={"decision_id": decision},
                              headers=auth)).status_code == 200
    assert (await client.post(f"/v1/lives/{life['id']}/rewind", json={"decision_id": decision},
                              headers=auth)).status_code == 402
    r = await client.post("/v1/purchases/verify", json={"product_id": "lifeline.rewindpass", "demo": True},
                          headers=auth)
    assert r.status_code == 200 and r.json() == {"product_id": "lifeline.rewindpass", "entitlement": "rewind_pass",
                                                 "active": True, "demo": True, "label": "Demo payment"}
    assert (await client.post(f"/v1/lives/{life['id']}/rewind", json={"decision_id": decision},
                              headers=auth)).status_code == 200, "the pass gives unlimited rewinds"
    r = await client.post("/v1/purchases/verify", json={"product_id": "lifeline.godmode", "demo": False}, headers=auth)
    assert r.status_code == 501, "real payments are not enabled"


async def test_finance_home_with_and_without_data(live: httpx.AsyncClient) -> None:
    auth = await sign_in(live, "home-device-01")
    r = await live.get("/v1/finance/home", headers=auth)
    assert r.status_code == 200
    assert r.json() == {"has_data": False, "connect_prompt": "Connect your money to see your next move"}
    assert (await live.put("/v1/finance/manual", json=MANUAL_MORTGAGE, headers=auth)).status_code == 200
    home = (await live.get("/v1/finance/home", headers=auth)).json()
    assert home["has_data"] is True and home["meta"]["source"] == "manual" and "connect_prompt" not in home
    assert home["net_worth"] == pytest.approx(240000 - 180000 + 6000, abs=1)
    assert "next_move" in home and len(home.get("coming_up", [])) <= 3


async def test_finance_home_demo(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "demo-presenter-01")
    home = (await client.get("/v1/finance/home", headers=auth)).json()
    assert home["has_data"] and home["meta"]["label"] == "Sample data"
    assert home["next_move"]["top"]["kind"] == "fix_mortgage"
    assert "guess" not in home["prediction"], "numbers stay hidden until the user guesses"
    assert len(home["coming_up"]) == 3 and home["coming_up_more"] is True
    day = home["prediction"]["date"]
    await client.post("/v1/finance/guesses", json={"date": day, "amount": 25}, headers=auth)
    home = (await client.get("/v1/finance/home", headers=auth)).json()
    assert home["prediction"]["guess"]["amount"] == 25


async def test_me_bank_name_from_connections(client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    from lifeline_api.main import app

    auth = await sign_in(client, "bank-name-device-01")
    assert "bank_name" not in (await client.get("/v1/me", headers=auth)).json()

    async def connections(subject: str) -> Any:
        return SimpleNamespace(providers=[SimpleNamespace(provider="trading212", connected=True),
                                          SimpleNamespace(provider="monzo", connected=True)])

    monkeypatch.setattr(app.state.lifeline.hub, "connections", connections, raising=False)
    assert (await client.get("/v1/me", headers=auth)).json()["bank_name"] == "Monzo"



async def test_statement_keeps_entered_student_fields(live: httpx.AsyncClient) -> None:
    from lifeline_api.main import app

    auth = await sign_in(live, "merge-device-02")
    sub = (await live.get("/v1/me", headers=auth)).json()["id"]
    entered = {"postcode": "LS6 1AN", "housing": "parents", "monthly_take_home": 500, "is_student": True, "age": 20,
               "student_loan_plan": "plan_5", "regular_costs": [{"name": "Phone", "monthly_amount": 15}],
               "income_sources": [{"id": "ml", "kind": "maintenance_loan", "amount": 1500, "schedule": "termly",
                                   "next_date": "2027-01-12"}]}
    assert (await live.put("/v1/finance/manual", json=entered, headers=auth)).status_code == 200
    content = (FIXTURES / "statement_monzo_sample.csv").read_bytes()
    r = await live.post("/v1/finance/statements", files={"file": ("m.csv", content, "text/csv")}, headers=auth)
    assert r.status_code == 201
    snap = await app.state.lifeline.hub.get_user_snapshot(sub)
    assert snap.age == 20 and snap.is_student is True and snap.housing == "parents"
    assert snap.student_loan_plan == "plan_5" and snap.monthly_costs == 15
    assert any(s.kind == "maintenance_loan" for s in snap.income_sources)
