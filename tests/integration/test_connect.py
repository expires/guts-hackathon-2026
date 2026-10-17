"""Connect routes and Monzo OAuth, with httpx.MockTransport standing in for the providers."""

import base64
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient

from playyourself.adapters.credentials import CredentialStore
from playyourself.adapters.monzo_oauth import OAuthStateStore
from playyourself.api.app import app
from playyourself.api.deps import get_credential_store, get_http_client, get_oauth_states
from playyourself.settings import Settings, get_settings

MONZO_TOKEN = "monzo_tok_SECRET_0123456789"
T212_KEY = "t212_key_SECRET_0123456789"
T212_SECRET = "t212_sec_SECRET_0123456789"
CLIENT_SECRET = "client_secret_VALUE_abc"


class Env:
    def __init__(self, tmp_path):
        self.settings = Settings(
            _env_file=None,
            cache_dir=tmp_path / "cache",
            credentials_dir=tmp_path / "private",
            source_max_retries=0,
            monzo_base_url="https://monzo.test",
            t212_base_url="https://t212.test/api/v0",
            monzo_client_id="client_1",
            monzo_client_secret=CLIENT_SECRET,
            monzo_auth_url="https://auth.monzo.test/",
            monzo_token_url="https://monzo.test/oauth2/token",
        )
        self.store = CredentialStore(self.settings.credentials_dir, self.settings)
        self.states = OAuthStateStore()
        self.token_requests: list[dict] = []
        self.token_response = httpx.Response(
            200,
            json={
                "access_token": "new_access_SECRET_999999",
                "refresh_token": "r_SECRET_8888888",
                "expires_in": 100,
            },
        )
        self.monzo_txs: list[dict] | None = None  # None: the fake serves {} for every path
        # True: like Monzo before in-app approval, whoami works but data calls get 403.
        self.data_forbidden = False
        self.tx_requests: list[dict] = []
        self.valid_monzo = {MONZO_TOKEN, "new_access_SECRET_999999"}
        self.valid_t212 = {
            "Basic " + base64.b64encode(f"{T212_KEY}:{T212_SECRET}".encode()).decode()
        }
        self.client = httpx.AsyncClient(transport=httpx.MockTransport(self._handler))

    def _handler(self, req: httpx.Request) -> httpx.Response:
        auth = req.headers.get("Authorization", "")
        if req.url.path == "/oauth2/token":
            self.token_requests.append({k: v[0] for k, v in parse_qs(req.content.decode()).items()})
            return self.token_response
        if req.url.host == "monzo.test":
            ok = auth.removeprefix("Bearer ") in self.valid_monzo
            if ok and self.data_forbidden and req.url.path != "/ping/whoami":
                return httpx.Response(403, json={})
            if ok and self.monzo_txs is not None and req.url.path == "/accounts":
                return httpx.Response(
                    200, json={"accounts": [{"id": "acc_1", "type": "uk_retail"}]}
                )
            if ok and self.monzo_txs is not None and req.url.path == "/transactions":
                self.tx_requests.append(dict(req.url.params))
                return httpx.Response(200, json={"transactions": self.monzo_txs})
            return httpx.Response(200 if ok else 401, json={})
        if req.url.host == "t212.test":
            return httpx.Response(200 if auth in self.valid_t212 else 401, json={})
        return httpx.Response(404)


@pytest.fixture
def env(tmp_path):
    e = Env(tmp_path)
    app.dependency_overrides[get_settings] = lambda: e.settings
    app.dependency_overrides[get_credential_store] = lambda: e.store
    app.dependency_overrides[get_oauth_states] = lambda: e.states
    app.dependency_overrides[get_http_client] = lambda: e.client
    yield e
    app.dependency_overrides.clear()


@pytest.fixture
def client(env):
    return TestClient(app, follow_redirects=False)


def post(client, path, body):
    return client.post(path, json=body)


def test_status_demo_by_default(client, env):
    r = client.get("/v1/connect/status")
    d = r.json()["data"]["sources"]
    assert d["monzo"]["mode"] == "demo" and not d["monzo"]["connected"]
    assert d["monzo"]["oauth_available"] and not d["trading212"]["oauth_available"]
    assert d["monzo"]["health"]["ok"]


