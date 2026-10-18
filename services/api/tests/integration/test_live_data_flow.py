"""Live data end to end through the HTTP API, with Monzo and Trading212 mocked by respx (no network).

Covers: connect Trading212 -> connections live -> the user's own data (Money, Next Move) live, the ISA not counted
as cash; Monzo sign-in -> callback (302 to lifeline://connected) -> sync -> finance overview live; account delete
forgets the tokens; subject isolation; and that no secret ever appears in a response body or header.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from lifeline_data.hub import DataHub
from lifeline_data.providers.trading212 import reset_cache
from lifeline_data.settings import DataSettings
from tests.integration.conftest import sign_in

MONZO = "https://api.monzo.com"
T212 = "https://live.trading212.com/api/v0"

T212_KEY = "t212key-SECRET-9f8e7d6c"
T212_SECRET = "t212secret-SECRET-1a2b3c4d"
MONZO_TOKEN = "monzo-access-SECRET-5e6f7a8b"
MONZO_REFRESH = "monzo-refresh-SECRET-0p9o8i7u"
MONZO_CLIENT_SECRET = "monzo-client-SECRET-zxcvbnm"
SECRETS = [T212_KEY, T212_SECRET, MONZO_TOKEN, MONZO_REFRESH, MONZO_CLIENT_SECRET, "oauth-code-SECRET"]

POSITIONS = [
    {
        "instrument": {"ticker": "VUSAl_EQ", "isin": "IE00B3XXRP09", "name": "Vanguard S&P 500", "currency": "GBX"},
        "quantity": 10,
        "walletImpact": {"currency": "GBP", "currentValue": 900.0},
    },
    {
        "instrument": {"ticker": "AAPL_US_EQ", "isin": "US0378331005", "name": "Apple", "currency": "USD"},
        "quantity": 2.5,
        "walletImpact": {"currency": "GBP", "currentValue": 480.5},
    },
]
SUMMARY = {"id": 42, "currency": "GBP", "totalValue": 1500.0, "cash": {"availableToTrade": 119.5}}
CREATED = "2026-10-01T09:00:00Z"


def mock_t212(router: respx.MockRouter) -> None:
    router.get(T212 + "/equity/positions").mock(return_value=httpx.Response(200, json=POSITIONS))
    router.get(T212 + "/equity/account/summary").mock(return_value=httpx.Response(200, json=SUMMARY))


def mock_monzo(router: respx.MockRouter, approved: bool = True) -> None:
    def guard(request: httpx.Request, payload: Any) -> httpx.Response:
        return httpx.Response(200, json=payload) if request.headers["Authorization"] == f"Bearer {MONZO_TOKEN}" \
            else httpx.Response(401)

    if not approved:
        router.get(f"{MONZO}/accounts").mock(return_value=httpx.Response(403))
    else:
        router.get(f"{MONZO}/accounts").mock(
            side_effect=lambda r: guard(r, {"accounts": [{"id": "acc_1", "type": "uk_retail"}]})
        )
    router.get(f"{MONZO}/ping/whoami").mock(side_effect=lambda r: guard(r, {"authenticated": True}))
    router.get(f"{MONZO}/balance").mock(side_effect=lambda r: guard(r, {"balance": 123456}))
    router.get(f"{MONZO}/pots").mock(side_effect=lambda r: guard(r, {"pots": []}))
    txs = [
        {"id": "tx_1", "created": CREATED, "amount": -450, "description": "COSTA", "category": "eating_out",
         "merchant": {"name": "Costa"}},
    ]
    router.get(f"{MONZO}/transactions").mock(side_effect=lambda r: guard(r, {"transactions": txs}))


@pytest.fixture
def router() -> Iterator[respx.MockRouter]:
    with respx.mock(assert_all_called=False) as r:
        yield r


@pytest.fixture
async def live(tmp_path: Path, router: respx.MockRouter) -> AsyncIterator[httpx.AsyncClient]:
    """The real app with a data hub that may call (mocked) providers and stores credentials under tmp_path."""
    reset_cache()
    from lifeline_api.main import app

    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async def no_sleep(_: float) -> None:
            return None

        cfg = DataSettings(app_env="test", backoff_base_seconds=0, redis_url="", database_url="",
                           credentials_dir=str(tmp_path), monzo_client_id="cid",
                           monzo_client_secret=MONZO_CLIENT_SECRET)
        async with httpx.AsyncClient() as provider_client:
            hub = DataHub(cfg, client=provider_client, sleep=no_sleep, env={})
            real = app.state.lifeline.hub
            app.state.lifeline.hub = hub
            try:
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
                    yield c
            finally:
                app.state.lifeline.hub = real
    reset_cache()


def assert_no_secrets(r: httpx.Response) -> None:
    blob = r.text + str(dict(r.headers))
    for s in SECRETS:
        assert s not in blob, "a secret leaked into a response"


async def test_trading212_flow(live: httpx.AsyncClient, router: respx.MockRouter) -> None:
    mock_t212(router)
    auth = await sign_in(live, "flow-device-t212")
    seen: list[httpx.Response] = []

    async def call(method: str, path: str, **kw: Any) -> httpx.Response:
        r = await live.request(method, path, headers=auth, **kw)
        seen.append(r)
        return r

    r = await call("POST", "/v1/connections/trading212", json={"api_key": T212_KEY, "api_secret": T212_SECRET})
    assert r.status_code == 200, r.text
    assert r.json()["connected"] and r.json()["data_status"] == "live" and r.json()["hint"].endswith("9f8e7d6c"[-4:])

    conns = {p["provider"]: p for p in (await call("GET", "/v1/connections")).json()["providers"]}
    assert conns["trading212"]["connected"] and conns["trading212"]["data_status"] == "live"
    assert not conns["monzo"]["connected"] and conns["monzo"]["oauth_available"]

    me = (await call("GET", "/v1/me")).json()
    assert me["has_finance_data"] and "bank" in me["finance_inputs"]

    ov = (await call("GET", "/v1/finance/overview")).json()
    assert ov["meta"]["data_status"] == "live" and ov["meta"]["source"] == "trading212"
    # A Stocks and Shares ISA is an investment: it is not cash and not "savings earning 2%".
    assert ov["balance"] == 0 and ov["net_worth"] == 1500.0
    prof = (await call("GET", "/v1/finance/profile")).json()
    assert prof["profile"]["savings"] == 0

    nm = await call("GET", "/v1/next-move")
    assert nm.status_code == 200 and nm.json()["meta"]["data_status"] == "live"

    gone = await call("DELETE", "/v1/connections/trading212")
    assert gone.status_code == 200 and not gone.json()["providers"][1]["connected"]
    assert (await call("GET", "/v1/me")).json()["has_finance_data"] is False
    for r in seen:
        assert_no_secrets(r)


async def test_monzo_oauth_flow(live: httpx.AsyncClient, router: respx.MockRouter) -> None:
    auth = await sign_in(live, "flow-device-monzo")
    link = await live.get("/v1/bank/auth-link", headers=auth)
    body = link.json()
    assert link.status_code == 200 and body["status"] == "live" and body["provider"] == "monzo"
    assert body["url"].startswith("https://auth.monzo.com/") and f"state={body['state']}" in body["url"]
    assert MONZO_CLIENT_SECRET not in link.text

    router.post(f"{MONZO}/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": MONZO_TOKEN, "refresh_token": MONZO_REFRESH,
                                               "expires_in": 100})
    )
    mock_monzo(router, approved=False)  # the user has not approved access in the Monzo app yet
    cb = await live.get("/v1/bank/callback", params={"state": body["state"], "code": "oauth-code-SECRET"},
                        follow_redirects=False)
    assert cb.status_code == 302
    assert cb.headers["location"] == f"lifeline://connected?status=ok&provider=monzo&session={body['state']}"
    assert_no_secrets(cb)

    replay = await live.get("/v1/bank/callback", params={"state": body["state"], "code": "c"}, follow_redirects=False)
    assert replay.status_code == 302 and replay.headers["location"] == "lifeline://connected?status=error&code=bad_state"

    first = (await live.get("/v1/connections", headers=auth)).json()["providers"][0]
    assert first["connected"] and first["history"]["synced"] is False

    pending = await live.post("/v1/connections/monzo/sync", headers=auth)
    assert pending.status_code == 200 and pending.json()["synced"] is False and pending.json()["last_error"] == "auth"

    router.clear()
    router.post(f"{MONZO}/oauth2/token").mock(return_value=httpx.Response(200, json={"access_token": MONZO_TOKEN}))
    mock_monzo(router, approved=True)
    done = await live.post("/v1/connections/monzo/sync", headers=auth)
    assert done.status_code == 200 and done.json()["synced"] is True and done.json()["count"] == 1
    assert_no_secrets(done)

    ov = await live.get("/v1/finance/overview", headers=auth)
    assert ov.json()["meta"]["data_status"] == "live" and ov.json()["meta"]["source"] == "monzo"
    assert ov.json()["balance"] == 1234.56
    summary = await live.get("/v1/bank/summary", params={"session": body["state"]}, headers=auth)
    assert summary.status_code == 200 and summary.json()["status"] == "live" and summary.json()["accounts"] >= 1
    assert (await live.get("/v1/me", headers=auth)).json()["bank_name"] == "Monzo"
    assert_no_secrets(ov)
    assert_no_secrets(summary)

    assert (await live.delete("/v1/connections/monzo", headers=auth)).status_code == 200
    assert (await live.get("/v1/me", headers=auth)).json()["has_finance_data"] is False


async def test_monzo_token_connect_isolation_and_account_delete(
    live: httpx.AsyncClient, router: respx.MockRouter, tmp_path: Path
) -> None:
    mock_monzo(router)
    mock_t212(router)
    a = await sign_in(live, "iso-device-a")
    b = await sign_in(live, "iso-device-b")
    token = await live.post("/v1/connections/monzo/token", json={"access_token": MONZO_TOKEN}, headers=a)
    assert token.status_code == 200
    assert (await live.post("/v1/connections/trading212", headers=a,
                            json={"api_key": T212_KEY, "api_secret": T212_SECRET})).status_code == 200

    a_ov = (await live.get("/v1/finance/overview", headers=a)).json()
    assert a_ov["meta"]["data_status"] == "live" and a_ov["meta"]["source"] == "monzo+trading212"
    assert a_ov["balance"] == 1234.56, "cash is the Monzo balance only; the ISA is not added"

    # tokens and history sit on disk encrypted, never in plain text
    blob = "".join(f.read_text() for f in tmp_path.rglob("*.json"))
    assert blob and MONZO_TOKEN not in blob and T212_KEY not in blob and "Costa" not in blob

    # device B sees none of it, and never uses A's credentials
    b_conns = (await live.get("/v1/connections", headers=b)).json()["providers"]
    assert not any(p["connected"] for p in b_conns)
    assert (await live.get("/v1/me", headers=b)).json()["has_finance_data"] is False
    assert (await live.post("/v1/connections/monzo/sync", headers=b)).status_code == 409
    assert (await live.delete("/v1/connections/monzo", headers=b)).status_code == 200
    assert (await live.get("/v1/finance/overview", headers=a)).json()["meta"]["data_status"] == "live", \
        "B's disconnect must not touch A"

    # deleting the account forgets the Monzo and Trading212 credentials and history
    assert (await live.delete("/v1/me", headers=a)).status_code in (200, 204)
    assert not any(tmp_path.glob("*/credentials.json"))
    assert not any(tmp_path.glob("*/monzo_history.json"))


@pytest.mark.parametrize(
    "response,status,code",
    [
        (httpx.Response(401), 400, "provider_auth"),
        (httpx.Response(429, headers={"Retry-After": "7"}), 429, "rate_limited"),
        (httpx.Response(500), 502, "unavailable"),
        (httpx.Response(200, json={"currency": "EUR"}), 502, "bad_data"),
        (httpx.ReadTimeout("slow"), 504, "timeout"),
    ],
)
async def test_provider_failures_map_to_http(
    live: httpx.AsyncClient, router: respx.MockRouter, response: Any, status: int, code: str
) -> None:
    if isinstance(response, Exception):
        router.get(T212 + "/equity/account/summary").mock(side_effect=response)
    else:
        router.get(T212 + "/equity/account/summary").mock(return_value=response)
    auth = await sign_in(live, "fail-device-1")
    creds = {"api_key": T212_KEY, "api_secret": T212_SECRET}
    r = await live.post("/v1/connections/trading212", json=creds, headers=auth)
    assert r.status_code == status and r.json()["error"]["code"] == code
    assert set(r.json()["error"]) == {"code", "message", "source"} and r.json()["error"]["source"] == "trading212"
    if status == 429:
        assert r.headers["retry-after"] == "7"
    assert_no_secrets(r)
    # nothing was stored on failure
    conn = (await live.get("/v1/connections", headers=auth)).json()["providers"][1]
    assert conn["connected"] is False
    # and the failure is not the app's own 401
    assert r.status_code != 401


async def test_monzo_start_not_configured_is_unavailable_never_mock(tmp_path: Path) -> None:
    reset_cache()
    from lifeline_api.main import app

    async with app.router.lifespan_context(app):
        cfg = DataSettings(app_env="test", credentials_dir=str(tmp_path))
        app.state.lifeline.hub = DataHub(cfg, env={})
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            auth = await sign_in(c, "flow-device-mock")
            r = await c.get("/v1/bank/auth-link", headers=auth)
            assert r.status_code == 503 and r.json()["error"]["code"] == "not_configured"
