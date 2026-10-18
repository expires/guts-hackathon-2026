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


async def test_bank_link_without_oauth_is_unavailable_never_mock(client: httpx.AsyncClient) -> None:
    auth = await _auth(client)
    r = await client.get("/v1/bank/auth-link", headers=auth)
    assert r.status_code == 503 and r.json()["error"]["code"] == "not_configured"
    assert "mock" not in r.text


async def test_bank_callback_browser_gets_page_with_app_button(client: httpx.AsyncClient) -> None:
    html_accept = {"accept": "text/html,application/xhtml+xml"}
    r = await client.get(
        "/v1/bank/callback", params={"state": "forged", "code": "c"}, headers=html_accept, follow_redirects=False
    )
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert "Open Penny" in r.text and "expired or was already used" in r.text
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