def test_monzo_paste_happy_path_and_no_secret_leaks(client, env):
    r = post(client, "/v1/connect/monzo/token", {"access_token": MONZO_TOKEN, "remember": True})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["mode"] == "live" and r.json()["data"]["hint"] == "…6789"
    assert env.store.get("monzo")["access_token"] == MONZO_TOKEN
    bodies = [r.text, client.get("/v1/connect/status").text, client.get("/v1/health").text]
    for b in bodies:
        assert MONZO_TOKEN not in b
    assert client.get("/v1/connect/status").json()["data"]["sources"]["monzo"]["remembered"]


def test_trading212_paste_with_secret_and_leaks(client, env):
    r = post(client, "/v1/connect/trading212", {"api_key": T212_KEY, "api_secret": T212_SECRET})
    assert r.status_code == 200, r.text
    for b in (r.text, client.get("/v1/connect/status").text):
        assert T212_KEY not in b and T212_SECRET not in b
    assert env.store.get("trading212")["api_secret"] == T212_SECRET


def test_bad_key_is_auth_error_and_stores_nothing(client, env):
    r = post(
        client,
        "/v1/connect/trading212",
        {"api_key": "nope_nope_nope_nope", "api_secret": "nope_secret_value", "remember": True},
    )
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "source_auth"
    assert "nope_nope_nope_nope" not in r.text and "nope_secret_value" not in r.text
    assert env.store.get("trading212") is None
    assert not (env.settings.credentials_dir / "credentials.json").exists()
    r = post(client, "/v1/connect/monzo/token", {"access_token": "bad"})
    assert r.json()["error"]["code"] == "source_auth" and env.store.get("monzo") is None


def test_validation_error_does_not_echo_secret(client):
    r = post(client, "/v1/connect/trading212", {"api_key": "", "api_secret": "leaky_secret_value"})
    assert r.status_code == 422 and "leaky_secret_value" not in r.text


def test_trading212_requires_secret(client, env):
    r = post(client, "/v1/connect/trading212", {"api_key": T212_KEY})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
    assert T212_KEY not in r.text and env.store.get("trading212") is None


def test_delete_reverts_to_demo(client, env):
    post(client, "/v1/connect/monzo/token", {"access_token": MONZO_TOKEN, "remember": True})
    r = client.delete("/v1/connect/monzo")
    assert r.json()["data"]["mode"] == "demo" and not r.json()["data"]["connected"]
    assert env.store.get("monzo") is None
    assert not (env.settings.credentials_dir / "credentials.json").exists()
    assert client.get("/v1/connect/status").json()["data"]["sources"]["monzo"]["mode"] == "demo"
    assert client.get("/v1/dashboard").json()["meta"]["sources"]["monzo"]["mode"] == "demo"


def test_connected_source_shows_live_in_dashboard_meta(client, env):
    post(client, "/v1/connect/monzo/token", {"access_token": MONZO_TOKEN})
    meta = client.get("/v1/dashboard").json()["meta"]["sources"]
    assert meta["monzo"]["mode"] == "live" and meta["trading212"]["mode"] == "demo"


def test_cross_origin_and_content_type_rejected(client, env):
    body = {"access_token": MONZO_TOKEN}
    r = client.post("/v1/connect/monzo/token", json=body, headers={"Origin": "http://evil.example"})
    assert r.status_code == 403 and env.store.get("monzo") is None
    r = client.delete("/v1/connect/monzo", headers={"Origin": "http://evil.example"})
    assert r.status_code == 403
    r = client.post(
        "/v1/connect/monzo/token",
        content='{"access_token":"x"}',
        headers={"Content-Type": "text/plain"},
    )
    assert r.status_code == 415
    r = client.post("/v1/connect/monzo/token", json=body, headers={"Origin": "http://testserver"})
    assert r.status_code == 200


