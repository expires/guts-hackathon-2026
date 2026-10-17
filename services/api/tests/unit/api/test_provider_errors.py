"""ProviderError -> HTTP mapping and the connection routes' validation (offline hub)."""

from __future__ import annotations

import httpx
import pytest

from lifeline_api.errors import PROVIDER_STATUS, provider_error_to_api
from lifeline_data.providers._http import ProviderError

SECRET = "leaky-secret-value"  # noqa: S105


@pytest.mark.parametrize(
    "code,status,api_code",
    [
        ("auth", 400, "provider_auth"),
        ("rate_limited", 429, "rate_limited"),
        ("timeout", 504, "timeout"),
        ("unavailable", 502, "unavailable"),
        ("bad_data", 502, "bad_data"),
        ("not_configured", 503, "not_configured"),
        ("offline", 503, "offline"),
        ("bad_state", 400, "bad_state"),
        ("not_connected", 409, "not_connected"),
    ],
)
def test_mapping(code: str, status: int, api_code: str) -> None:
    err = provider_error_to_api(ProviderError(code, f"raw text with {SECRET}", source="monzo"))
    assert (err.status, err.code, err.source) == (status, api_code, "monzo")
    assert SECRET not in err.message and "HTTP" not in err.message
    assert "—" not in err.message and "–" not in err.message  # no dashes used as pauses in copy


def test_auth_is_not_the_apps_own_401() -> None:
    assert PROVIDER_STATUS["auth"][0] == 400 and PROVIDER_STATUS["auth"][1] != "unauthorized"


def test_rate_limited_carries_retry_after() -> None:
    err = provider_error_to_api(ProviderError("rate_limited", "x", source="trading212", retry_after=12.2))
    assert err.headers == {"Retry-After": "13"}
    assert provider_error_to_api(ProviderError("rate_limited", "x")).headers == {"Retry-After": "30"}


