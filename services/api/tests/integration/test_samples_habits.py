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


@pytest.mark.parametrize("sample_id", ["rich", "working", "commuter"])
async def test_student_moves_can_be_tested(client: httpx.AsyncClient, sample_id: str) -> None:
    """ADR 0065: testable student moves run Test it, one stored life per option, same seed."""
    auth = await sign_in(client, f"student-test-it-{sample_id}")
    await client.post(f"/v1/samples/{sample_id}/import", headers=auth)
    nm = (await client.get("/v1/next-move", headers=auth)).json()
    moves = [m for m in [nm["top"], *nm["runners_up"]] if m["testable"]]
    assert moves, "a student has at least one testable move"
    for m in moves:
        r = await client.post("/v1/next-move/test", json={"move_id": m["id"]}, headers=auth)
        assert r.status_code == 200, (m["kind"], r.text)
        res = r.json()
        assert [o["option_id"] for o in res["outcomes"]] == [o["id"] for o in m["options"]]
        seeds = {(await client.get(f"/v1/lives/{o['life_id']}", headers=auth)).json()["seed"] for o in res["outcomes"]}
        assert len(seeds) == 1
    untestable = [m for m in [nm["top"], *nm["runners_up"]] if not m["testable"]]
    for m in untestable:
        r = await client.post("/v1/next-move/test", json={"move_id": m["id"]}, headers=auth)
        assert r.status_code == 409 and r.json()["error"]["code"] == "not_testable"


async def test_fresh_database_with_sources_down_never_hangs(client: httpx.AsyncClient,
                                                            monkeypatch: pytest.MonkeyPatch) -> None:
    """V3 F4: no last good table anywhere and a build that takes very long: home answers in time without
    the next move, and GET /v1/next-move answers 503 data_warming with Retry-After."""
    import asyncio

    from lifeline_api import macro
    from lifeline_api.main import app

    state = app.state.lifeline
    state.memo.pop(("macro-build",), None)
    state.memo.pop(("macro-last",), None)

    async def no_pointer(owner: str, kind: str) -> None:
        return None

    real_get_doc = state.store.get_doc

    async def get_doc(owner: str, kind: str) -> object:
        return None if (owner, kind) == (macro.POINTER_OWNER, macro.POINTER_KIND) else await real_get_doc(owner, kind)

    async def very_slow(*a: object, **k: object) -> object:
        await asyncio.sleep(30)
        raise AssertionError("not reached")

    monkeypatch.setattr(state.store, "get_doc", get_doc)
    monkeypatch.setattr(state.hub, "macro_table", very_slow)
    auth = await sign_in(client, "fresh-db-device-01")
    assert (await client.post("/v1/samples/working/import", headers=auth)).status_code == 201
    t0 = time.monotonic()
    home = await client.get("/v1/finance/home", headers=auth)
    assert home.status_code == 200 and time.monotonic() - t0 < 3.5
    assert home.json()["has_data"] and "next_move" not in home.json()
    r = await client.get("/v1/next-move", headers=auth)
    assert r.status_code == 503 and r.json()["error"]["code"] == "data_warming" and r.headers["retry-after"]
    for task in list(state.games):
        task.cancel()
    build = state.memo.pop(("macro-build",), None)
    if build is not None:
        build.cancel()


STUDENT_IDS = ["scholarship", "scottish", "commuter", "loan_england", "working", "mature", "international",
               "final_year", "rich", "graduate"]


async def test_samples_are_exactly_the_10_students(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "samples-device-ten")
    body = (await client.get("/v1/samples", headers=auth)).json()
    assert [s["id"] for s in body["samples"]] == STUDENT_IDS
    assert all(s["team"] is False for s in body["samples"])


async def _plan(client: httpx.AsyncClient, auth: dict[str, str]) -> tuple[list[dict], list[dict]]:
    budgets = (await client.get("/v1/finance/budgets", headers=auth)).json()["items"]
    goals = (await client.get("/v1/finance/goals", headers=auth)).json()["items"]
    return budgets, goals


async def test_sample_import_sets_up_budgets_and_goals(client: httpx.AsyncClient) -> None:
    """ADR 0070: each sample comes with its budgets and goals; re-import never adds copies; a user goal stays;
    another sample replaces the first sample's plan; reset clears it."""
    auth = await sign_in(client, "samples-plan-01")
    assert (await client.post("/v1/samples/loan_england/import", headers=auth)).status_code == 201
    budgets, goals = await _plan(client, auth)
    hints = samples.hints("loan_england") or {}
    assert {(b["category"], b["limit"]) for b in budgets} == {(b["category"], b["limit"]) for b in hints["budgets"]}
    assert [g["name"] for g in goals] == [g["name"] for g in hints["goals"]]
    assert goals[0]["id"] == "gl_sample_loan_england_1" and goals[0]["target"] == hints["goals"][0]["target"]
    assert goals[0]["target_date"] == hints["goals"][0]["target_date"] and goals[0]["monthly_needed"] > 0

    own = await client.post("/v1/finance/goals", headers=auth, json={"name": "New bike", "target": 300})
    assert own.status_code == 201
    assert (await client.post("/v1/samples/loan_england/import", headers=auth)).status_code == 201
    budgets2, goals2 = await _plan(client, auth)
    assert len(budgets2) == len(budgets)
    assert sorted(g["name"] for g in goals2) == sorted([*(g["name"] for g in hints["goals"]), "New bike"])

    assert (await client.post("/v1/samples/commuter/import", headers=auth)).status_code == 201
    budgets3, goals3 = await _plan(client, auth)
    commuter = samples.hints("commuter") or {}
    assert {b["category"] for b in budgets3} == {b["category"] for b in commuter["budgets"]}
    assert not any(g["id"].startswith("gl_sample_loan_england") for g in goals3)
    pot_goal = next(g for g in goals3 if g["id"] == "gl_sample_commuter_1")
    pots = sum(a["balance"] for a in commuter["accounts"] if a["kind"] == "savings")
    assert pot_goal["saved"] == round(pots, 2) and 0 < pot_goal["progress"] < 1

    assert (await client.post("/v1/me/reset", headers=auth)).status_code == 200
    budgets4 = (await client.get("/v1/finance/budgets", headers=auth))
    goals4 = (await client.get("/v1/finance/goals", headers=auth))
    assert budgets4.status_code != 200 or budgets4.json()["items"] == []
    assert goals4.status_code != 200 or goals4.json()["items"] == []


@pytest.mark.parametrize("sample_id", STUDENT_IDS)
async def test_every_sample_gets_a_budget_and_a_goal(client: httpx.AsyncClient, sample_id: str) -> None:
    auth = await sign_in(client, f"samples-plan-{sample_id.replace('_', '-')}")
    assert (await client.post(f"/v1/samples/{sample_id}/import", headers=auth)).status_code == 201
    budgets, goals = await _plan(client, auth)
    assert budgets and goals
    spend = (await client.get("/v1/finance/spending", headers=auth)).json()
    assert all(c["amount"] > 0 for c in spend["categories"]), "no £0 categories"
    other = sum(c["amount"] for c in spend["categories"] if c["category"] == "other")
    assert other < 0.15 * spend["total"]
