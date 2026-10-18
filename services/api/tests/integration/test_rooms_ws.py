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
        rival_life = life_ids[you[1]["id"]]
        host = {"Authorization": f"Bearer {tokens[0]}"}
        assert tc.get(f"/v1/lives/{rival_life}", headers=host).status_code == 200, "room members can read"
        assert tc.get(f"/v1/lives/{rival_life}/summary", headers=host).status_code == 200
        assert tc.post(f"/v1/lives/{rival_life}/age", headers=host).status_code == 404, "but never play it"
        outsider = {"Authorization": f"Bearer {_token(tc, 'room-outsider-01')}"}
        assert tc.get(f"/v1/lives/{rival_life}", headers=outsider).status_code == 404
        assert tc.get(f"/v1/lives/{rival_life}/summary", headers=outsider).status_code == 404

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
    missing = "9999" if code != "9999" else "9998"
    with tc.websocket_connect(f"/v1/rooms/{missing}?token={tokens[0]}") as ws:
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


def test_room_lives_hidden_after_room_expires(tc: TestClient) -> None:
    from lifeline_api.main import app

    host, guest = _token(tc, DEVICES[0]), _token(tc, DEVICES[1])
    code = tc.post("/v1/rooms", json={"mode": "duel", "host_name": "Ana", "preset_id": "nurse-leeds",
                                      "start_year": 2006}, headers={"Authorization": f"Bearer {host}"}).json()["code"]
    with (tc.websocket_connect(f"/v1/rooms/{code}?token={host}") as w0,
          tc.websocket_connect(f"/v1/rooms/{code}?token={guest}") as w1):
        w0.send_json({"type": "join", "name": "Ana"})
        _until(w0, "welcome")
        w1.send_json({"type": "join", "name": "Ben"})
        guest_id = _until(w1, "welcome")["you"]["id"]
        for ws in (w0, w1):
            ws.send_json({"type": "ready"})
        for _ in range(10):
            if all(p["ready"] for p in _until(w0, "roster")["room"]["players"]):
                break
        w0.send_json({"type": "start"})
        room = _until(w0, "started")["room"]
    guest_life = next(p["life_id"] for p in room["players"] if p["id"] == guest_id)
    auth = {"Authorization": f"Bearer {host}"}
    assert tc.get(f"/v1/lives/{guest_life}", headers=auth).status_code == 200
    rooms = app.state.lifeline.rooms
    tc.portal.call(rooms.redis.delete, f"lifeline:room:{code}")  # the 24 h TTL ran out
    assert tc.get(f"/v1/lives/{guest_life}", headers=auth).status_code == 404
    assert tc.get(f"/v1/lives/{guest_life}", headers={"Authorization": f"Bearer {guest}"}).status_code == 200


def test_four_digit_codes_and_wrong_code_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """V6 final F-1 and V3 final: wrong codes are limited per account (and per IP only as a high flood guard),
    separate from sign-in; a seated player is never blocked; a fake X-Forwarded-For does not reset the count."""
    import re

    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("WRONG_CODE_PER_MINUTE", "3")
    from lifeline_api.main import app

    with TestClient(app) as c:
        tok = _token(c, "code-guess-0001")
        h = {"Authorization": f"Bearer {tok}"}
        codes = {c.post("/v1/rooms", json={}, headers=h).json()["code"] for _ in range(5)}
        assert all(re.fullmatch(r"[0-9]{4}", x) for x in codes) and len(codes) == 5
        assert all(c.get(f"/v1/rooms/{x}", headers=h).json()["join_url"] == f"lifeline://join/{x}" for x in codes)
        outsider = {"Authorization": f"Bearer {_token(c, 'code-guess-0003')}"}
        view = c.get(f"/v1/rooms/{next(iter(codes))}", headers=outsider).json()
        assert [p["name"] for p in view["players"]] == ["Player 1"] and "life_id" not in view["players"][0]
        assert view["players"][0]["id"] == "seat-1", "no real player ids for someone without a seat"
        wrong = [f"{n:04d}" for n in range(10_000) if f"{n:04d}" not in codes][:6]
        statuses = [c.get(f"/v1/rooms/{x}", headers={**h, "x-forwarded-for": f"9.9.9.{i}"}).status_code
                    for i, x in enumerate(wrong)]
        assert statuses[:3] == [404, 404, 404] and statuses[3:] == [429, 429, 429]
        r = c.get(f"/v1/rooms/{wrong[0]}", headers=h)
        assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1
        mine = next(iter(codes))
        assert c.get(f"/v1/rooms/{mine}", headers=h).status_code == 200, "a seated player is never blocked"
        with c.websocket_connect(f"/v1/rooms/{wrong[0]}?token={tok}") as ws:
            ws.send_json({"type": "join"})
            assert _until_error(ws) == "rate_limited"
        # Another account on the same Wi-Fi is not blocked by this account's mistakes (venue risk).
        other = {"Authorization": f"Bearer {_token(c, 'code-guess-0002')}"}
        assert c.get(f"/v1/rooms/{wrong[1]}", headers=other).status_code == 404


