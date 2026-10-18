"""Every endpoint matches contracts/openapi.yaml; one error format everywhere. BOSS-owned."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from tests.contract.conftest import BASE
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
}
TIER2 = {
    "getForecast",
    "setForecastSettings",
    "getCategoryDetail",
    "getLearnPath",
    "getLearnLesson",
    "attemptLearnLesson",
    "listConnections",
    "connectTrading212",
    "connectMonzoToken",
    "syncMonzo",
    "disconnectProvider",
    "getProfileStats",
    "askPennyStream",
    "getFinanceHome",
    "askPenny",
    "listChatThreads",
    "getChatThread",
    "listNews",
    "getRateDecisions",
    "getMe",
    "deleteAccount",
    "resetDemo",
    "signOut",
    "importStatement",
    "listSamples",
    "importSample",
    "getHabits",
    "leaveCircle",
    "joinCircle",
    "createCircle",
    "listCircles",
    "listPaths",
    "setManualFinance",
    "logPayment",
    "reversePostcode",
    "setHealthSignal",
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
    # Direction V2 (ADR 0052, 0061): student path characters are offered; old presets are not.
    assert {"path-uni", "path-apprentice", "path-job18", "path-gap_year", "path-masters"} <= ids
    old = {"nurse-leeds", "banker-london", "plumber", "retired", "teacher-glasgow"}
    assert not ids & old, "only student or graduate presets"
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
    r3 = await client.get("/v1/rooms/0000", headers=auth)
    assert r3.status_code == 404 and is_error(r3.json())


@pytest.mark.tier2
@pytest.mark.skip(reason="Bank connections are cut in Direction V2 (ADR 0046); routes stay until cleanup")
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
async def test_purchase_demo(client: httpx.AsyncClient) -> None:
    # Fresh account: a saved rewind pass must not leak into later stack runs of test_actions_and_rewind.
    auth = await fresh_auth(client)
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


LATER = sorted(
    (m, p, o)
    for m, p, o in operations()
    if o in TIER1 | TIER2 and o not in ("bankCallback", "importStatement", "deleteAccount", "signOut", "askPennyStream")
)


@pytest.mark.parametrize("method,path,op_id", LATER, ids=[o for _, _, o in LATER])
async def test_later_tier_ops_answer_inside_contract(
    client: httpx.AsyncClient, auth: dict[str, str], method: str, path: str, op_id: str
) -> None:
    """Whether built (2xx) or stubbed (501), every response is a declared status with a valid body."""
    life = await new_life(client, auth)
    concrete = path.replace("{id}", life["id"]).replace("{code}", "0000")
    op = spec()["paths"][path][method.lower()]
    params = {"session": "missing-session"} if op_id == "getBankSummary" else None
    body = _example_body(op)
    if op_id == "rewindLife":
        body = {"decision_id": "ev-1900-1"}
    if op_id == "chooseLife":
        return
    # A demo purchase saves an entitlement; use a fresh account so it never leaks into later stack runs.
    headers = await fresh_auth(client) if op_id == "verifyPurchase" else auth
    r = await client.request(method, concrete, json=body, params=params, headers=headers)
    validate(method, path, r.status_code, r.json())
    if r.status_code >= 400:
        assert is_error(r.json())


# ---------------- Tier 1: Money tab (ADR 0016) ----------------

FINANCE_GETS = [
    ("/v1/finance/overview", None),
    ("/v1/finance/spending", None),
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

    device = f"guess-{uuid.uuid4().hex[:12]}"
    tok = await client.post("/v1/auth/demo", json={"device_id": device})
    auth = {"Authorization": f"Bearer {tok.json()['access_token']}"}
    if not BASE:  # no persona is served; the test seeds one explicitly (in-process only)
        from tests.integration.personas import seed_persona

        await seed_persona(device)
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
    assert nm["question"] == "Where should my money go this month?"
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


async def test_next_move_trade_offs(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    """GUTS brief: every recommendation states its trade-off (ADR 0042)."""
    r = await client.get("/v1/next-move", headers=auth)
    assert r.status_code == 200
    nm = r.json()
    for move in [nm["top"], *nm["runners_up"]]:
        t = move.get("trade_off")
        assert t, f"{move['kind']} has no trade-off"
        assert t["summary"] and len(t["summary"]) <= 90
        assert 1 <= len(t["points"]) <= 4
        if move["gain_kind"] == "months_of_cover":
            assert move["cover_months"] is not None


# ---------------- Tier 2: accounts, onboarding, connectors (ADR 0029) ----------------

MONZO_CSV = (
    "Transaction ID,Date,Time,Type,Name,Emoji,Category,Amount,Currency,Local amount,Local currency,"
    "Notes and #tags,Address,Receipt,Description,Category split,Money Out,Money In\n"
    "tx_1,01/10/2026,08:01:00,Card payment,Pret A Manger,,Eating out,-4.20,GBP,-4.20,GBP,,,,PRET,,-4.20,\n"
    "tx_2,01/10/2026,09:00:00,Faster payment,NHS SALARY,,Income,2314.18,GBP,2314.18,GBP,,,,SALARY,,,2314.18\n"
)


async def fresh_auth(client: httpx.AsyncClient) -> dict[str, str]:
    import uuid

    tok = await client.post("/v1/auth/demo", json={"device_id": f"t2-{uuid.uuid4().hex[:12]}"})
    return {"Authorization": f"Bearer {tok.json()['access_token']}"}


@pytest.mark.tier2
async def test_account_lifecycle(client: httpx.AsyncClient) -> None:
    auth = await fresh_auth(client)
    me = await client.get("/v1/me", headers=auth)
    validate("GET", "/v1/me", me.status_code, me.json())
    assert me.status_code == 200 and me.json()["has_finance_data"] is False
    r = await client.post("/v1/me/reset", headers=auth)
    validate("POST", "/v1/me/reset", r.status_code, r.json())
    d = await client.delete("/v1/me", headers=auth)
    assert d.status_code == 204
    gone = await client.get("/v1/me", headers=auth)
    assert gone.status_code in (401, 404) and is_error(gone.json())


@pytest.mark.tier2
async def test_onboarding_statement_then_next_move(client: httpx.AsyncClient) -> None:
    auth = await fresh_auth(client)
    files = {"file": ("monzo.csv", MONZO_CSV.encode(), "text/csv")}
    r = await client.post("/v1/finance/statements", files=files, data={"provider": "monzo"}, headers=auth)
    validate("POST", "/v1/finance/statements", r.status_code, r.json())
    assert r.status_code == 201 and r.json()["transactions"] >= 2
    me = (await client.get("/v1/me", headers=auth)).json()
    assert me["has_finance_data"] is True and "statement" in me["finance_inputs"]


@pytest.mark.tier2
async def test_onboarding_manual_entry(client: httpx.AsyncClient) -> None:
    auth = await fresh_auth(client)
    ex = spec()["components"]["examples"]["ManualFinance"]["value"]
    r = await client.put("/v1/finance/manual", json=ex, headers=auth)
    validate("PUT", "/v1/finance/manual", r.status_code, r.json())
    assert r.status_code == 200
    nm = await client.get("/v1/next-move", headers=auth)
    validate("GET", "/v1/next-move", nm.status_code, nm.json())
    assert nm.status_code == 200


@pytest.mark.tier2
async def test_connectors(client: httpx.AsyncClient) -> None:
    auth = await fresh_auth(client)
    r = await client.get("/v1/postcodes/reverse", params={"lat": 53.8, "lon": -1.57}, headers=auth)
    validate("GET", "/v1/postcodes/reverse", r.status_code, r.json())
    h = await client.put(
        "/v1/me/health", json={"steps_per_day": 8000, "sleep_hours": 7, "measured_days": 30}, headers=auth
    )
    validate("PUT", "/v1/me/health", h.status_code, h.json())
    assert h.status_code == 200
    p = await client.post("/v1/finance/transactions", json={"amount": 4.2, "merchant": "Pret A Manger"}, headers=auth)
    validate("POST", "/v1/finance/transactions", p.status_code, p.json())
    assert p.status_code == 201


# ---------------- Tier 2: Ask Penny and news (ADR 0030-0034) ----------------


@pytest.mark.tier2
async def test_news_and_rate_dates(client: httpx.AsyncClient) -> None:
    auth = await fresh_auth(client)
    n = await client.get("/v1/news", params={"from": "2008-09-01", "to": "2008-09-30"}, headers=auth)
    validate("GET", "/v1/news", n.status_code, n.json())
    for item in n.json().get("items", []):
        assert set(item) <= {"id", "headline", "standfirst", "section", "date", "url", "source"}, "no body text"
    r = await client.get("/v1/rate-decisions", headers=auth)
    validate("GET", "/v1/rate-decisions", r.status_code, r.json())


@pytest.mark.tier2
async def test_ask_penny_numbers_are_facts(client: httpx.AsyncClient) -> None:
    import re

    auth = await fresh_auth(client)
    ex = spec()["components"]["examples"]["ManualFinance"]["value"]
    await client.put("/v1/finance/manual", json=ex, headers=auth)
    r = await client.post("/v1/chat", json={"message": "What if I lose my job?"}, headers=auth)
    validate("POST", "/v1/chat", r.status_code, r.json())
    assert r.status_code == 200
    body = r.json()
    allowed = {round(abs(f["value"]), 2) for f in body["facts"]}
    for b in body["bubbles"]:
        for num in re.findall(r"\d[\d,]*(?:\.\d+)?", b["text"]):
            v = round(float(num.replace(",", "")), 2)
            assert v in allowed or any(abs(v - a) <= max(0.5, 0.005 * a) for a in allowed), f"unverified {num}"
    t = await client.get(f"/v1/chat/threads/{body['thread_id']}", headers=auth)
    validate("GET", "/v1/chat/threads/{id}", t.status_code, t.json())


@pytest.mark.tier2
async def test_ask_penny_out_of_scope_shrugs(client: httpx.AsyncClient) -> None:
    auth = await fresh_auth(client)
    r = await client.post("/v1/chat", json={"message": "Which shares should I buy tomorrow?"}, headers=auth)
    validate("POST", "/v1/chat", r.status_code, r.json())
    assert r.status_code == 200 and r.json()["reaction"] == "shrug"


@pytest.mark.tier2
async def test_ask_penny_stream_order(client: httpx.AsyncClient) -> None:
    import json as _json

    auth = await fresh_auth(client)
    ex = spec()["components"]["examples"]["ManualFinance"]["value"]
    await client.put("/v1/finance/manual", json=ex, headers=auth)
    events = []
    async with client.stream("POST", "/v1/chat/stream", json={"message": "Why this move?"}, headers=auth) as r:
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
        async for line in r.aiter_lines():
            if line.startswith("data:"):
                events.append(_json.loads(line[5:].strip()))
    types = [e["type"] for e in events]
    assert types[0] == "reaction" and types[-1] == "done"
    # ADR 0051: keepalive while waiting; an error is followed by done with the unavailable reply.
    assert all(t in ("tool_step", "verifying", "bubble", "keepalive", "error") for t in types[1:-1])
    done = events[-1]["response"]
    assert len(done["bubbles"]) <= 2
    if "error" in types:
        assert "bubble" not in types and done["verified"] is False
        return
    last_step = max((i for i, t in enumerate(types) if t == "tool_step"), default=0)
    assert types.index("bubble") > last_step
    streamed = [e["bubble"]["bubble"]["id"] for e in events if e["type"] == "bubble"]
    assert streamed == [b["id"] for b in done["bubbles"]]


@pytest.mark.tier2
async def test_finance_home_empty_is_not_an_error(client: httpx.AsyncClient) -> None:
    auth = await fresh_auth(client)
    r = await client.get("/v1/finance/home", headers=auth)
    validate("GET", "/v1/finance/home", r.status_code, r.json())
    assert r.status_code == 200
    body = r.json()
    if not body["has_data"]:
        assert body.get("connect_prompt") and "next_move" not in body and "prediction" not in body


FORBIDDEN_SHARED_KEYS = {"balance", "amount", "income", "merchant", "description", "transactions", "accounts"}


def _walk(node: Any, path: str = "") -> list[tuple[str, Any]]:
    if isinstance(node, dict):
        return [p for k, v in node.items() for p in _walk(v, f"{path}.{k}")] + [(f"{path}.{k}", None) for k in node]
    if isinstance(node, list):
        return [p for i, v in enumerate(node) for p in _walk(v, f"{path}[{i}]")]
    return [(path, node)]


async def test_shared_payloads_never_carry_personal_money(client: httpx.AsyncClient) -> None:
    """ADR 0052 privacy rule: habits and rooms share ratios only, never the user's amounts or merchants."""
    auth = await fresh_auth(client)
    imp = await client.post("/v1/samples/rich/import", headers=auth)
    assert imp.status_code == 201, imp.text
    overview = (await client.get("/v1/finance/overview", headers=auth)).json()
    personal = {round(abs(float(v)), 2) for p, v in _walk(overview) if isinstance(v, int | float) and abs(v) >= 1}
    merchants = {
        str(v).lower()
        for p, v in _walk((await client.get("/v1/finance/spending", headers=auth)).json())
        if p.endswith("merchant") and isinstance(v, str)
    }
    ex = spec()["components"]["examples"]["CreateRoom"]["value"]
    room = await client.post("/v1/rooms", json=ex, headers=auth)
    circle = await client.post("/v1/circles", json={"name": "Flat 4B"}, headers=auth)
    circles = await client.get("/v1/circles", headers=auth)
    shared = [(await client.get("/v1/habits", headers=auth)).json(), room.json(), circle.json(), circles.json()]
    for payload in shared:
        for path, value in _walk(payload):
            key = path.rsplit(".", 1)[-1].split("[")[0]
            assert key not in FORBIDDEN_SHARED_KEYS, f"forbidden key shared: {path}"
            if isinstance(value, float) and abs(value) >= 1:
                assert round(abs(value), 2) not in personal, f"personal amount shared at {path}: {value}"
            if isinstance(value, str):
                assert value.lower() not in merchants, f"merchant shared at {path}"
