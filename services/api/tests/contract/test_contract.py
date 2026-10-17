"""Every endpoint matches contracts/openapi.yaml; one error format everywhere. BOSS-owned."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from tests.contract.spec import operations, spec, validate

TIER0 = {
    "getHealth",
    "listSources",
    "signInDemo",
    "listCharacters",
    "createLife",
    "getLife",
    "ageLife",
    "chooseLife",
    "getLifeSummary",
}
TIER1 = {
    "actLife",
    "rewindLife",
    "listConcepts",
    "createDecision",
    "getEvaluation",
    "listLives",
    "getFinanceOverview",
    "getFinanceSpending",
    "getFinanceInsights",
    "listSubscriptions",
    "listBills",
    "listBudgets",
    "updateBudgets",
    "listGoals",
    "createGoal",
    "getFinanceProfile",
    "getSpendPrediction",
    "listGuesses",
    "makeGuess",
    "getPredictionEvaluation",
    "getNextMove",
    "testNextMove",
    "getPlan",
    "addPlanItem",
    # Connected accounts, investments and the ISA replay (ADR 0018, live data).
    "getInvestments",
    "getHabits",
    "getIsaPeriods",
    "postIsaBacktest",
    "postIsaScenarios",
    "listConnections",
    "connectTrading212",
    "connectMonzoToken",
    "syncMonzo",
    "disconnectProvider",
}
TIER2 = {
    "listChallenges",
    "createRoom",
    "getRoom",
    "getBankAuthLink",
    "bankCallback",
    "getBankSummary",
    "verifyPurchase",
    "signInWithApple",
}


def test_spec_lists_every_required_endpoint() -> None:
    have = {(m, p) for m, p, _ in operations()}
    required = [
        ("GET", "/v1/health"),
        ("GET", "/v1/sources"),
        ("GET", "/v1/characters"),
        ("POST", "/v1/lives"),
        ("GET", "/v1/lives/{id}"),
        ("POST", "/v1/lives/{id}/age"),
        ("POST", "/v1/lives/{id}/choices"),
        ("POST", "/v1/lives/{id}/actions"),
        ("POST", "/v1/lives/{id}/rewind"),
        ("GET", "/v1/lives/{id}/summary"),
        ("GET", "/v1/concepts"),
        ("GET", "/v1/challenges"),
        ("POST", "/v1/decisions"),
        ("GET", "/v1/evaluation"),
        ("POST", "/v1/rooms"),
        ("GET", "/v1/rooms/{code}"),
        ("GET", "/v1/bank/auth-link"),
        ("GET", "/v1/bank/callback"),
        ("POST", "/v1/purchases/verify"),
    ]
    assert not [r for r in required if r not in have]


def test_every_operation_is_tiered() -> None:
    ids = {o for _, _, o in operations()}
    assert ids == TIER0 | TIER1 | TIER2


def is_error(body: Any) -> bool:
    return isinstance(body, dict) and set(body) == {"error"} and {"code", "message", "source"} <= set(body["error"])


async def new_life(client: httpx.AsyncClient, auth: dict[str, str], **kw: Any) -> dict[str, Any]:
    payload = {"mode": "preset", "preset_id": "nurse-leeds", "start_year": 2006, "seed": 424242, **kw}
    r = await client.post("/v1/lives", json=payload, headers=auth)
    validate("POST", "/v1/lives", r.status_code, r.json())
    assert r.status_code == 201, r.text
    return r.json()


async def clear_events(client: httpx.AsyncClient, auth: dict[str, str], life: dict[str, Any]) -> dict[str, Any]:
    for ev in list(life["pending_events"]):
        default = next((c for c in ev["choices"] if c.get("is_default")), ev["choices"][0])
        r = await client.post(
            f"/v1/lives/{life['id']}/choices", json={"event_id": ev["id"], "choice_id": default["id"]}, headers=auth
        )
        validate("POST", "/v1/lives/{id}/choices", r.status_code, r.json())
        assert r.status_code == 200, r.text
        life = r.json()["life"]
    return life


# ---------------- Tier 0 ----------------


async def test_health(client: httpx.AsyncClient) -> None:
    r = await client.get("/v1/health")
    validate("GET", "/v1/health", r.status_code, r.json())


async def test_sources(client: httpx.AsyncClient) -> None:
    r = await client.get("/v1/sources")
    validate("GET", "/v1/sources", r.status_code, r.json())
    ids = {s["id"] for s in r.json()["sources"]}
    assert {"boe", "ons", "nomis", "landregistry", "postcodes"} <= ids


async def test_characters(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    r = await client.get("/v1/characters", params={"seed": 7}, headers=auth)
    validate("GET", "/v1/characters", r.status_code, r.json())
    ids = {c["id"] for c in r.json()["presets"]}
    assert {"nurse-leeds", "banker-london"} <= ids
    r2 = await client.get("/v1/characters", params={"seed": 7}, headers=auth)
    assert r2.json()["random"] == r.json()["random"], "random character must be deterministic per seed"


async def test_life_flow(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    life = await new_life(client, auth)
    lid = life["id"]
    r = await client.get(f"/v1/lives/{lid}", headers=auth)
    validate("GET", "/v1/lives/{id}", r.status_code, r.json())
    life = await clear_events(client, auth, r.json())
    for _ in range(4):
        r = await client.post(f"/v1/lives/{lid}/age", headers=auth)
        validate("POST", "/v1/lives/{id}/age", r.status_code, r.json())
        assert r.status_code == 200, r.text
        life = r.json()["life"]
        if life["pending_events"]:
            blocked = await client.post(f"/v1/lives/{lid}/age", headers=auth)
            validate("POST", "/v1/lives/{id}/age", blocked.status_code, blocked.json())
            assert blocked.status_code == 409 and is_error(blocked.json())
        life = await clear_events(client, auth, life)
    assert life["year"] == 2010
    r = await client.get(f"/v1/lives/{lid}/summary", headers=auth)
    validate("GET", "/v1/lives/{id}/summary", r.status_code, r.json())


async def test_same_seed_same_life(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    async def play() -> list[Any]:
        life = await clear_events(client, auth, await new_life(client, auth))
        for _ in range(3):
            r = await client.post(f"/v1/lives/{life['id']}/age", headers=auth)
            life = await clear_events(client, auth, r.json()["life"])
        return [(h["year"], h["text"], round(h["net_worth"], 2)) for h in life["history"]]

    assert await play() == await play()


async def test_life_requires_auth(client: httpx.AsyncClient) -> None:
    r = await client.get("/v1/lives/lf_abcdef12")
    validate("GET", "/v1/lives/{id}", r.status_code, r.json())
    assert r.status_code == 401 and is_error(r.json())


async def test_other_users_life_is_hidden(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    life = await new_life(client, auth)
    other = await client.post("/v1/auth/demo", json={"device_id": "another-device-123"})
    r = await client.get(f"/v1/lives/{life['id']}", headers={"Authorization": f"Bearer {other.json()['access_token']}"})
    assert r.status_code == 404 and is_error(r.json())


async def test_not_found_life(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    r = await client.get("/v1/lives/lf_doesnotexist", headers=auth)
    validate("GET", "/v1/lives/{id}", r.status_code, r.json())
    assert r.status_code == 404


async def test_validation_error_format(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    r = await client.post("/v1/lives", json={"mode": "preset", "start_year": 1800}, headers=auth)
    validate("POST", "/v1/lives", r.status_code, r.json())
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
    r = await client.post("/v1/lives", json={"mode": "preset", "start_year": 2006, "evil": 1}, headers=auth)
    assert r.status_code == 422 and is_error(r.json())


@pytest.mark.parametrize("method,path", [("GET", "/v1/nope"), ("DELETE", "/v1/health"), ("POST", "/v1/health")])
async def test_error_format_everywhere(client: httpx.AsyncClient, method: str, path: str) -> None:
    r = await client.request(method, path)
    assert r.status_code in (404, 405) and is_error(r.json()), r.text


async def test_bad_json_body(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    r = await client.post("/v1/lives", content=b"{not json", headers={**auth, "content-type": "application/json"})
    assert r.status_code == 422 and is_error(r.json())


# ---------------- Tier 1 ----------------


@pytest.mark.tier1
async def test_concepts(client: httpx.AsyncClient) -> None:
    r = await client.get("/v1/concepts")
    validate("GET", "/v1/concepts", r.status_code, r.json())
    assert len(r.json()["concepts"]) >= 40


@pytest.mark.tier1
async def test_actions_and_rewind(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    life = await clear_events(client, auth, await new_life(client, auth))
    decision_id = None
    for _ in range(6):
        r = await client.post(f"/v1/lives/{life['id']}/age", headers=auth)
        life = await clear_events(client, auth, r.json()["life"])
        decision_id = decision_id or next((h["decision_id"] for h in life["history"] if h.get("decision_id")), None)
    act = next(a for a in life["available_actions"] if a["enabled"] and not a["paid"])
    r = await client.post(
        f"/v1/lives/{life['id']}/actions", json={"tab": act["tab"], "action_id": act["id"]}, headers=auth
    )
    validate("POST", "/v1/lives/{id}/actions", r.status_code, r.json())
    assert r.status_code == 200
    assert decision_id, "six years should produce at least one decision"
    r = await client.post(f"/v1/lives/{life['id']}/rewind", json={"decision_id": decision_id}, headers=auth)
    validate("POST", "/v1/lives/{id}/rewind", r.status_code, r.json())
    assert r.status_code == 200
    r = await client.post(f"/v1/lives/{life['id']}/rewind", json={"decision_id": decision_id}, headers=auth)
    validate("POST", "/v1/lives/{id}/rewind", r.status_code, r.json())
    assert r.status_code == 402 and is_error(r.json())


@pytest.mark.tier1
async def test_decision(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    ex = spec()["components"]["examples"]["DecisionRequest"]["value"]
    r = await client.post("/v1/decisions", json=ex, headers=auth)
    validate("POST", "/v1/decisions", r.status_code, r.json())
    assert r.status_code == 200


@pytest.mark.tier1
async def test_evaluation(client: httpx.AsyncClient) -> None:
    r = await client.get("/v1/evaluation")
    validate("GET", "/v1/evaluation", r.status_code, r.json())
    assert r.status_code == 200


# ---------------- Tier 2 ----------------


@pytest.mark.tier2
async def test_challenges(client: httpx.AsyncClient) -> None:
    r = await client.get("/v1/challenges")
    validate("GET", "/v1/challenges", r.status_code, r.json())
    assert len(r.json()["challenges"]) >= 2


@pytest.mark.tier2
async def test_rooms_http(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    ex = spec()["components"]["examples"]["CreateRoom"]["value"]
    r = await client.post("/v1/rooms", json=ex, headers=auth)
    validate("POST", "/v1/rooms", r.status_code, r.json())
    assert r.status_code == 201
    r2 = await client.get(f"/v1/rooms/{r.json()['code']}", headers=auth)
    validate("GET", "/v1/rooms/{code}", r2.status_code, r2.json())
    assert r2.json()["seed"] == r.json()["seed"]
    r3 = await client.get("/v1/rooms/ZZZZZZ", headers=auth)
    assert r3.status_code == 404 and is_error(r3.json())


@pytest.mark.tier2
async def test_bank_flow(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    r = await client.get("/v1/bank/auth-link", headers=auth)
    validate("GET", "/v1/bank/auth-link", r.status_code, r.json())
    bad = await client.get("/v1/bank/callback", params={"state": "forged", "code": "x"}, follow_redirects=False)
    assert bad.status_code in (302, 400)
    if bad.status_code == 302:
        assert "status=error" in bad.headers["location"]
    ok = await client.get(
        "/v1/bank/callback", params={"state": r.json()["state"], "code": "sandbox-code"}, follow_redirects=False
    )
    assert ok.status_code == 302 and ok.headers["location"].startswith("lifeline://connected?status=ok")
    session = ok.headers["location"].split("session=")[1].split("&")[0]
    s = await client.get("/v1/bank/summary", params={"session": session}, headers=auth)
    validate("GET", "/v1/bank/summary", s.status_code, s.json())


@pytest.mark.tier2
async def test_purchase_demo(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    r = await client.post(
        "/v1/purchases/verify", json={"product_id": "lifeline.rewindpass", "demo": True}, headers=auth
    )
    validate("POST", "/v1/purchases/verify", r.status_code, r.json())
    assert r.json()["label"] == "Demo payment" and r.json()["demo"] is True


@pytest.mark.tier2
async def test_apple_sign_in_rejects_garbage(client: httpx.AsyncClient) -> None:
    r = await client.post("/v1/auth/apple", json={"identity_token": "not-a-real-token"})
    validate("POST", "/v1/auth/apple", r.status_code, r.json())
    assert r.status_code == 401 and is_error(r.json())


# ---------------- cross-cutting ----------------


async def test_characters_without_token(client: httpx.AsyncClient) -> None:
    r = await client.get("/v1/characters")
    validate("GET", "/v1/characters", r.status_code, r.json())
    assert r.status_code == 200
    bad = await client.get("/v1/characters", params={"seed": "abc"})
    validate("GET", "/v1/characters", bad.status_code, bad.json())
    assert bad.status_code == 422 and is_error(bad.json())


async def test_body_too_large(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    big = b'{"mode": "preset", "start_year": 2006, "pad": "' + b"x" * 70_000 + b'"}'
    r = await client.post("/v1/lives", content=big, headers={**auth, "content-type": "application/json"})
    validate("POST", "/v1/lives", r.status_code, r.json())
    assert r.status_code == 413 and r.json()["error"]["code"] == "payload_too_large"


@pytest.mark.parametrize("path", ["/v1/lives/not-a-life-id", "/v1/lives/lf_UPPER123/summary"])
async def test_invalid_path_param(client: httpx.AsyncClient, auth: dict[str, str], path: str) -> None:
    r = await client.get(path, headers=auth)
    template = "/v1/lives/{id}/summary" if path.endswith("summary") else "/v1/lives/{id}"
    validate("GET", template, r.status_code, r.json())
    assert r.status_code in (404, 422) and is_error(r.json())


def _example_body(op: dict[str, Any]) -> Any:
    rb = op.get("requestBody")
    if not rb:
        return None
    exs = rb["content"]["application/json"]["examples"]
    ref = next(iter(exs.values()))["$ref"].split("/")[-1]
    return spec()["components"]["examples"][ref]["value"]


LATER = sorted((m, p, o) for m, p, o in operations() if o in TIER1 | TIER2 and o != "bankCallback")


@pytest.mark.parametrize("method,path,op_id", LATER, ids=[o for _, _, o in LATER])
async def test_later_tier_ops_answer_inside_contract(
    client: httpx.AsyncClient, auth: dict[str, str], method: str, path: str, op_id: str
) -> None:
    """Whether built (2xx) or stubbed (501), every response is a declared status with a valid body."""
    life = await new_life(client, auth)
    concrete = path.replace("{id}", life["id"]).replace("{code}", "ZZZZZZ").replace("{provider}", "monzo")
    op = spec()["paths"][path][method.lower()]
    params = {"session": "missing-session"} if op_id == "getBankSummary" else None
    body = _example_body(op)
    if op_id == "rewindLife":
        body = {"decision_id": "ev-1900-1"}
    if op_id == "chooseLife":
        return
    r = await client.request(method, concrete, json=body, params=params, headers=auth)
    validate(method, path, r.status_code, r.json())
    if r.status_code >= 400:
        assert is_error(r.json())


# ---------------- Tier 1: Money tab (ADR 0016) ----------------

FINANCE_GETS = [
    ("/v1/finance/overview", None),
    ("/v1/finance/spending", None),
    ("/v1/finance/insights", None),
    ("/v1/finance/insights", {"months": 3}),
    ("/v1/finance/subscriptions", None),
    ("/v1/finance/bills", None),
    ("/v1/finance/budgets", None),
    ("/v1/finance/goals", None),
    ("/v1/finance/profile", None),
    ("/v1/finance/prediction", None),
    ("/v1/finance/guesses", None),
    ("/v1/finance/prediction/evaluation", None),
]


@pytest.mark.tier1
@pytest.mark.parametrize("path,params", FINANCE_GETS)
async def test_finance_reads(client: httpx.AsyncClient, auth: dict[str, str], path: str, params: Any) -> None:
    r = await client.get(path, params=params, headers=auth)
    validate("GET", path, r.status_code, r.json())
    assert r.status_code == 200
    meta = r.json()["meta"]
    if meta["data_status"] == "mock":
        assert meta.get("label") == "Sample data"


@pytest.mark.tier1
async def test_finance_requires_auth(client: httpx.AsyncClient) -> None:
    r = await client.get("/v1/finance/overview")
    validate("GET", "/v1/finance/overview", r.status_code, r.json())
    assert r.status_code == 401 and is_error(r.json())


@pytest.mark.tier1
async def test_finance_writes_and_bridge(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    r = await client.put(
        "/v1/finance/budgets", json={"items": [{"category": "eating_out", "limit": 180}]}, headers=auth
    )
    validate("PUT", "/v1/finance/budgets", r.status_code, r.json())
    assert r.status_code == 200
    assert any(b["category"] == "eating_out" and b["limit"] == 180 for b in r.json()["items"])
    g = await client.post("/v1/finance/goals", json={"name": "Holiday", "target": 1500}, headers=auth)
    validate("POST", "/v1/finance/goals", g.status_code, g.json())
    assert g.status_code == 201
    bad = await client.get("/v1/finance/spending", params={"month": "2026-13x"}, headers=auth)
    assert bad.status_code == 422 and is_error(bad.json())
    prof = (await client.get("/v1/finance/profile", headers=auth)).json()
    r = await client.post(
        "/v1/lives", json={"mode": "self", "start_year": 2026, "character": prof["character"]}, headers=auth
    )
    validate("POST", "/v1/lives", r.status_code, r.json())
    assert r.status_code == 201, "Money tab profile must start a Play yourself life"
    d = await client.post("/v1/decisions", json={"profile": prof["profile"]}, headers=auth)
    validate("POST", "/v1/decisions", d.status_code, d.json())
    assert d.status_code == 200


@pytest.mark.tier1
async def test_list_lives(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    life = await new_life(client, auth)
    r = await client.get("/v1/lives", headers=auth)
    validate("GET", "/v1/lives", r.status_code, r.json())
    assert any(x["id"] == life["id"] for x in r.json()["lives"])


@pytest.mark.tier1
async def test_guess_my_spend(client: httpx.AsyncClient) -> None:
    # Fresh device per run: the stack store keeps guesses, and a guess is allowed once per day per user.
    import uuid

    tok = await client.post("/v1/auth/demo", json={"device_id": f"guess-{uuid.uuid4().hex[:12]}"})
    auth = {"Authorization": f"Bearer {tok.json()['access_token']}"}
    pred = (await client.get("/v1/finance/prediction", headers=auth)).json()
    assert pred.get("guess") is None
    assert len(pred["reasons"]) <= 3 and pred["low"] <= pred["predicted"] <= pred["high"]
    r = await client.post("/v1/finance/guesses", json={"date": pred["date"], "amount": 30}, headers=auth)
    validate("POST", "/v1/finance/guesses", r.status_code, r.json())
    assert r.status_code == 201 and r.json()["guess"]["amount"] == 30
    again = await client.post("/v1/finance/guesses", json={"date": pred["date"], "amount": 40}, headers=auth)
    validate("POST", "/v1/finance/guesses", again.status_code, again.json())
    assert again.status_code == 409 and is_error(again.json())
    ev = (await client.get("/v1/finance/prediction/evaluation", headers=auth)).json()
    assert ev["n_days"] > 0 and ev["mae"] >= 0


# ---------------- Tier 1: Next Move (ADR 0018, top priority) ----------------


@pytest.mark.tier1
async def test_next_move_flow(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    r = await client.get("/v1/next-move", headers=auth)
    validate("GET", "/v1/next-move", r.status_code, r.json())
    assert r.status_code == 200
    nm = r.json()
    assert nm["question"] == "What is my next money move?"
    top = nm["top"]
    assert len(top["evidence"]) == 3 and len(nm["runners_up"]) <= 2
    assert all(s["status"] in ("live", "cached", "mock") for s in top["sources"])
    testable = next((m for m in [top, *nm["runners_up"]] if m["testable"]), None)
    assert testable is not None, "the demo persona must have a testable move"
    t = await client.post("/v1/next-move/test", json={"move_id": testable["id"]}, headers=auth)
    validate("POST", "/v1/next-move/test", t.status_code, t.json())
    assert t.status_code == 200 and len(t.json()["outcomes"]) >= 2
    for o in t.json()["outcomes"]:
        life = await client.get(f"/v1/lives/{o['life_id']}", headers=auth)
        assert life.status_code == 200, "each outcome life must open in the Life tab"
    missing = await client.post("/v1/next-move/test", json={"move_id": "mv_nope"}, headers=auth)
    validate("POST", "/v1/next-move/test", missing.status_code, missing.json())
    assert missing.status_code == 404 and is_error(missing.json())
    p = await client.post("/v1/plan", json={"move_id": top["id"]}, headers=auth)
    validate("POST", "/v1/plan", p.status_code, p.json())
    assert p.status_code == 201
    plan = await client.get("/v1/plan", headers=auth)
    validate("GET", "/v1/plan", plan.status_code, plan.json())
    assert any(i["move_id"] == top["id"] for i in plan.json()["items"])
