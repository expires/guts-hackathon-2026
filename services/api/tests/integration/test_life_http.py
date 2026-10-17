"""Play a nurse-leeds life 2006 -> 2009 through the HTTP API, always taking the default choice."""

from __future__ import annotations

from typing import Any

import httpx

from tests.integration.conftest import sign_in


async def _answer_all(client: httpx.AsyncClient, auth: dict[str, str], life: dict[str, Any]) -> dict[str, Any]:
    while life["pending_events"]:
        ev = life["pending_events"][0]
        choice = next((c for c in ev["choices"] if c.get("is_default")), ev["choices"][0])
        r = await client.post(f"/v1/lives/{life['id']}/choices", json={"event_id": ev["id"], "choice_id": choice["id"]},
                              headers=auth)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["outcome"]["event_id"] == ev["id"]
        life = body["life"]
    return life


async def _play(client: httpx.AsyncClient, auth: dict[str, str], seed: int) -> dict[str, Any]:
    r = await client.post("/v1/lives", json={"mode": "preset", "preset_id": "nurse-leeds", "start_year": 2006,
                                             "seed": seed}, headers=auth)
    assert r.status_code == 201, r.text
    life = r.json()
    assert life["id"].startswith("lf_") and life["year"] == 2006 and life["seed"] == seed
    assert life["character"]["id"] == "nurse-leeds"
    life = await _answer_all(client, auth, life)
    for expected_year in (2007, 2008, 2009):
        r = await client.post(f"/v1/lives/{life['id']}/age", headers=auth)
        assert r.status_code == 200, r.text
        life = r.json()["life"]
        assert life["year"] == expected_year
        if life["pending_events"]:
            blocked = await client.post(f"/v1/lives/{life['id']}/age", headers=auth)
            assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "pending_events"
        life = await _answer_all(client, auth, life)
    return life


async def test_nurse_leeds_2006_to_2009(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client)
    life = await _play(client, auth, seed=424242)
    assert life["year"] == 2009 and life["alive"]

    stored = await client.get(f"/v1/lives/{life['id']}", headers=auth)
    assert stored.status_code == 200 and stored.json() == life

    s = await client.get(f"/v1/lives/{life['id']}/summary", headers=auth)
    assert s.status_code == 200, s.text
    summary = s.json()
    assert summary["life_id"] == life["id"]
    assert summary["net_worth"] == life["finances"]["net_worth"]


async def test_replay_is_deterministic(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client)
    a = await _play(client, auth, seed=7)
    b = await _play(client, auth, seed=7)
    assert a["id"] != b["id"]
    strip = ("id",)
    assert {k: v for k, v in a.items() if k not in strip} == {k: v for k, v in b.items() if k not in strip}
