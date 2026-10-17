"""Sample statements, habit scores and judge-mode reset (ADR 0047, 0049, 0052)."""

from __future__ import annotations

import time
from collections.abc import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient

from lifeline_api import samples
from tests.integration.conftest import sign_in

pytestmark = pytest.mark.skipif(not samples.listing().samples, reason="demo/statements not generated")


async def test_list_samples(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "samples-device-01")
    assert (await client.get("/v1/samples")).status_code == 401
    body = (await client.get("/v1/samples", headers=auth)).json()
    ids = {s["id"]: s for s in body["samples"]}
    assert {"scholarship", "rich", "working", "commuter"} <= set(ids)
    assert not any(s["team"] for s in body["samples"]), "team phone profiles are not offered"
    assert all("hints" not in s for s in body["samples"])


@pytest.mark.parametrize("sample_id", ["scholarship", "rich", "working", "commuter"])
async def test_import_sample_under_10_seconds(client: httpx.AsyncClient, sample_id: str) -> None:
    auth = await sign_in(client, f"samples-import-{sample_id}")
    t0 = time.monotonic()
    r = await client.post(f"/v1/samples/{sample_id}/import", headers=auth)
    elapsed = time.monotonic() - t0
    assert r.status_code == 201, r.text
    assert elapsed < 10, f"import took {elapsed:.1f} s (ADR 0055 budget is 10 s)"
    res = r.json()
    assert res["status"] in ("done", "partial") and res["transactions"] > 0
    assert all(s["done"] for s in res["stages"]), res
    home = (await client.get("/v1/finance/home", headers=auth)).json()
    assert home["has_data"] and home["meta"]["label"] == "Sample data" and home["meta"]["source"] == "sample"
    prof = (await client.get("/v1/finance/profile", headers=auth)).json()
    hints = samples.hints(sample_id)
    assert hints is not None
    assert prof["is_student"] is hints["is_student"] and prof["profile"]["housing"] == hints["housing"]
    assert prof["profile"]["age"] == hints["age"]
    me = (await client.get("/v1/me", headers=auth)).json()
    assert me["has_finance_data"] is True and "sample" in me["finance_inputs"]


async def test_unknown_sample_is_404(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "samples-device-02")
    for bad in ("nope", "..%2F..%2Fetc%2Fpasswd", "index"):
        r = await client.post(f"/v1/samples/{bad}/import", headers=auth)
        assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


async def test_habits(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "habits-device-01")
    await client.post("/v1/samples/scholarship/import", headers=auth)
    r = await client.get("/v1/habits", headers=auth)
    assert r.status_code == 200
    body = r.json()
    for v in body["components"].values():
        assert v is None or 0 <= v <= 100, "ratios only, 0-100"
    text = r.text
    assert "£" not in text and "balance" not in text, "no amounts leave the user's view"


async def test_habits_without_data_is_409(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATA_MODE", "live")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "test-only-encryption-key-for-user-data")
    from lifeline_api.main import app

    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app), httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/v1/habits", headers=await sign_in(c, "habits-device-02"))
        assert r.status_code == 409 and r.json()["error"]["code"] == "no_finance_data"