def test_rooms_with_redis_down(tc: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """V3 F2: REST answers 503 in the error format; the WebSocket says so and closes cleanly."""
    from lifeline_api.main import app

    tok = _token(tc, DEVICES[0])
    h = {"Authorization": f"Bearer {tok}"}
    code = tc.post("/v1/rooms", json={}, headers=h).json()["code"]
    inner = app.state.lifeline.rooms.redis._inner

    async def down(*a: object, **k: object) -> None:
        raise ConnectionError("redis down")

    for name in ("get", "set", "publish", "sadd", "smembers", "delete", "expire"):
        monkeypatch.setattr(inner, name, down)
    r = tc.post("/v1/rooms", json={}, headers=h)
    assert r.status_code == 503 and r.json()["error"]["code"] == "rooms_unavailable"
    r = tc.get(f"/v1/rooms/{code}", headers=h)
    assert r.status_code == 503 and r.json()["error"] == {
        "code": "rooms_unavailable", "message": r.json()["error"]["message"], "source": "rooms"}
    with tc.websocket_connect(f"/v1/rooms/{code}?token={tok}") as ws:
        ws.send_json({"type": "join"})
        assert _until_error(ws) == "rooms_unavailable"



def test_ip_flood_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("WRONG_CODE_IP_PER_MINUTE", "4")
    from lifeline_api.main import app

    with TestClient(app) as c:
        heads = [{"Authorization": f"Bearer {_token(c, f'flood-device-{i:02d}')}"} for i in range(3)]
        statuses = [c.get(f"/v1/rooms/{9990 + i}", headers=heads[i % 3]).status_code for i in range(6)]
        assert statuses[:4] == [404] * 4 and statuses[4:] == [429, 429], "many accounts, one address: flood guard"


def test_rooms_recover_right_after_redis_returns(tc: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """V3 final: the first failure resets the pool; the next call after Redis is back works at once."""
    from lifeline_api.main import app

    h = {"Authorization": f"Bearer {_token(tc, DEVICES[0])}"}
    guarded = app.state.lifeline.rooms.redis
    inner = guarded._inner
    resets: list[bool] = []
    pool = inner.connection_pool
    real_disconnect = pool.disconnect

    async def disconnect(*a: object, **k: object) -> None:
        resets.append(True)
        await real_disconnect(*a, **k)

    monkeypatch.setattr(pool, "disconnect", disconnect)
    real_set = inner.set

    async def down(*a: object, **k: object) -> None:
        raise ConnectionError("redis down")

    monkeypatch.setattr(inner, "set", down)
    assert tc.post("/v1/rooms", json={}, headers=h).status_code == 503
    assert resets, "the pool is reset on the first failure"
    monkeypatch.setattr(inner, "set", real_set)  # Redis is back
    assert tc.post("/v1/rooms", json={}, headers=h).status_code == 201


def test_host_start_counts_as_host_ready(tc: TestClient) -> None:
    """The app shows the host as ready and never sends `ready` for the host; Start must still work."""
    host, guest = _token(tc, DEVICES[0]), _token(tc, DEVICES[1])
    code = tc.post("/v1/rooms", json={"mode": "duel", "host_name": "Ana"},
                   headers={"Authorization": f"Bearer {host}"}).json()["code"]
    with (tc.websocket_connect(f"/v1/rooms/{code}?token={host}") as w0,
          tc.websocket_connect(f"/v1/rooms/{code}?token={guest}") as w1):
        w0.send_json({"type": "join", "name": "Ana"})
        _until(w0, "welcome")
        w1.send_json({"type": "join", "name": "Ben"})
        _until(w1, "welcome")
        w0.send_json({"type": "pick_game", "game": "quiz", "options": {"questions": 3}})
        _until(w0, "game_picked")
        w1.send_json({"type": "ready"})
        _until(w1, "roster")
        w0.send_json({"type": "start"})
        assert _until(w1, "started")["room"]["status"] == "playing"
        assert _until(w1, "question")["question"]["total"] == 3
