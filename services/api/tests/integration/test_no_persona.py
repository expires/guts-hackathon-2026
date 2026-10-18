"""No account ever gets a demo finance persona (user decision: the 4 non-student personas are for tests only).

An account without its own money data gets the honest "no data" state: Money home has_data=false, /v1/me
has_finance_data=false, money routes 409 no_finance_data. Checked for a fresh demo account, the old
presenter devices (they were pinned to the Leeds persona), new device ids (they were hashed to a persona)
and after POST /v1/me/reset. No response carries a persona name, employer, postcode, label or exact £ amount.
"""

from __future__ import annotations

import ast
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest

from lifeline_contracts.chat import ChatBubble, ChatRequest, ChatResponse
from lifeline_data.finance import PERSONA_IDS, fixture_snapshot
from lifeline_data.finance.personas import PERSONAS
from lifeline_explain.chat_tools import ChatToolContext
from tests.integration.conftest import sign_in

API_ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_PACKAGES = ("lifeline_api", "lifeline_data", "lifeline_engine", "lifeline_sim", "lifeline_explain",
                       "lifeline_eval", "lifeline_contracts", "seed")
PERSONA_PACKAGE = API_ROOT / "lifeline_data" / "finance"

# Routes that show the user's own money, or their game state built from it.
MONEY_GETS = (
    "/v1/finance/home", "/v1/finance/overview", "/v1/finance/spending", "/v1/finance/subscriptions",
    "/v1/finance/bills", "/v1/finance/budgets", "/v1/finance/goals", "/v1/finance/profile",
    "/v1/finance/prediction", "/v1/finance/guesses", "/v1/finance/prediction/evaluation", "/v1/next-move",
    "/v1/plan", "/v1/habits", "/v1/me", "/v1/circles", "/v1/lives", "/v1/bank/summary",
)
# Play and Learn: shared game content. Sim characters reuse some first names (Tom, Jordan) and round salaries
# (45,000), so only the full persona identity and the exact non-round amounts are checked here.
GAME_GETS = ("/v1/characters", "/v1/challenges", "/v1/learn", "/v1/concepts", "/v1/paths")
NO_DATA_409 = {
    "/v1/finance/overview", "/v1/finance/spending", "/v1/finance/subscriptions", "/v1/finance/bills",
    "/v1/finance/budgets", "/v1/finance/goals", "/v1/finance/profile", "/v1/finance/prediction",
    "/v1/finance/guesses", "/v1/next-move", "/v1/habits",
}

DEVICES = ("no-persona-device-01", "demo-presenter-01", "demo-presenter-05",
           *(f"new-player-device-{n:02d}" for n in range(6)))


def _identity() -> set[str]:
    """Strings that only a persona has: full name, label, employer, postcode, id, savings product, landlord."""
    out: set[str] = set()
    for p in PERSONAS.values():
        out |= {p.id, p.label, p.employer, p.postcode, p.savings_name}
        if " " in p.name:
            out.add(p.name)
        if p.landlord:
            out.add(p.landlord)
    return {s.lower() for s in out if s}


def _first_names() -> set[str]:
    return {p.name.split(" ")[0] for p in PERSONAS.values()}


def _amounts() -> set[float]:
    """Exact £ amounts of every persona: salaries, pay, rent, balances (persona and generated snapshot)."""
    out: set[float] = set()
    for pid, p in PERSONAS.items():
        out |= {p.gross_salary, p.net_pay, p.current_balance, p.savings_balance, p.isa_balance, p.pension_balance}
        if p.rent:
            out.add(p.rent)
        if p.mortgage is not None:
            out |= {v for v in vars(p.mortgage).values() if isinstance(v, float)}
        snap = fixture_snapshot(f"persona:{pid}")
        out |= {a.balance for a in snap.accounts}
        if snap.mortgage is not None:
            out |= {snap.mortgage.balance, snap.mortgage.property_value, snap.mortgage.monthly_payment}
    return {round(abs(v), 2) for v in out if abs(v) >= 100}


IDENTITY, FIRST_NAMES, AMOUNTS = _identity(), _first_names(), _amounts()


def _walk(node: Any) -> Iterator[Any]:
    if isinstance(node, dict):
        for k, v in node.items():
            yield k
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)
    else:
        yield node


def assert_no_persona(path: str, body: Any, *, first_names: bool = True) -> None:
    """`first_names=False` (game content): skip first names and amounts that are whole multiples of £50."""
    text = json.dumps(body).lower()
    leaked = sorted(s for s in IDENTITY if s in text)
    assert not leaked, f"{path}: persona identity in response: {leaked}"
    if first_names:
        words = {w for v in _walk(body) if isinstance(v, str) for w in v.replace(",", " ").split()}
        assert not (words & FIRST_NAMES), f"{path}: persona first name in response: {words & FIRST_NAMES}"
    nums = {round(abs(float(v)), 2) for v in _walk(body) if isinstance(v, int | float) and not isinstance(v, bool)}
    amounts = AMOUNTS if first_names else {v for v in AMOUNTS if v % 50}
    assert not (nums & amounts), f"{path}: persona amount in response: {sorted(nums & amounts)}"


