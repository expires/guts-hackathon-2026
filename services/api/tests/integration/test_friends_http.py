"""Two demo devices add each other and see cards, never money amounts."""

from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx

from lifeline_contracts.accounts import Holding
from tests.integration.conftest import sign_in

MONEY_KEYS = ("pence", "amount", "balance", "value", "salary", "income")


def _keys(node: Any) -> set[str]:
    if isinstance(node, dict):
        return set(node) | {k for v in node.values() for k in _keys(v)}
    if isinstance(node, list):
        return {k for v in node for k in _keys(v)}
    return set()


async def _pair(client: httpx.AsyncClient) -> tuple[dict[str, str], dict[str, str], str]:
    a = await sign_in(client, "friends-device-a")
    b = await sign_in(client, "friends-device-b")
    code = (await client.post("/v1/friends/invite", headers=a)).json()["code"]
    return a, b, code


async def test_two_devices_add_each_other(client: httpx.AsyncClient) -> None:
    a, b, code = await _pair(client)
    assert (await client.post("/v1/friends/invite", headers=a)).json()["code"] == code
    r = await client.post("/v1/friends/join", json={"code": code.lower()}, headers=b)
    assert r.status_code == 200, r.text
    again = await client.post("/v1/friends/join", json={"code": code}, headers=b)
    assert again.status_code == 200 and again.json() == r.json()

    for headers in (a, b):
        board = (await client.get("/v1/friends", headers=headers)).json()
        assert len(board["entries"]) == 2
        assert [e["rank"] for e in board["entries"]] == [1, 2]
        assert sum(e["is_me"] for e in board["entries"]) == 1
        me = next(e for e in board["entries"] if e["is_me"])
        assert me["card"]["display_name"] == "You"
        other = next(e for e in board["entries"] if not e["is_me"])
        assert other["card"]["display_name"].startswith("Friend ")
        assert other["card"]["data_status"] == "mock"
        assert "mix" not in other["card"]
        assert "explain" in board

    removed = await client.delete(f"/v1/friends/{other['card']['friend_id']}", headers=b)
    assert removed.status_code == 200 and len(removed.json()["entries"]) == 1
    assert len((await client.get("/v1/friends", headers=a)).json()["entries"]) == 1


async def test_errors(client: httpx.AsyncClient) -> None:
    a, _, code = await _pair(client)
    r = await client.post("/v1/friends/join", json={"code": "ZZZZZZZZ"}, headers=a)
    assert r.status_code == 404 and r.json()["error"]["code"] == "invite_not_found"
    r = await client.post("/v1/friends/join", json={"code": code}, headers=a)
    assert r.status_code == 400 and r.json()["error"]["code"] == "cannot_add_self"
    assert (await client.get("/v1/friends")).status_code == 401
    new = (await client.post("/v1/friends/invite?rotate=true", headers=a)).json()["code"]
    assert new != code


async def test_share_mix_and_no_amounts_leak(client: httpx.AsyncClient) -> None:
    from lifeline_api import money
    from lifeline_api.auth import demo_subject
    from lifeline_api.main import app

    a, b, code = await _pair(client)
    await client.post("/v1/friends/join", json={"code": code}, headers=b)
    r = await client.put("/v1/friends/me", json={"display_name": "  Ash  ", "share_mix": True}, headers=a)
    assert r.status_code == 200 and r.json()["display_name"] == "Ash"
    blank = await client.put("/v1/friends/me", json={"display_name": " ", "share_mix": True}, headers=a)
    assert blank.status_code == 422

    seen = (await client.get("/v1/friends", headers=b)).json()
    ash = next(e for e in seen["entries"] if not e["is_me"])["card"]
    assert ash["display_name"] == "Ash"
    assert not [k for k in _keys(seen) if any(w in k for w in MONEY_KEYS)]
    assert (await client.get("/v1/friends/me", headers=a)).json() == ash

    # None of the owners' own snapshot amounts appear in any friends response.
    state = app.state.lifeline
    # Give A a portfolio so the shared mix is real, then check it is percentages only.
    sub_a = demo_subject("friends-device-a")
    snap = await money.snapshot(state, sub_a)
    held = [Holding(instrument_id="x", name="Fund", quantity=3, value=4321.0, asset_class="equity", region="US"),
            Holding(instrument_id="y", name="Bonds", quantity=1, value=1234.0, asset_class="bond")]
    state.memo[("snapshot", sub_a)] = (time.monotonic(), snap.model_copy(update={"holdings": held}))
    ash = next(e for e in (await client.get("/v1/friends", headers=b)).json()["entries"] if not e["is_me"])["card"]
    assert set(ash["mix"]) == {"equity", "bond"} and ash["growth_index"] > 0
    seen = (await client.get("/v1/friends", headers=b)).json()
    bodies = [
        json.dumps(seen),
        json.dumps((await client.get("/v1/friends", headers=a)).json()),
        json.dumps((await client.get("/v1/friends/me", headers=a)).json()),
    ]
    text = "\n".join(bodies)
    numbers = set(re.findall(r"\d+(?:\.\d+)?", text))
    for device in ("friends-device-a", "friends-device-b"):
        snap = await money.snapshot(state, demo_subject(device))
        amounts = {a.balance for a in snap.accounts} | {h.value for h in snap.holdings} | {4321.0, 1234.0}
        amounts |= {abs(t.amount) for t in snap.transactions}
        for amt in amounts:
            if amt >= 1000 or amt != int(amt):  # round small values collide with scores by chance
                assert f"{amt:.2f}".rstrip("0").rstrip(".") not in numbers
                assert str(amt) not in numbers
