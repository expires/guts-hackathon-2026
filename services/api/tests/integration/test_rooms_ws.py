"""Same Life rooms with 4 simulated clients over WebSocket (ADR 0029 part 3)."""

from __future__ import annotations

import base64
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession

DEVICES = ["room-host-0001", "room-guest-0002", "room-guest-0003", "room-guest-0004"]


@pytest.fixture
def tc(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("APP_ENV", "test")
    from lifeline_api.main import app

    with TestClient(app) as c:
        yield c


def _token(tc: TestClient, device: str) -> str:
    r = tc.post("/v1/auth/demo", json={"device_id": device})
    assert r.status_code == 200
    return str(r.json()["access_token"])


def _until(ws: WebSocketTestSession, kind: str, limit: int = 30) -> dict[str, Any]:
    """Read messages until one of `kind` arrives (rosters and rivals from others may come first)."""
    for _ in range(limit):
        msg: dict[str, Any] = ws.receive_json()
        if msg["type"] == kind:
            return msg
        assert msg["type"] != "error", msg
    raise AssertionError(f"no {kind} message")


def _until_error(ws: WebSocketTestSession, limit: int = 30) -> str:
    for _ in range(limit):
        msg: dict[str, Any] = ws.receive_json()
        if msg["type"] == "error":
            return str(msg["error"]["code"])
    raise AssertionError("no error message")


def _age_and_clear(tc: TestClient, token: str, life_id: str) -> dict[str, Any]:
    auth = {"Authorization": f"Bearer {token}"}
    life = tc.post(f"/v1/lives/{life_id}/age", headers=auth).json()["life"]
    for ev in life["pending_events"]:
        choice = next((c for c in ev["choices"] if c.get("is_default")), ev["choices"][0])
        life = tc.post(f"/v1/lives/{life_id}/choices", json={"event_id": ev["id"], "choice_id": choice["id"]},
                       headers=auth).json()["life"]
    return dict(life)


def test_four_players_full_game(tc: TestClient) -> None:
    tokens = [_token(tc, d) for d in DEVICES]
    r = tc.post("/v1/rooms", json={"mode": "group", "host_name": "Ana", "preset_id": "nurse-leeds",
                                   "start_year": 2006}, headers={"Authorization": f"Bearer {tokens[0]}"})
    assert r.status_code == 201, r.text
    room = r.json()
    code = room["code"]
    assert room["join_url"] == f"lifeline://join/{code}" and room["status"] == "lobby"
    assert base64.b64decode(room["qr_png_base64"]).startswith(b"\x89PNG\r\n\x1a\n")

    names = ["Ana", "Ben", "Cat", "Dev"]
    with (tc.websocket_connect(f"/v1/rooms/{code}?token={tokens[0]}") as w0,
          tc.websocket_connect(f"/v1/rooms/{code}?token={tokens[1]}") as w1,
          tc.websocket_connect(f"/v1/rooms/{code}?token={tokens[2]}") as w2,
          tc.websocket_connect(f"/v1/rooms/{code}?token={tokens[3]}") as w3):
        sockets = [w0, w1, w2, w3]
        you: list[dict[str, Any]] = []
        for ws, name in zip(sockets, names, strict=True):
            ws.send_json({"type": "join", "name": name})
            you.append(_until(ws, "welcome")["you"])
        assert you[0]["is_host"] and not any(y["is_host"] for y in you[1:])
        assert len({y["id"] for y in you}) == 4

        w0.send_json({"type": "start"})
        assert _until_error(w0) == "not_ready"

        for ws in sockets:
            ws.send_json({"type": "ready"})
        # Each client sees the roster with everyone ready.
        for ws in sockets:
            for _ in range(30):
                roster = _until(ws, "roster")
                if all(p["ready"] for p in roster["room"]["players"]) and len(roster["room"]["players"]) == 4:
                    break
            else:
                raise AssertionError("not all ready")

        w0.send_json({"type": "start"})
        started = [_until(ws, "started")["room"] for ws in sockets]
        assert all(s["status"] == "playing" for s in started)
        life_ids = {p["id"]: p["life_id"] for p in started[0]["players"]}
        assert all(life_ids.values()) and len(set(life_ids.values())) == 4

        seeds = set()
        for i, y in enumerate(you):
            life = tc.get(f"/v1/lives/{life_ids[y['id']]}", headers={"Authorization": f"Bearer {tokens[i]}"}).json()
            seeds.add(life["seed"])
            assert life["room_code"] == code
        assert seeds == {room["seed"]}, "the server owns one seed for the room"
        other = tc.get(f"/v1/lives/{life_ids[you[1]['id']]}", headers={"Authorization": f"Bearer {tokens[0]}"})
        assert other.status_code == 404, "each life belongs to its player"

        # Player 1 ages; everyone gets a rival update with the server's numbers.
        life = _age_and_clear(tc, tokens[1], life_ids[you[1]["id"]])
        w1.send_json({"type": "progress", "net_worth": 99_999_999})
        for ws in sockets:
            rival = _until(ws, "rival")["player"]
            assert rival["id"] == you[1]["id"] and rival["year"] == life["year"]
            assert rival["net_worth"] == round(life["finances"]["net_worth"], 2), "client numbers are ignored"

        for ws in sockets:
            ws.send_json({"type": "finish"})
        results = [_until(ws, "finished")["room"] for ws in sockets]
        assert all(r["status"] == "finished" for r in results)
        assert all(p["finished"] for p in results[0]["players"])

    after = tc.get(f"/v1/rooms/{code}", headers={"Authorization": f"Bearer {tokens[0]}"}).json()
    assert after["status"] == "finished" and not any(p["connected"] for p in after["players"])


def test_reconnect_keeps_the_seat(tc: TestClient) -> None:
    host, guest = _token(tc, DEVICES[0]), _token(tc, DEVICES[1])
    code = tc.post("/v1/rooms", json={"mode": "duel", "host_name": "Ana", "preset_id": "nurse-leeds",
                                      "start_year": 2006}, headers={"Authorization": f"Bearer {host}"}).json()["code"]
    with tc.websocket_connect(f"/v1/rooms/{code}?token={host}") as w0:
        w0.send_json({"type": "join", "name": "Ana"})
        _until(w0, "welcome")
        with tc.websocket_connect(f"/v1/rooms/{code}?token={guest}") as w1:
            w1.send_json({"type": "join", "name": "Ben"})
            pid = _until(w1, "welcome")["you"]["id"]
        # Guest dropped (phone slept): the host sees them disconnected, seat kept.
        for _ in range(10):
            players = {p["id"]: p for p in _until(w0, "roster")["room"]["players"]}
            if pid in players and not players[pid]["connected"]:
                break
        else:
            raise AssertionError("host never saw the guest disconnect")
        with tc.websocket_connect(f"/v1/rooms/{code}?token={guest}") as w1:
            w1.send_json({"type": "join", "player_id": pid})
            back = _until(w1, "welcome")["you"]
            assert back["id"] == pid and back["connected"] and back["name"] == "Ben"
            assert len(_until(w0, "roster")["room"]["players"]) == 2


def test_room_rules(tc: TestClient) -> None:
    tokens = [_token(tc, d) for d in DEVICES[:3]]
    code = tc.post("/v1/rooms", json={"mode": "duel", "host_name": "Ana", "preset_id": "nurse-leeds",
                                      "start_year": 2006}, headers={"Authorization": f"Bearer {tokens[0]}"}
                   ).json()["code"]
    with tc.websocket_connect(f"/v1/rooms/{code}?token=bad") as ws:
        assert ws.receive_json()["error"]["code"] == "unauthorized"
    with tc.websocket_connect(f"/v1/rooms/ZZZZZZ?token={tokens[0]}") as ws:
        ws.send_json({"type": "join", "name": "X"})
        assert _until_error(ws) == "not_found"
    with (tc.websocket_connect(f"/v1/rooms/{code}?token={tokens[0]}") as w0,
          tc.websocket_connect(f"/v1/rooms/{code}?token={tokens[1]}") as w1,
          tc.websocket_connect(f"/v1/rooms/{code}?token={tokens[2]}") as w2):
        w0.send_json({"type": "ready"})
        assert _until_error(w0) == "join_first"
        w0.send_json({"type": "join", "name": "Ana"})
        _until(w0, "welcome")
        w1.send_json({"type": "join", "name": "Ben"})
        _until(w1, "welcome")
        w2.send_json({"type": "join", "name": "Cat"})
        assert _until_error(w2) == "room_full", "a duel has 2 seats"
        w1.send_json({"type": "start"})
        assert _until_error(w1) == "not_host"
        w0.send_json({"type": "start"})
        assert _until_error(w0) == "not_ready"
        w0.send_json({"type": "ping"})
        assert _until(w0, "pong")["type"] == "pong"
        w0.send_json({"type": "bogus"})
        assert _until_error(w0) == "validation_error"