def test_unknown_code_is_a_bad_gateway() -> None:
    err = provider_error_to_api(ProviderError("weird", "x"))
    assert err.status == 502


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_ENV", "test")
    from lifeline_api.main import app

    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app), httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _auth(client: httpx.AsyncClient) -> dict[str, str]:
    r = await client.post("/v1/auth/demo", json={"device_id": "provider-errors-1"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


NEW_ROUTES = [
    ("GET", "/v1/connections", None),
    ("POST", "/v1/connections/trading212", {"api_key": "k", "api_secret": "s"}),
    ("POST", "/v1/connections/monzo/token", {"access_token": "t"}),
    ("POST", "/v1/connections/monzo/sync", None),
    ("DELETE", "/v1/connections/monzo", None),
    ("GET", "/v1/finance/investments", None),
    ("GET", "/v1/finance/habits", None),
    ("GET", "/v1/finance/isa/periods", None),
    ("POST", "/v1/finance/isa/backtest", {"strategies": [{"weights": {"cash": 1.0}}]}),
    ("POST", "/v1/finance/isa/scenarios", {"strategy": {"weights": {"cash": 1.0}}}),
    ("GET", "/v1/bank/summary?session=abc", None),
]


@pytest.mark.parametrize("method,path,body", NEW_ROUTES)
async def test_new_routes_need_auth(client: httpx.AsyncClient, method: str, path: str, body: object) -> None:
    r = await client.request(method, path, json=body)
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthorized"


async def test_connection_validation(client: httpx.AsyncClient) -> None:
    auth = await _auth(client)
    for path, body in (
        ("/v1/connections/trading212", {"api_key": "", "api_secret": "s"}),
        ("/v1/connections/trading212", {"api_key": "k"}),
        ("/v1/connections/monzo/token", {}),
        ("/v1/connections/monzo/token", {"access_token": "t", "extra": 1}),
    ):
        r = await client.post(path, json=body, headers=auth)
        assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error", path
    assert (await client.delete("/v1/connections/paypal", headers=auth)).status_code == 422


async def test_offline_hub_refuses_connect_with_503_and_no_echo(client: httpx.AsyncClient) -> None:
    auth = await _auth(client)
    r = await client.post("/v1/connections/trading212", json={"api_key": SECRET, "api_secret": SECRET}, headers=auth)
    assert r.status_code == 503 and r.json()["error"]["code"] == "offline"
    assert set(r.json()["error"]) == {"code", "message", "source"} and SECRET not in r.text
    r = await client.post("/v1/connections/monzo/sync", headers=auth)
    assert r.status_code == 409 and r.json()["error"]["code"] == "not_connected"


async def test_connections_default_and_disconnect_is_idempotent(client: httpx.AsyncClient) -> None:
    auth = await _auth(client)
    body = (await client.get("/v1/connections", headers=auth)).json()
    assert [(p["provider"], p["connected"], p["data_status"]) for p in body["providers"]] == [
        ("monzo", False, "mock"),
        ("trading212", False, "mock"),
    ]
    r = await client.delete("/v1/connections/trading212", headers=auth)
    assert r.status_code == 200 and not r.json()["providers"][1]["connected"]


async def test_bank_mock_flow_when_oauth_not_configured(client: httpx.AsyncClient) -> None:
    auth = await _auth(client)
    link = (await client.get("/v1/bank/auth-link", headers=auth)).json()
    assert link["status"] == "mock" and link["provider"] == "monzo" and link["state"].startswith("mock_")
    r = await client.get("/v1/bank/callback", params={"state": link["state"], "code": "x"}, follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"].startswith("lifeline://connected?status=ok&provider=monzo")
    again = await client.get("/v1/bank/callback", params={"state": link["state"], "code": "x"}, follow_redirects=False)
    assert again.status_code == 302 and "status=error" in again.headers["location"], "state is single use"
    s = await client.get("/v1/bank/summary", params={"session": link["state"]}, headers=auth)
    assert s.status_code == 200 and s.json()["status"] == "mock"


async def test_bank_callback_browser_gets_page_with_app_button(client: httpx.AsyncClient) -> None:
    html_accept = {"accept": "text/html,application/xhtml+xml"}
    r = await client.get(
        "/v1/bank/callback", params={"state": "forged", "code": "c"}, headers=html_accept, follow_redirects=False
    )
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert "Open Lifeline" in r.text and "expired or was already used" in r.text
    assert r.headers["x-app-redirect"] == "lifeline://connected?status=error&code=bad_state"
    assert 'href="lifeline://connected?status=error&amp;code=bad_state"' in r.text


async def test_bank_callback_error_and_missing_code(client: httpx.AsyncClient) -> None:
    denied = await client.get(
        "/v1/bank/callback", params={"state": "s", "error": "access_denied"}, follow_redirects=False
    )
    assert denied.headers["location"] == "lifeline://connected?status=error&code=access_denied"
    no_code = await client.get("/v1/bank/callback", params={"state": "s"}, follow_redirects=False)
    assert no_code.status_code == 302 and "status=error" in no_code.headers["location"]
    forged = await client.get("/v1/bank/callback", params={"state": "forged", "code": "c"}, follow_redirects=False)
    assert forged.status_code == 302 and "status=error" in forged.headers["location"]


async def test_habits_and_isa_on_sample_data(client: httpx.AsyncClient) -> None:
    auth = await _auth(client)
    h = (await client.get("/v1/finance/habits", headers=auth)).json()
    assert h["version"] == "hf-1" and len(h["factors"]) == 7
    periods = (await client.get("/v1/finance/isa/periods", headers=auth)).json()
    assert periods["data_status"] == "mock" and periods["label"] and "gfc_2008" in {p["id"] for p in periods["periods"]}
    strat = {"weights": {"global_equity": 0.8, "gilts": 0.2}, "period": "gfc_2008"}
    r = await client.post("/v1/finance/isa/backtest", headers=auth, json={"strategies": [strat, strat]})
    body = r.json()
    assert r.status_code == 200 and len(body["results"]) == 2 and body["contribution_source"] in ("derived", "default")
    assert body["data_status"] == "mock" and body["label"]
    r = await client.post(
        "/v1/finance/isa/backtest", headers=auth, json={"strategies": [strat], "monthly_contribution": 250}
    )
    assert r.json()["contribution_source"] == "request" and r.json()["monthly_contribution"] == 250
    r = await client.post("/v1/finance/isa/scenarios", headers=auth, json={"strategy": strat, "horizon_months": 24})
    assert r.status_code == 200 and r.json()["label"].startswith("Modelled scenarios") and r.json()["paths"]


async def test_isa_validation(client: httpx.AsyncClient) -> None:
    auth = await _auth(client)
    bad = [
        {"strategies": []},
        {"strategies": [{"weights": {"global_equity": 0.5}}]},
        {"strategies": [{"weights": {"bitcoin": 1.0}}]},
        {"strategies": [{"weights": {"cash": 1.0}}] * 5},
        {"strategies": [{"weights": {"cash": 1.0}}], "monthly_contribution": 0},
    ]
    for body in bad:
        r = await client.post("/v1/finance/isa/backtest", json=body, headers=auth)
        assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error", body
    r = await client.post(
        "/v1/finance/isa/backtest", headers=auth, json={"strategies": [{"weights": {"cash": 1.0}, "period": "nope"}]}
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


async def test_prediction_budgets_goals_roundtrip(client: httpx.AsyncClient) -> None:
    auth = await _auth(client)
    pred = (await client.get("/v1/finance/prediction", headers=auth)).json()
    assert pred["meta"]["data_status"] == "mock" and pred["low"] <= pred["predicted"] <= pred["high"]
    future = await client.get("/v1/finance/prediction", params={"date": "2999-01-01"}, headers=auth)
    assert future.status_code == 422
    first = await client.post("/v1/finance/guesses", json={"date": pred["date"], "amount": 20}, headers=auth)
    assert first.status_code == 201
    dup = await client.post("/v1/finance/guesses", json={"date": pred["date"], "amount": 21}, headers=auth)
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "already_guessed"
    past = (await client.get("/v1/finance/prediction", params={"date": "2026-10-10"}, headers=auth)).json()
    assert past["actual"] is not None
    made = await client.post("/v1/finance/guesses", json={"date": "2026-10-10", "amount": past["actual"]}, headers=auth)
    assert made.json()["guess"]["points"] == 100
    listed = (await client.get("/v1/finance/guesses", headers=auth)).json()
    assert listed["points_total"] >= 100 and len(listed["items"]) == 2
    assert listed["best_streak"] >= 1
    b = (await client.get("/v1/finance/budgets", headers=auth)).json()
    assert b["items"], "suggested budgets exist for sample data"
    await client.put("/v1/finance/budgets", json={"items": [{"category": "groceries", "limit": 321}]}, headers=auth)
    b2 = (await client.get("/v1/finance/budgets", headers=auth)).json()
    assert any(i["category"] == "groceries" and i["limit"] == 321 for i in b2["items"])
    g = await client.post("/v1/finance/goals", json={"name": "Bike", "target": 500}, headers=auth)
    assert g.status_code == 201
    assert [x["name"] for x in (await client.get("/v1/finance/goals", headers=auth)).json()["items"]] == ["Bike"]