# ---- Monzo OAuth ------------------------------------------------------------------------
def start(client):
    r = client.get("/v1/connect/monzo/start")
    assert r.status_code == 302
    return r.headers["location"]


def test_start_redirect_has_params(client, env):
    loc = urlparse(start(client))
    q = parse_qs(loc.query)
    assert f"{loc.scheme}://{loc.netloc}/" == "https://auth.monzo.test/"
    assert q["client_id"] == ["client_1"] and q["response_type"] == ["code"]
    assert q["redirect_uri"] == [env.settings.monzo_redirect_uri] and len(q["state"][0]) >= 32
    assert CLIENT_SECRET not in loc.geturl()


def test_start_not_configured(tmp_path):
    e = Env(tmp_path)
    e.settings = e.settings.model_copy(update={"monzo_client_id": ""})
    app.dependency_overrides[get_settings] = lambda: e.settings
    try:
        r = TestClient(app, follow_redirects=False).get("/v1/connect/monzo/start")
        assert r.status_code == 400 and r.json()["error"]["code"] == "not_configured"
    finally:
        app.dependency_overrides.clear()


def state_of(url):
    return parse_qs(urlparse(url).query)["state"][0]


def test_callback_success_stores_masked_token(client, env):
    st = state_of(start(client))
    r = client.get("/v1/connect/monzo/callback", params={"code": "abc", "state": st})
    assert r.status_code == 302 and r.headers["location"] == "/#connections?monzo=connected"
    req = env.token_requests[0]
    assert req["grant_type"] == "authorization_code" and req["code"] == "abc"
    assert req["client_id"] == "client_1" and req["redirect_uri"] == env.settings.monzo_redirect_uri
    creds = env.store.get("monzo")
    assert creds["access_token"] == "new_access_SECRET_999999" and creds["refresh_token"]
    assert "expires_at" in creds
    s = client.get("/v1/connect/status")
    assert "new_access_SECRET_999999" not in s.text and "r_SECRET_8888888" not in s.text
    assert s.json()["data"]["sources"]["monzo"]["hint"] == "…9999"


def test_callback_rejects_bad_expired_and_reused_state(client, env):
    loc = "/#connections?monzo=error&code=invalid_state"
    assert (
        client.get("/v1/connect/monzo/callback", params={"code": "a", "state": "forged"}).headers[
            "location"
        ]
        == loc
    )
    assert client.get("/v1/connect/monzo/callback", params={"code": "a"}).headers["location"] == loc
    st = state_of(start(client))
    assert (
        client.get("/v1/connect/monzo/callback", params={"code": "a", "state": st})
        .headers["location"]
        .endswith("connected")
    )
    assert (
        client.get("/v1/connect/monzo/callback", params={"code": "a", "state": st}).headers[
            "location"
        ]
        == loc
    )  # reuse
    now = [1000.0]
    env.states = OAuthStateStore(ttl_seconds=600, clock=lambda: now[0])
    st2 = env.states.issue()
    now[0] += 601
    assert (
        client.get("/v1/connect/monzo/callback", params={"code": "a", "state": st2}).headers[
            "location"
        ]
        == loc
    )
    assert len(env.token_requests) == 1


def test_callback_token_endpoint_error(client, env):
    env.token_response = httpx.Response(401, json={"error": "invalid_grant"})
    st = state_of(start(client))
    r = client.get("/v1/connect/monzo/callback", params={"code": "a", "state": st})
    assert r.headers["location"] == "/#connections?monzo=error&code=auth"
    assert env.store.get("monzo") is None


def test_callback_user_denied(client, env):
    st = state_of(start(client))
    r = client.get("/v1/connect/monzo/callback", params={"error": "access_denied", "state": st})
    assert r.headers["location"] == "/#connections?monzo=error&code=denied"


