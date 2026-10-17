"""Route behaviour through the real app in test mode: auth, ownership, 501 stubs, rate limit, characters."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest


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
        ("GET", "/v1/challenges", None),
        ("POST", "/v1/purchases/verify", {"product_id": "lifeline.rewindpass", "demo": True}),
        ("GET", "/v1/rooms/ABC123", None),
        ("GET", "/v1/bank/auth-link", None),
    ],
)
async def test_later_tiers_answer_501(client: httpx.AsyncClient, method: str, path: str, body: object) -> None:
    r = await client.request(method, path, json=body, headers=await _auth(client))
    assert r.status_code == 501 and r.json()["error"]["code"] == "not_implemented"


async def test_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "3")
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
