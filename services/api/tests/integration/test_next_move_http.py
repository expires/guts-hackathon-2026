"""Next move, Test it, plan and the Money tab through the HTTP API (ADR 0016, ADR 0018)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from lifeline_api.routes.next_move import scenario_seed, summary_sentence, worst_year_of
from lifeline_contracts.next_move import OptionOutcome, TestPeriod
from tests.integration.conftest import sign_in

DEMO_DEVICE = "demo-presenter-01"


async def _next_move(client: httpx.AsyncClient, auth: dict[str, str]) -> dict[str, Any]:
    r = await client.get("/v1/next-move", headers=auth)
    assert r.status_code == 200, r.text
    return r.json()


async def test_demo_persona_fix_mortgage_test_it(client: httpx.AsyncClient) -> None:
    from lifeline_api.main import app

    auth = await sign_in(client, DEMO_DEVICE)
    nm = await _next_move(client, auth)
    assert nm["meta"]["label"] == "Sample data"
    move = next(m for m in [nm["top"], *nm["runners_up"]] if m["kind"] == "fix_mortgage")
    assert move["testable"] and move["days_left"] == 165

    r = await client.post("/v1/next-move/test", json={"move_id": move["id"]}, headers=auth)
    assert r.status_code == 200, r.text
    res = r.json()
    assert [o["option_id"] for o in res["outcomes"]] == [o["id"] for o in move["options"]]
    assert res["character"]["housing"] == "mortgage"

    store = app.state.lifeline.store
    seeds, hashes = set(), set()
    for o in res["outcomes"]:
        life = (await client.get(f"/v1/lives/{o['life_id']}", headers=auth)).json()
        seeds.add(life["seed"])
        assert life["year"] == res["period"]["end"]
        rec = store._lives[o["life_id"]]  # MemoryLifeStore in test mode
        hashes.add(rec.macro_hash)
        assert await store.get_macro(rec.macro_hash) is not None, "macro table must be pinned"
        assert o["net_worth_path"][-1]["value"] == o["end_net_worth"]
        years = [int(pt["date"][:4]) for pt in o["net_worth_path"]]
        assert years == list(range(res["period"]["start"] - 1, res["period"]["end"] + 1)), "setup year, then period"
        assert res["period"]["start"] <= o["worst_year"] <= res["period"]["end"]
        assert o["total_cost"] > 0, "every option of the mortgage move has a cost"
    assert len(seeds) == 1, "every option plays with the same seed"
    assert len(hashes) == 1, "every option plays with the same macro table"

    again = (await client.post("/v1/next-move/test", json={"move_id": move["id"]}, headers=auth)).json()
    assert [o["end_net_worth"] for o in again["outcomes"]] == [o["end_net_worth"] for o in res["outcomes"]]

    listed = (await client.get("/v1/lives", headers=auth)).json()["lives"]
    assert {o["life_id"] for o in res["outcomes"]} <= {x["id"] for x in listed}


async def test_test_it_errors(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, DEMO_DEVICE)
    nm = await _next_move(client, auth)
    r = await client.post("/v1/next-move/test", json={"move_id": "mv_nope"}, headers=auth)
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    r = await client.post("/v1/next-move/test", json={"move_id": nm["top"]["id"], "option_ids": ["nope"]},
                          headers=auth)
    assert r.status_code == 404
    one = nm["top"]["options"][0]["id"]
    r = await client.post("/v1/next-move/test", json={"move_id": nm["top"]["id"], "option_ids": [one]}, headers=auth)
    assert r.status_code == 200 and len(r.json()["outcomes"]) == 1
    other = await sign_in(client, "someone-else-77")
    life_id = r.json()["outcomes"][0]["life_id"]
    assert (await client.get(f"/v1/lives/{life_id}", headers=other)).status_code == 404


async def test_plan_per_subject(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, DEMO_DEVICE)
    nm = await _next_move(client, auth)
    assert (await client.get("/v1/plan", headers=auth)).json() == {"items": [], "total_impact_per_year": 0.0}
    first = await client.post("/v1/plan", json={"move_id": nm["top"]["id"]}, headers=auth)
    assert first.status_code == 201
    dup = await client.post("/v1/plan", json={"move_id": nm["top"]["id"]}, headers=auth)
    assert dup.json()["id"] == first.json()["id"]
    if nm["runners_up"]:
        await client.post("/v1/plan", json={"move_id": nm["runners_up"][0]["id"]}, headers=auth)
    plan = (await client.get("/v1/plan", headers=auth)).json()
    assert len(plan["items"]) == 1 + min(1, len(nm["runners_up"]))
    assert plan["total_impact_per_year"] == round(sum(i["impact_per_year"] for i in plan["items"]), 2)
    assert (await client.post("/v1/plan", json={"move_id": "mv_nope"}, headers=auth)).status_code == 404
    other = await sign_in(client, "someone-else-77")
    assert (await client.get("/v1/plan", headers=other)).json()["items"] == []


async def test_budgets_goals_profile(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, DEMO_DEVICE)
    r = await client.put("/v1/finance/budgets", json={"items": [{"category": "groceries", "limit": 300}]},
                         headers=auth)
    r = await client.put("/v1/finance/budgets", json={"items": [{"category": "eating_out", "limit": 120}]},
                         headers=auth)
    cats = {b["category"]: b["limit"] for b in r.json()["items"]}
    assert cats == {"groceries": 300, "eating_out": 120}, "PUT upserts and keeps other limits"
    assert {b["category"] for b in (await client.get("/v1/finance/budgets", headers=auth)).json()["items"]} == set(cats)
    g = await client.post("/v1/finance/goals", json={"name": "Holiday", "target": 1500, "saved": 300}, headers=auth)
    assert g.status_code == 201
    goals = (await client.get("/v1/finance/goals", headers=auth)).json()["items"]
    assert [x["id"] for x in goals] == [g.json()["id"]] and goals[0]["progress"] == 0.2
    prof = (await client.get("/v1/finance/profile", headers=auth)).json()
    assert prof["character"]["town"] == "Leeds" and prof["personal_facts"]


async def test_lesson_personal_from_facts(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, DEMO_DEVICE)
    facts = (await client.get("/v1/finance/profile", headers=auth)).json()["personal_facts"]
    by_concept = {f["concept_id"]: f["text"] for f in facts}
    concepts = (await client.get("/v1/concepts", headers=auth)).json()["concepts"]
    filled = {c["id"]: c["lesson"].get("personal") for c in concepts if c["lesson"].get("personal")}
    assert filled and all(by_concept[k] == v for k, v in filled.items())
    anon = (await client.get("/v1/concepts")).json()["concepts"]
    assert not any(c["lesson"].get("personal") for c in anon)


async def test_decision_uses_server_time(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, DEMO_DEVICE)
    prof = (await client.get("/v1/finance/profile", headers=auth)).json()
    d = await client.post("/v1/decisions", json={"profile": prof["profile"]}, headers=auth)
    assert d.status_code == 200
    assert d.json()["generated_at"][:10] == datetime.now(UTC).strftime("%Y-%m-%d")


async def test_total_cost_uses_pinned_table(client: httpx.AsyncClient) -> None:
    from lifeline_api.main import app
    from lifeline_sim import api as sim_api

    auth = await sign_in(client, DEMO_DEVICE)
    nm = await _next_move(client, auth)
    move = next(m for m in [nm["top"], *nm["runners_up"]] if m["kind"] == "fix_mortgage")
    res = (await client.post("/v1/next-move/test", json={"move_id": move["id"]}, headers=auth)).json()
    store = app.state.lifeline.store
    for o in res["outcomes"]:
        rec = store._lives[o["life_id"]]
        table = await store.get_macro(rec.macro_hash)
        assert o["total_cost"] == round(sim_api.scenario_cost(rec.life, table), 2) > 0


def test_helpers() -> None:
    assert scenario_seed("a", "m") == scenario_seed("a", "m") != scenario_seed("a", "n")
    assert worst_year_of([(2021, 100.0), (2022, 50.0), (2023, 80.0)], 2023) == (2022, -50.0)
    assert worst_year_of([(2021, 100.0)], 2021) == (2021, 0.0)

    def o(oid: str, label: str, nw: float, cost: float = 1, rec: bool = False) -> OptionOutcome:
        return OptionOutcome(option_id=oid, label=label, is_recommended=rec, life_id="lf_x", net_worth_path=[],
                             end_net_worth=nw, total_cost=cost, missed_payments=0, worst_year=2023,
                             worst_year_change=0, index=100)

    period = TestPeriod(start=2021, end=2023, label="2021-2023 rate shock (stress test)")
    wins = [o("fix", "Fix for 5 years", 5180, rec=True), o("keep", "Keep", 1000), o("two", "Fix for 2 years", 2000)]
    assert summary_sentence(wins, period) == (
        "\u201cFix for 5 years\u201d left you £3,180 better off by 2023 than \u201cFix for 2 years\u201d.")
    loses = [o("tracker", "Take a tracker", 1000, cost=22339, rec=True), o("fix", "Fix for 5 years", 1300, cost=21553)]
    assert summary_sentence(loses, period) == (
        "In the 2021-2023 rate shock (stress test), \u201cTake a tracker\u201d cost £786 more "
        "than \u201cFix for 5 years\u201d.")
    cheaper = [o("a", "A", 1000, cost=10, rec=True), o("b", "B", 1500, cost=20)]
    assert summary_sentence(cheaper, period) == (
        "In the 2021-2023 rate shock (stress test), \u201cA\u201d left you £500 worse off by 2023 than \u201cB\u201d.")