def test_refresh_on_auth_failure_updates_store(client, env):
    env.store.set(
        "monzo", {"access_token": "expired_token_0000", "refresh_token": "r_old_000000000"}
    )
    env.token_response = httpx.Response(200, json={"access_token": "new_access_SECRET_999999"})
    r = client.get("/v1/connect/status")
    h = r.json()["data"]["sources"]["monzo"]["health"]
    assert h["ok"], r.text
    req = env.token_requests[0]
    assert req["grant_type"] == "refresh_token" and req["refresh_token"] == "r_old_000000000"
    creds = env.store.get("monzo")
    assert creds["access_token"] == "new_access_SECRET_999999"
    assert creds["refresh_token"] == "r_old_000000000"  # kept when the response has none
    assert "expires_at" not in creds  # no expires_in in the response, so no lifetime assumed


def test_refresh_failure_reports_auth(client, env):
    env.store.set(
        "monzo", {"access_token": "expired_token_0000", "refresh_token": "r_old_000000000"}
    )
    env.token_response = httpx.Response(400, json={})
    h = client.get("/v1/connect/status").json()["data"]["sources"]["monzo"]["health"]
    assert not h["ok"] and h["error_code"] == "auth"


# ---- Monzo history import ---------------------------------------------------------------
HISTORY_TXS = [
    {
        "id": f"tx_{i}",
        "created": f"2025-0{i}-05T10:00:00Z",
        "amount": -12345 - i,
        "category": "x",
        "description": "SECRETSHOP",
    }
    for i in range(1, 4)
]


def test_token_paste_triggers_full_sync(client, env):
    env.monzo_txs = HISTORY_TXS
    r = post(client, "/v1/connect/monzo/token", {"access_token": MONZO_TOKEN})
    assert r.status_code == 200
    assert "since" not in env.tx_requests[0]  # full history, not a window
    h = r.json()["data"]["history"]
    assert h == {"synced": True, "oldest": "2025-01-05", "count": 3, "last_error": None}
    assert (env.settings.credentials_dir / "monzo_history.json").exists()
    status = client.get("/v1/connect/status")
    assert status.json()["data"]["sources"]["monzo"]["history"]["count"] == 3
    for needle in ("12345", "SECRETSHOP", MONZO_TOKEN):
        assert needle not in status.text and needle not in r.text


def test_oauth_callback_triggers_full_sync(client, env):
    env.monzo_txs = HISTORY_TXS
    st = state_of(start(client))
    client.get("/v1/connect/monzo/callback", params={"code": "abc", "state": st})
    assert len(env.tx_requests) == 1 and "since" not in env.tx_requests[0]
    h = client.get("/v1/connect/status").json()["data"]["sources"]["monzo"]["history"]
    assert h["synced"] and h["count"] == 3


def test_full_sync_failure_keeps_connection(client, env):
    r = post(client, "/v1/connect/monzo/token", {"access_token": MONZO_TOKEN})  # fake serves {}
    assert r.status_code == 200 and r.json()["data"]["connected"]
    h = r.json()["data"]["history"]
    assert h["synced"] is False and h["last_error"] == "bad_data" and h["count"] == 0
    assert env.store.get("monzo")["access_token"] == MONZO_TOKEN


def test_sync_retry_after_in_app_approval(client, env):
    env.monzo_txs, env.data_forbidden = HISTORY_TXS, True
    r = post(client, "/v1/connect/monzo/token", {"access_token": MONZO_TOKEN})
    assert r.status_code == 200 and r.json()["data"]["history"]["last_error"] == "auth"
    env.data_forbidden = False  # user approves in the Monzo app
    r = post(client, "/v1/connect/monzo/sync", {})
    h = r.json()["data"]["history"]
    assert h["synced"] and h["count"] == 3 and h["last_error"] is None
    assert MONZO_TOKEN not in r.text


def test_sync_requires_connection(client):
    r = post(client, "/v1/connect/monzo/sync", {})
    assert r.status_code == 409 and r.json()["error"] is not None


def test_disconnect_deletes_history(client, env):
    env.monzo_txs = HISTORY_TXS
    post(client, "/v1/connect/monzo/token", {"access_token": MONZO_TOKEN})
    path = env.settings.credentials_dir / "monzo_history.json"
    assert path.exists()
    r = client.delete("/v1/connect/monzo")
    assert not path.exists() and r.json()["data"]["history"]["synced"] is False
