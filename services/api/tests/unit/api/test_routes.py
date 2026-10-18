"""Route behaviour through the real app in test mode: auth, ownership, 501 stubs, rate limit, characters."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest

from tests.integration.personas import seed_persona


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setenv("APP_ENV", "test")
    from lifeline_api.main import app

    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app), httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _auth(client: httpx.AsyncClient, device: str = "unit-device-001") -> dict[str, str]:
    r = await client.post("/v1/auth/demo", json={"device_id": device})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_health_test_mode(client: httpx.AsyncClient) -> None:
    r = await client.get("/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["checks"] == {"postgres": "skipped", "redis": "skipped"}


async def test_demo_sign_in_validates(client: httpx.AsyncClient) -> None:
    r = await client.post("/v1/auth/demo", json={"device_id": "short"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
    r = await client.post("/v1/auth/demo", json={"device_id": "bad id with spaces"})
    assert r.status_code == 422


async def test_bad_tokens(client: httpx.AsyncClient) -> None:
    for header in ({"Authorization": "Bearer nope"}, {"Authorization": "Basic abc"}, {}):
        r = await client.get("/v1/lives/lf_abcdef12", headers=header)
        assert r.status_code == 401 and r.json()["error"]["code"] == "unauthorized"


async def test_invalid_life_id_is_422(client: httpx.AsyncClient) -> None:
    r = await client.get("/v1/lives/NOT-AN-ID", headers=await _auth(client))
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


async def test_create_life_rules(client: httpx.AsyncClient) -> None:
    auth = await _auth(client)
    r = await client.post("/v1/lives", json={"mode": "preset", "start_year": 2006}, headers=auth)
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
    r = await client.post("/v1/lives", json={"mode": "preset", "preset_id": "nobody-here", "start_year": 2006},
                          headers=auth)
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    r = await client.post("/v1/lives", json={"mode": "god", "start_year": 2006}, headers=auth)
    assert r.status_code == 422
    person = (await client.get("/v1/characters", params={"seed": 99})).json()["random"]
    start = min(2026, max(1990, person["birth_year"] + 30))
    r = await client.post("/v1/lives", json={"mode": "random", "start_year": start, "seed": 99}, headers=auth)
    assert r.status_code == 201, r.text
    assert r.json()["mode"] == "random" and r.json()["seed"] == 99
    assert r.json()["character"] == person, "random life must be the person GET /v1/characters showed for that seed"
    r = await client.post("/v1/lives", json={"mode": "random", "start_year": person["birth_year"] + 2, "seed": 99},
                          headers=auth)
    assert r.status_code == 422 and r.json()["error"]["source"] == "sim"


async def test_characters_without_auth_and_deterministic(client: httpx.AsyncClient) -> None:
    a = await client.get("/v1/characters", params={"seed": 11})
    b = await client.get("/v1/characters", params={"seed": 11})
    assert a.status_code == 200 and a.json()["random"] == b.json()["random"]
    r = await client.get("/v1/characters", params={"seed": -1})
    assert r.status_code == 422


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("POST", "/v1/purchases/verify", {"product_id": "lifeline.rewindpass", "demo": False}),
    ],
)
async def test_later_tiers_answer_501(client: httpx.AsyncClient, method: str, path: str, body: object) -> None:
    r = await client.request(method, path, json=body, headers=await _auth(client))
    assert r.status_code == 501 and r.json()["error"]["code"] == "not_implemented"


async def test_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("IP_RATE_LIMIT_PER_MINUTE", "3")
    from lifeline_api.main import app

    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app), httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        codes = [(await c.get("/v1/sources")).status_code for _ in range(4)]
        assert codes[:3] == [200, 200, 200] and codes[3] == 429
        r = await c.get("/v1/sources")
        assert r.json()["error"]["code"] == "rate_limited" and int(r.headers["retry-after"]) >= 1
        assert (await c.get("/v1/health")).status_code == 200, "health is never rate limited"


async def test_store_down(client: httpx.AsyncClient) -> None:
    """Read-only routes keep working; life routes answer 503 store_unavailable."""
    from lifeline_api.main import app
    from lifeline_api.store import StoreUnavailable

    auth = await _auth(client)

    class DownStore:
        def __getattr__(self, name: str) -> object:
            async def fail(*_: object, **__: object) -> None:
                raise StoreUnavailable()

            return fail

    real = app.state.lifeline.store
    app.state.lifeline.store = DownStore()
    try:
        assert (await client.get("/v1/characters", params={"seed": 3})).status_code == 200
        r = await client.post("/v1/lives", json={"mode": "preset", "preset_id": "nurse-leeds", "start_year": 2006},
                              headers=auth)
        assert r.status_code == 503 and r.json()["error"] == {
            "code": "store_unavailable", "message": r.json()["error"]["message"], "source": "store"}
        r = await client.get("/v1/lives/lf_abcdef12", headers=auth)
        assert r.status_code == 503
    finally:
        app.state.lifeline.store = real


async def test_finance_auth_and_month_validation(client: httpx.AsyncClient) -> None:
    assert (await client.get("/v1/finance/overview")).status_code == 401
    assert (await client.get("/v1/lives")).status_code == 401
    r = await client.get("/v1/finance/spending", params={"month": "2026-9"}, headers=await _auth(client))
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
    r = await client.put("/v1/finance/budgets", json={"bogus": 1}, headers=await _auth(client))
    assert r.status_code == 422


async def test_prediction_validation(client: httpx.AsyncClient) -> None:
    assert (await client.get("/v1/finance/prediction")).status_code == 401
    assert (await client.get("/v1/finance/prediction/evaluation")).status_code == 401
    auth = await _auth(client)
    await seed_persona("unit-device-001")
    r = await client.get("/v1/finance/prediction", params={"date": "2026-10"}, headers=auth)
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
    r = await client.get("/v1/finance/prediction/evaluation", headers=auth)
    assert r.status_code == 200 and "n_days" in r.json(), "must not be shadowed by /prediction"
    r = await client.post("/v1/finance/guesses", json={"bogus": 1}, headers=auth)
    assert r.status_code == 422


async def test_next_move_auth_and_validation(client: httpx.AsyncClient) -> None:
    for method, path in (("GET", "/v1/next-move"), ("POST", "/v1/next-move/test"), ("GET", "/v1/plan"),
                         ("POST", "/v1/plan")):
        assert (await client.request(method, path, json={})).status_code in (401, 422)
    auth = await _auth(client)
    for path in ("/v1/next-move/test", "/v1/plan"):
        r = await client.post(path, json={"bogus": 1}, headers=auth)
        assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


async def test_reads_survive_store_down(client: httpx.AsyncClient) -> None:
    """V3 G2, G3, N3: next move and prediction work without the store; writes say saving is down."""
    from lifeline_api.main import app
    from lifeline_api.store import StoreUnavailable

    auth = await _auth(client, "demo-presenter-01")
    await seed_persona("demo-presenter-01")

    class DownStore:
        def __getattr__(self, name: str) -> object:
            async def fail(*_: object, **__: object) -> None:
                raise StoreUnavailable()

            return fail

    real = app.state.lifeline.store
    app.state.lifeline.store = DownStore()
    try:
        r = await client.get("/v1/next-move", headers=auth)
        assert r.status_code == 200 and r.json()["top"]["id"]
        r = await client.get("/v1/finance/prediction", headers=auth)
        assert r.status_code == 200 and "guess" not in r.json()
        r = await client.post("/v1/plan", json={"move_id": "fix_mortgage"}, headers=auth)
        assert r.status_code == 503
        assert r.json()["error"]["message"] == "Saving is down. Try again in a minute."
    finally:
        app.state.lifeline.store = real


@pytest.mark.parametrize(
    "path,params",
    [
        ("/v1/finance/spending", {"month": "2026-13"}),
        ("/v1/finance/spending", {"month": "2026-00"}),
        ("/v1/finance/budgets", {"month": "2026-13"}),
        ("/v1/finance/prediction", {"date": "2026-02-30"}),
        ("/v1/finance/prediction", {"date": "2026-13-01"}),
    ],
)
async def test_impossible_calendar_values_are_422(client: httpx.AsyncClient, path: str, params: dict[str, str]) -> None:
    """V3 N4."""
    r = await client.get(path, params=params, headers=await _auth(client))
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


async def test_guess_for_impossible_day_is_422(client: httpx.AsyncClient) -> None:
    r = await client.post("/v1/finance/guesses", json={"date": "2026-02-30", "amount": 10},
                          headers=await _auth(client))
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


async def test_random_character_is_labelled_simulated(client: httpx.AsyncClient) -> None:
    from lifeline_sim.api import SIMULATED_LABEL

    auth = await _auth(client)
    body = (await client.get("/v1/characters", params={"seed": 21})).json()
    assert SIMULATED_LABEL in body["random"]["blurb"]
    assert all(SIMULATED_LABEL not in (p.get("blurb") or "") for p in body["presets"])
    person = body["random"]
    start = min(2026, max(1990, person["birth_year"] + 30))
    life = (await client.post("/v1/lives", json={"mode": "random", "start_year": start, "seed": 21},
                              headers=auth)).json()
    assert life["character"] == person
    listed = (await client.get("/v1/lives", headers=auth)).json()["lives"]
    assert any(x["id"] == life["id"] for x in listed)


TIER2_ACCOUNT = [
    ("GET", "/v1/me", None),
    ("DELETE", "/v1/me", None),
    ("POST", "/v1/me/reset", None),
    ("PUT", "/v1/me/health", {"steps_per_day": 8000, "sleep_hours": 7, "measured_days": 30}),
    ("POST", "/v1/auth/logout", None),
    ("PUT", "/v1/finance/manual", {"postcode": "LS6 1AN", "housing": "rent", "monthly_take_home": 2000}),
    ("POST", "/v1/finance/transactions", {"amount": 3.2, "merchant": "Pret"}),
    ("GET", "/v1/postcodes/reverse?lat=53.8&lon=-1.55", None),
]


@pytest.mark.parametrize("method,path,body", TIER2_ACCOUNT)
async def test_account_routes_need_auth(client: httpx.AsyncClient, method: str, path: str, body: object) -> None:
    assert (await client.request(method, path, json=body)).status_code == 401
    r = await client.request(method, path, json=body, headers=await _auth(client))
    assert r.status_code in (200, 201, 204, 404, 501), r.text


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("PUT", "/v1/me/health", {"steps_per_day": -1, "sleep_hours": 7, "measured_days": 30}),
        ("PUT", "/v1/finance/manual", {"postcode": "x", "housing": "rent", "monthly_take_home": 2000}),
        ("POST", "/v1/finance/transactions", {"amount": 0, "merchant": "Pret"}),
        ("GET", "/v1/postcodes/reverse?lat=40&lon=0", None),
        ("POST", "/v1/finance/statements", {"file": "not multipart"}),
    ],
)
async def test_account_stubs_validate(client: httpx.AsyncClient, method: str, path: str, body: object) -> None:
    r = await client.request(method, path, json=body, headers=await _auth(client))
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


async def test_statement_upload_has_its_own_5mb_limit(client: httpx.AsyncClient) -> None:
    auth = await _auth(client)
    one_mb = {"file": ("statement.csv", b"x" * 1_000_000, "text/csv")}
    r = await client.post("/v1/finance/statements", files=one_mb, headers=auth)
    assert r.status_code != 413, "1 MB is allowed on this route"
    six_mb = {"file": ("statement.csv", b"x" * 6_000_000, "text/csv")}
    r = await client.post("/v1/finance/statements", files=six_mb, headers=auth)
    assert r.status_code == 413 and r.json()["error"]["code"] == "payload_too_large"
    r = await client.post("/v1/finance/transactions", files=one_mb, headers=auth)
    assert r.status_code == 413, "other routes keep the 64 KB limit"


CHAT_ROUTES = [
    ("GET", "/v1/chat/threads", None),
    ("GET", "/v1/chat/threads/th_1", None),
    ("GET", "/v1/news?from=2026-10-01&to=2026-10-17&topic=rates", None),
    ("GET", "/v1/rate-decisions", None),
]


@pytest.mark.parametrize("method,path,body", CHAT_ROUTES)
async def test_chat_routes_need_auth(client: httpx.AsyncClient, method: str, path: str, body: object) -> None:
    assert (await client.request(method, path, json=body)).status_code == 401
    r = await client.request(method, path, json=body, headers=await _auth(client))
    assert r.status_code in (200, 404), r.text


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("POST", "/v1/chat", {"bogus": 1}),
        ("GET", "/v1/chat/threads/bad id!", None),
        ("GET", "/v1/news?from=2026-10-01", None),
        ("GET", "/v1/news?from=2026-10-01&to=2026-02-30", None),
        ("GET", "/v1/news?from=2026-10-01&to=2026-10-17&topic=gossip", None),
    ],
)
async def test_chat_stubs_validate(client: httpx.AsyncClient, method: str, path: str, body: object) -> None:
    r = await client.request(method, path, json=body, headers=await _auth(client))
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


async def test_truelayer_is_disabled_monzo_needs_setup(client: httpx.AsyncClient) -> None:
    auth = await _auth(client)
    assert (await client.get("/v1/bank/auth-link", params={"provider": "truelayer"})).status_code == 401
    r = await client.get("/v1/bank/auth-link", params={"provider": "truelayer"}, headers=auth)
    assert r.status_code == 409 and r.json()["error"]["code"] == "source_disabled"
    r = await client.get("/v1/bank/auth-link", headers=auth)
    assert r.status_code == 503 and r.json()["error"]["code"] == "not_configured", "no Monzo client id in tests"
    r = await client.get("/v1/bank/auth-link", params={"provider": "barclays"}, headers=auth)
    assert r.status_code == 422


async def test_reverse_postcode(client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from lifeline_api.main import app

    auth = await _auth(client)
    hub = app.state.lifeline.hub

    async def leeds(lat: float, lon: float) -> dict[str, str]:
        return {"postcode": "LS6 1AN", "region": "yorkshire-and-the-humber", "town": "Leeds", "status": "live"}

    async def at_sea(lat: float, lon: float) -> None:
        return None

    monkeypatch.setattr(hub, "reverse_postcode", leeds)
    r = await client.get("/v1/postcodes/reverse", params={"lat": 53.82, "lon": -1.57}, headers=auth)
    assert r.status_code == 200 and r.json()["postcode"] == "LS6 1AN" and r.json()["status"] == "live"
    monkeypatch.setattr(hub, "reverse_postcode", at_sea)
    r = await client.get("/v1/postcodes/reverse", params={"lat": 53.82, "lon": -1.57}, headers=auth)
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


async def test_reads_have_a_larger_budget_than_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "2")
    monkeypatch.setenv("READ_RATE_LIMIT_PER_MINUTE", "6")
    from lifeline_api.main import app

    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app), httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        auth = await _auth(c, "budget-device-01")
        await seed_persona("budget-device-01")
        reads = [(await c.get("/v1/plan", headers=auth)).status_code for _ in range(7)]
        assert reads == [200] * 6 + [429]
        body = {"name": "Trip", "target": 100}
        writes = [(await c.post("/v1/finance/goals", json=body, headers=auth)).status_code for _ in range(3)]
        assert writes == [201, 201, 429], "writes keep the smaller budget"
        r = await c.post("/v1/finance/goals", json=body, headers=auth)
        assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1


async def test_health_reports_warming_without_failing(client: httpx.AsyncClient) -> None:
    from lifeline_api.main import app

    assert (await client.get("/v1/health")).json()["warming"] is False
    app.state.lifeline.warming = True
    try:
        r = await client.get("/v1/health")
        assert r.status_code == 200 and r.json()["warming"] is True and r.json()["status"] == "ok"
    finally:
        app.state.lifeline.warming = False