@pytest.fixture
def tc(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("APP_ENV", "test")
    from lifeline_api.main import app

    with TestClient(app) as c:
        yield c


def test_reset_clears_rooms_and_lobbies(tc: TestClient) -> None:
    def token(device: str) -> str:
        return str(tc.post("/v1/auth/demo", json={"device_id": device}).json()["access_token"])

    host, guest = token("judge-host-0001"), token("judge-guest-0001")
    code = tc.post("/v1/rooms", json={"mode": "group", "host_name": "Ana", "preset_id": "nurse-leeds",
                                      "start_year": 2006}, headers={"Authorization": f"Bearer {host}"}).json()["code"]
    with tc.websocket_connect(f"/v1/rooms/{code}?token={guest}") as ws:
        ws.send_json({"type": "join", "name": "Ben"})
        while ws.receive_json()["type"] != "welcome":
            pass
    room = tc.get(f"/v1/rooms/{code}", headers={"Authorization": f"Bearer {host}"}).json()
    assert len(room["players"]) == 2
    assert tc.post("/v1/me/reset", headers={"Authorization": f"Bearer {host}"}).status_code == 200
    room = tc.get(f"/v1/rooms/{code}", headers={"Authorization": f"Bearer {guest}"}).json()
    assert [p["name"] for p in room["players"]] == ["Ben"] and room["players"][0]["is_host"]
    assert tc.post("/v1/me/reset", headers={"Authorization": f"Bearer {guest}"}).status_code == 200
    assert tc.get(f"/v1/rooms/{code}", headers={"Authorization": f"Bearer {host}"}).status_code == 404, \
        "an empty room is deleted"


async def test_import_does_not_wait_for_slow_live_data(client: httpx.AsyncClient,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    """V1: a cold start (macro table still building) must not hold the import past its budget."""
    import asyncio

    from lifeline_api.main import app
    from lifeline_api.routes import account

    monkeypatch.setattr(account, "NEXT_MOVE_BUDGET_SECONDS", 0.3)
    hub = app.state.lifeline.hub
    real = hub.macro_table

    async def slow_macro(*a: object, **k: object) -> object:
        await asyncio.sleep(2.0)
        return await real(*a, **k)

    monkeypatch.setattr(hub, "macro_table", slow_macro)
    auth = await sign_in(client, "cold-start-device-01")
    t0 = time.monotonic()
    r = await client.post("/v1/samples/working/import", headers=auth)
    assert r.status_code == 201 and time.monotonic() - t0 < 1.5
    stages = {s["name"]: s["done"] for s in r.json()["stages"]}
    assert stages["build_profile"] and stages["next_move"] is False
    await asyncio.sleep(2.2)
    nm = await client.get("/v1/next-move", headers=auth)
    assert nm.status_code == 200


async def test_sample_balances_are_real(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "balance-device-01")
    for sid in ("scholarship", "rich", "working", "commuter"):
        assert (await client.post(f"/v1/samples/{sid}/import", headers=auth)).status_code == 201
        ov = (await client.get("/v1/finance/overview", headers=auth)).json()
        assert ov["balance"] != 0 and ov["balance_parts"], f"{sid} must not show £0"



async def test_student_challenges_and_evaluation(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "student-challenges-01")
    listed = (await client.get("/v1/challenges")).json()
    titles = {c["title"] for c in listed["challenges"]}
    assert {"Make your money last the term", "1 month safety fund", "Clear Klarna", "Lifetime ISA by 25"} <= titles
    assert not titles & {"Survive 2008 with no missed payment", "Beat your twin", "Ride out the 2022 rate shock"}
    assert (await client.post("/v1/samples/rich/import", headers=auth)).status_code == 201
    body = (await client.get("/v1/challenges", headers=auth)).json()
    scoped = {c["id"] for c in body["challenges"] if c.get("scope") == "you"}
    assert scoped == {"last-the-term", "safety-fund-1m", "clear-klarna", "lisa-by-25"}
    mine = {p["challenge_id"]: p for p in body["progress"] if p["challenge_id"] in scoped}
    assert all("life_id" not in p for p in mine.values())
    assert set(mine) == {"last-the-term", "safety-fund-1m", "clear-klarna", "lisa-by-25"}
    assert mine["clear-klarna"]["status"] == "in_progress", "the rich student has a Klarna plan"
    assert all("£" not in (p.get("detail") or "") for p in mine.values())
    ev = (await client.get("/v1/evaluation", headers=auth)).json()
    assert ev["n"] == 0 and ev["periods"] == [] and "Not enough history" in ev["method"]
    assert (await client.get("/v1/evaluation")).json()["n"] > 0, "without a student the mortgage backtest stays"


@pytest.mark.parametrize("sample_id", ["scholarship", "rich", "working", "commuter"])
async def test_sample_profile_age_and_income(client: httpx.AsyncClient, sample_id: str) -> None:
    from lifeline_api.money import PAYMENTS_PER_YEAR

    auth = await sign_in(client, f"profile-{sample_id}-01")
    await client.post(f"/v1/samples/{sample_id}/import", headers=auth)
    prof = (await client.get("/v1/finance/profile", headers=auth)).json()
    as_of_year = int(prof["meta"]["as_of"][:4])
    assert prof["character"]["birth_year"] == as_of_year - prof["profile"]["age"]
    assert prof["profile"]["annual_income"] > 0
    assert prof["character"]["annual_income"] == prof["profile"]["annual_income"]
    from lifeline_api.main import app

    sub = (await client.get("/v1/me", headers=auth)).json()["id"]
    snap = await app.state.lifeline.hub.get_user_snapshot(sub)
    want = round(sum(s.amount * PAYMENTS_PER_YEAR[s.schedule] for s in snap.income_sources), 2)
    assert prof["profile"]["annual_income"] == pytest.approx(want)


async def test_cold_start_import_then_next_move_under_3_seconds(client: httpx.AsyncClient,
                                                                monkeypatch: pytest.MonkeyPatch) -> None:
    """V1 O1: after a restart the MacroTable build takes ~26 s. Import and GET /v1/next-move must not wait:
    they use the last good table (kept in Postgres) and finish the stored move in the background."""
    import asyncio

    from lifeline_api import macro
    from lifeline_api.main import app

    state = app.state.lifeline
    await macro.table(state)  # a previous process built and kept a good table
    await asyncio.sleep(0.05)
    state.memo.pop(("macro-build",), None)  # new process: no build yet, nothing in memory
    state.memo.pop(("macro-last",), None)
    real = state.hub.macro_table

    async def cold(*a: object, **k: object) -> object:
        await asyncio.sleep(4.0)
        return await real(*a, **k)

    monkeypatch.setattr(state.hub, "macro_table", cold)
    auth = await sign_in(client, "cold-next-move-01")
    t0 = time.monotonic()
    assert (await client.post("/v1/samples/scholarship/import", headers=auth)).status_code == 201
    r = await client.get("/v1/next-move", headers=auth)
    elapsed = time.monotonic() - t0
    assert r.status_code == 200 and elapsed < 3.0, f"import + next move took {elapsed:.1f} s"
    home = await client.get("/v1/finance/home", headers=auth)
    assert home.status_code == 200 and "next_move" in home.json()