async def assert_no_data_everywhere(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    for path in MONEY_GETS:
        r = await client.get(path, headers=auth)
        assert r.status_code < 500, (path, r.text)
        body = r.json()
        assert_no_persona(path, body)
        if path in NO_DATA_409:
            assert r.status_code == 409 and body["error"]["code"] == "no_finance_data", (path, r.text)
    home = (await client.get("/v1/finance/home", headers=auth)).json()
    assert home == {"has_data": False, "connect_prompt": "Connect your money to see your next move"}
    me = (await client.get("/v1/me", headers=auth)).json()
    assert me["has_finance_data"] is False and me["finance_inputs"] == []
    for path in GAME_GETS:
        r = await client.get(path, headers=auth)
        assert r.status_code < 500, (path, r.text)
        assert_no_persona(path, r.json(), first_names=False)
    # Rooms and circles: names and habits come from the user's own data only.
    room = await client.post("/v1/rooms", json={}, headers=auth)
    assert room.status_code < 500, room.text
    assert_no_persona("/v1/rooms", room.json(), first_names=False)
    circle = await client.post("/v1/circles", json={"name": "Flat"}, headers=auth)
    assert circle.status_code < 500, circle.text
    assert_no_persona("/v1/circles", circle.json())
    assert_no_persona("/v1/circles", (await client.get("/v1/circles", headers=auth)).json())


# ---------- Penny chat context ----------

SEEN: list[ChatToolContext] = []


async def _fake_answer(req: ChatRequest, ctx: ChatToolContext) -> ChatResponse:
    SEEN.append(ctx)
    return ChatResponse(thread_id=ctx.thread_id or "", message_id="pm_1", reply_to=ctx.user_message_id or "",
                        reaction="brain", bubbles=[ChatBubble(id="b1", kind="answer", text="ok")], confidence=0.9,
                        verified=True)


@pytest.fixture(autouse=True)
def fake_penny(monkeypatch: pytest.MonkeyPatch) -> None:
    from lifeline_api.routes import chat as chat_routes

    SEEN.clear()
    monkeypatch.setattr(chat_routes.penny, "answer", _fake_answer)


async def assert_penny_has_no_persona(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    r = await client.post("/v1/chat", json={"message": "How much money do I have?"}, headers=auth)
    assert r.status_code == 200, r.text
    assert_no_persona("/v1/chat", r.json())
    ctx = SEEN[-1]
    tools: Any = ctx.tools
    snap = tools.snapshot
    assert snap.source == "none" and snap.status == "unavailable" and not snap.transactions
    assert snap.persona is None and all(a.balance == 0 for a in snap.accounts)
    assert tools.personal_facts() == [] and tools.preload == ()
    assert not {"user_balance", "finance_summary"} & set(tools._inputs), "no personal tools without own data"
    assert_no_persona("chat context", json.loads(snap.model_dump_json()))


# ---------- scenarios ----------


@pytest.mark.parametrize("device", DEVICES)
async def test_new_account_gets_no_persona(client: httpx.AsyncClient, device: str) -> None:
    """Fresh demo account, new player (new device id), and the old presenter devices."""
    auth = await sign_in(client, device)
    await assert_no_data_everywhere(client, auth)
    await assert_penny_has_no_persona(client, auth)


async def test_after_reset_no_persona(client: httpx.AsyncClient) -> None:
    from tests.integration.personas import seed_persona

    device = "demo-presenter-01"
    auth = await sign_in(client, device)
    await seed_persona(device)  # the account has data (here a test-seeded persona) before the reset
    assert (await client.get("/v1/me", headers=auth)).json()["has_finance_data"] is True
    r = await client.post("/v1/me/reset", headers=auth)
    assert r.status_code == 200, r.text
    assert_no_persona("/v1/me/reset", r.json())
    await assert_no_data_everywhere(client, auth)
    await assert_penny_has_no_persona(client, auth)


async def test_new_player_after_play_gets_no_persona(client: httpx.AsyncClient) -> None:
    """New player = a new device id + POST /v1/auth/demo. Earlier data of another device never carries over."""
    from tests.integration.personas import seed_persona

    await sign_in(client, "old-device-0001")
    await seed_persona("old-device-0001")
    auth = await sign_in(client, "new-device-0002")
    await assert_no_data_everywhere(client, auth)


# ---------- the persona module is test-only ----------


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module)
            out |= {f"{node.module}.{a.name}" for a in node.names}
    return out


def test_no_production_module_imports_the_personas() -> None:
    offenders = []
    for pkg in PRODUCTION_PACKAGES:
        for path in (API_ROOT / pkg).rglob("*.py"):
            if PERSONA_PACKAGE in path.parents:
                continue
            if any(m == "lifeline_data.finance" or m.startswith("lifeline_data.finance.") for m in _imports(path)):
                offenders.append(str(path.relative_to(API_ROOT)))
    assert offenders == [], f"production code imports the test-only personas: {offenders}"


def test_hub_has_no_persona_path() -> None:
    from lifeline_data import hub

    assert "fixture_snapshot" not in vars(hub) and "DEMO_PERSONA_ID" not in vars(hub)
    assert len(PERSONA_IDS) == 4, "the 4 old personas stay for tests"
