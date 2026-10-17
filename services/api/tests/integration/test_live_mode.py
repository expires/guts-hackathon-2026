"""DATA_MODE=live (ADR 0027) with an offline hub: no fixtures, no mock data, gaps in the MacroTable."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest

from lifeline_api.errors import ApiError
from lifeline_api.sim_bridge import call_pure
from tests.integration.conftest import sign_in

NO_DATA = {"code": "no_finance_data", "message": "Connect your money first.", "source": "data"}


@pytest.fixture
async def live(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATA_MODE", "live")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "test-only-encryption-key-for-user-data")
    from lifeline_api.main import app

    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app), httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("GET", "/v1/finance/overview", None),
        ("GET", "/v1/finance/spending", None),
        ("GET", "/v1/finance/subscriptions", None),
        ("GET", "/v1/finance/bills", None),
        ("GET", "/v1/finance/budgets", None),
        ("GET", "/v1/finance/goals", None),
        ("GET", "/v1/finance/profile", None),
        ("GET", "/v1/finance/prediction", None),
        ("GET", "/v1/finance/guesses", None),
        ("GET", "/v1/finance/prediction/evaluation", None),
        ("POST", "/v1/finance/guesses", {"date": "2026-10-17", "amount": 10}),
        ("PUT", "/v1/finance/budgets", {"items": [{"category": "groceries", "limit": 100}]}),
        ("POST", "/v1/finance/goals", {"name": "Holiday", "target": 100}),
        ("GET", "/v1/next-move", None),
        ("POST", "/v1/next-move/test", {"move_id": "fix_mortgage"}),
        ("POST", "/v1/plan", {"move_id": "fix_mortgage"}),
    ],
)
async def test_money_needs_own_data(live: httpx.AsyncClient, method: str, path: str, body: object) -> None:
    # Even the demo device gets no fixture persona in live mode.
    r = await live.request(method, path, json=body, headers=await sign_in(live, "demo-presenter-01"))
    assert r.status_code == 409 and r.json() == {"error": NO_DATA}


async def test_plan_list_works_without_data(live: httpx.AsyncClient) -> None:
    r = await live.get("/v1/plan", headers=await sign_in(live))
    assert r.status_code == 200 and r.json() == {"items": [], "total_impact_per_year": 0.0}


async def test_sources_report_unavailable_with_reason(live: httpx.AsyncClient) -> None:
    sources = (await live.get("/v1/sources")).json()["sources"]
    assert sources and all(s["status"] != "mock" for s in sources)
    down = [s for s in sources if s["status"] == "unavailable"]
    assert down and all(s.get("last_error") for s in down)


async def test_lives_play_on_real_data_only(live: httpx.AsyncClient) -> None:
    auth = await sign_in(live)
    assert (await live.get("/v1/characters", params={"seed": 3})).status_code == 200
    for body in ({"mode": "preset", "preset_id": "nurse-leeds", "start_year": 2006, "seed": 1},
                 {"mode": "random", "start_year": 2020, "seed": 5}):
        r = await live.post("/v1/lives", json=body, headers=auth)
        assert r.status_code == 201, r.text
        life = r.json()
        for _ in range(4):
            for ev in life["pending_events"]:
                choice = next((x for x in ev["choices"] if x.get("is_default")), ev["choices"][0])
                r = await live.post(f"/v1/lives/{life['id']}/choices",
                                    json={"event_id": ev["id"], "choice_id": choice["id"]}, headers=auth)
                assert r.status_code == 200, r.text
                life = r.json()["life"]
            r = await live.post(f"/v1/lives/{life['id']}/age", headers=auth)
            assert r.status_code == 200, r.text
            life = r.json()["life"]


async def test_no_personal_lesson_without_own_data(live: httpx.AsyncClient) -> None:
    concepts = (await live.get("/v1/concepts", headers=await sign_in(live, "demo-presenter-01"))).json()["concepts"]
    assert concepts and not any(c["lesson"].get("personal") for c in concepts)
    assert (await live.get("/v1/evaluation")).status_code == 200


async def test_macro_gap_is_409_data_unavailable() -> None:
    from lifeline_contracts.macro import MacroKey, MacroTable

    def read_gap() -> float:
        return MacroTable(values={}).get(MacroKey.BANK_RATE, 2020).value

    with pytest.raises(ApiError) as exc:
        await call_pure(read_gap)
    assert exc.value.status == 409 and exc.value.code == "data_unavailable" and "bank_rate" in exc.value.message.lower()

    def bug() -> None:
        raise KeyError("some_dict_key")

    with pytest.raises(KeyError):
        await call_pure(bug)  # A plain KeyError is a bug: it stays a 500.
