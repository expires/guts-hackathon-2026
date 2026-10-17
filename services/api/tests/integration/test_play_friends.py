"""Play with friends (ADR 0059): lobby first, Money Quiz with 4 players, Same Decision, circles, privacy."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession

DEVICES = ["friends-host-01", "friends-guest-02", "friends-guest-03", "friends-guest-04"]
FORBIDDEN = {"balance", "amount", "income", "merchant", "description", "transactions", "accounts"}


@pytest.fixture
def tc(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("APP_ENV", "test")
    from lifeline_api import games

    monkeypatch.setattr(games, "REVEAL_PAUSE_SECONDS", 0.0)
    monkeypatch.setattr(games, "POLL_SECONDS", 0.02)
    from lifeline_api.main import app

    with TestClient(app) as c:
        yield c


def _token(tc: TestClient, device: str) -> str:
    return str(tc.post("/v1/auth/demo", json={"device_id": device}).json()["access_token"])


def _until(ws: WebSocketTestSession, kind: str, limit: int = 60) -> dict[str, Any]:
    for _ in range(limit):
        msg: dict[str, Any] = ws.receive_json()
        if msg["type"] == kind:
            return msg
        assert msg["type"] != "error", msg
    raise AssertionError(f"no {kind}")


def _lobby(tc: TestClient, tokens: list[str]) -> str:
    r = tc.post("/v1/rooms", json={}, headers={"Authorization": f"Bearer {tokens[0]}"})
    assert r.status_code == 201, r.text
    room = r.json()
    assert room["status"] == "lobby" and "game" not in room and room["max_players"] == 8
    assert room["players"][0]["name"] == "Player 1", "no display name yet: Player N"
    return str(room["code"])


def _join_all(sockets: list[WebSocketTestSession]) -> list[dict[str, Any]]:
    you = []
    for ws in sockets:
        ws.send_json({"type": "join"})
        you.append(_until(ws, "welcome")["you"])
    for ws in sockets:
        ws.send_json({"type": "ready"})
    for ws in sockets:
        for _ in range(40):
            players = _until(ws, "roster")["room"]["players"]
            if len(players) == len(sockets) and all(p["ready"] for p in players):
                break
    return you


def test_money_quiz_four_players(tc: TestClient) -> None:
    tokens = [_token(tc, d) for d in DEVICES]
    code = _lobby(tc, tokens)
    with (tc.websocket_connect(f"/v1/rooms/{code}?token={tokens[0]}") as w0,
          tc.websocket_connect(f"/v1/rooms/{code}?token={tokens[1]}") as w1,
          tc.websocket_connect(f"/v1/rooms/{code}?token={tokens[2]}") as w2,
          tc.websocket_connect(f"/v1/rooms/{code}?token={tokens[3]}") as w3):
        sockets = [w0, w1, w2, w3]
        you = _join_all(sockets)
        assert [y["name"] for y in you] == ["Player 1", "Player 2", "Player 3", "Player 4"]
        w1.send_json({"type": "pick_game", "game": "quiz"})
        err = w1.receive_json()
        while err["type"] != "error":
            err = w1.receive_json()
        assert err["error"]["code"] == "not_host"
        w0.send_json({"type": "pick_game", "game": "quiz", "options": {"questions": 3, "topic": "mixed"}})
        picked = [_until(ws, "game_picked")["room"] for ws in sockets]
        assert all(r["game"] == "quiz" and r["options"]["questions"] == 3 for r in picked)
        w0.send_json({"type": "start"})
        started = [_until(ws, "started")["room"] for ws in sockets]
        assert all(r["mode"] == "group" and r["status"] == "playing" for r in started)

        ever_right: set[str] = set()
        for qn in range(3):
            questions = [_until(ws, "question")["question"] for ws in sockets]
            q = questions[0]
            assert q["index"] == qn and q["total"] == 3 and q["source_label"] and q["answer_ms"] == 15_000
            assert all(x == q for x in questions)
            # Player 1 answers the first choice; the others the second (one of them is likely right).
            for i, ws in enumerate(sockets):
                ws.send_json({"type": "answer", "question_id": q["id"], "choice_id": q["choices"][min(i, 1)]["id"]})
            reveals = [_until(ws, "quiz_reveal")["quiz_reveal"] for ws in sockets]
            rv = reveals[0]
            assert rv["question_id"] == q["id"] and rv["explanation"] and rv["source_label"]
            ranks = [r["rank"] for r in rv["ranking"]]
            assert ranks == sorted(ranks) and len(rv["ranking"]) == 4
            chosen = {y["id"]: q["choices"][min(i, 1)]["id"] for i, y in enumerate(you)}
            for r in rv["ranking"]:
                assert r["last_correct"] == (chosen[r["player_id"]] == rv["correct_choice_id"])
                if r["last_correct"]:
                    ever_right.add(r["player_id"])
        final = [_until(ws, "ranking")["ranking"] for ws in sockets]
        assert all(f == final[0] for f in final) and len(final[0]) == 4
        for f in final[0]:
            assert (f["score"] >= 100) == (f["player_id"] in ever_right), "100 points per correct answer"
        done = _until(w0, "finished")["room"]
        assert done["status"] == "finished"


def test_quiz_answer_rules(tc: TestClient) -> None:
    tokens = [_token(tc, d) for d in DEVICES[:2]]
    code = _lobby(tc, tokens)
    with (tc.websocket_connect(f"/v1/rooms/{code}?token={tokens[0]}") as w0,
          tc.websocket_connect(f"/v1/rooms/{code}?token={tokens[1]}") as w1):
        _join_all([w0, w1])
        w0.send_json({"type": "pick_game", "game": "quiz", "options": {"questions": 3}})
        _until(w0, "game_picked")
        w0.send_json({"type": "start"})
        assert _until(w0, "started")["room"]["mode"] == "duel", "2 players = duel"
        q = _until(w0, "question")["question"]
        w0.send_json({"type": "answer", "question_id": q["id"], "choice_id": "nope"})
        bad = w0.receive_json()
        while bad["type"] != "error":
            bad = w0.receive_json()
        assert bad["error"]["code"] == "invalid_choice"
        w0.send_json({"type": "answer", "question_id": q["id"], "choice_id": q["choices"][0]["id"]})
        w0.send_json({"type": "answer", "question_id": q["id"], "choice_id": q["choices"][1]["id"]})
        dup = w0.receive_json()
        while dup["type"] != "error":
            dup = w0.receive_json()
        assert dup["error"]["code"] == "already_answered"


def test_same_decision_until_content_lands(tc: TestClient) -> None:
    from lifeline_sim import api as sim_api

    tokens = [_token(tc, d) for d in DEVICES[:2]]
    code = _lobby(tc, tokens)
    with (tc.websocket_connect(f"/v1/rooms/{code}?token={tokens[0]}") as w0,
          tc.websocket_connect(f"/v1/rooms/{code}?token={tokens[1]}") as w1):
        _join_all([w0, w1])
        w0.send_json({"type": "pick_game", "game": "same_decision", "options": {"start_year": 2008}})
        _until(w0, "game_picked")
        w0.send_json({"type": "start"})
        if not hasattr(sim_api, "decision_prompts"):
            msg = w0.receive_json()
            while msg["type"] != "error":
                msg = w0.receive_json()
            assert msg["error"]["code"] == "game_unavailable"
            return
        pr = _until(w0, "decision")["decision"]
        for ws in (w0, w1):
            ws.send_json({"type": "answer", "question_id": pr["id"], "choice_id": pr["options"][0]["id"]})
        rv = _until(w1, "decision_reveal")["decision_reveal"]
        assert rv["penny_line"] and len(rv["choices"]) == 2 and rv["outcomes"]


def _walk(node: Any, path: str = "") -> list[tuple[str, Any]]:
    if isinstance(node, dict):
        return [x for k, v in node.items() for x in _walk(v, f"{path}.{k}")] + [(f"{path}.{k}", None) for k in node]
    if isinstance(node, list):
        return [x for i, v in enumerate(node) for x in _walk(v, f"{path}[{i}]")]
    return [(path, node)]


def test_circles_share_ratios_only(tc: TestClient) -> None:
    a, b = _token(tc, "circle-device-01"), _token(tc, "circle-device-02")
    ha, hb = {"Authorization": f"Bearer {a}"}, {"Authorization": f"Bearer {b}"}
    assert tc.post("/v1/samples/rich/import", headers=ha).status_code == 201
    assert tc.post("/v1/samples/scholarship/import", headers=hb).status_code == 201
    personal = {round(abs(float(v)), 2) for _, v in _walk(tc.get("/v1/finance/overview", headers=ha).json())
                if isinstance(v, int | float) and abs(v) >= 1}
    r = tc.post("/v1/circles", json={"name": "Flat 4"}, headers=ha)
    assert r.status_code == 201, r.text
    circle = r.json()
    assert len(circle["members"]) == 1 and circle["members"][0]["is_you"]
    joined = tc.post("/v1/circles/join", json={"code": circle["code"]}, headers=hb)
    assert joined.status_code == 200 and len(joined.json()["members"]) == 2
    assert tc.post("/v1/circles/join", json={"code": "ZZZZZZ"}, headers=hb).status_code == 404
    listed = tc.get("/v1/circles", headers=ha).json()["circles"]
    assert [c["id"] for c in listed] == [circle["id"]]
    c = listed[0]
    assert all(m["improvement"] == 0 and m["rank"] == 1 for m in c["members"]), "first score is the baseline"
    assert c["recap"] and c["recap_week"]
    for path, value in _walk(c):
        key = path.rsplit(".", 1)[-1].split("[")[0]
        assert key not in FORBIDDEN, path
        if isinstance(value, float) and abs(value) >= 1:
            assert round(abs(value), 2) not in personal, path
    assert "£" not in str(c)
    assert tc.post(f"/v1/circles/{circle['id']}/leave", headers=hb).status_code == 204
    assert tc.post(f"/v1/circles/{circle['id']}/leave", headers=hb).status_code == 404
    assert tc.post("/v1/me/reset", headers=ha).status_code == 200
    assert tc.post("/v1/circles/join", json={"code": circle["code"]}, headers=hb).status_code == 404, \
        "the last member out deletes the circle"


def test_paths_and_quick_life_room(tc: TestClient) -> None:
    tokens = [_token(tc, d) for d in DEVICES[:2]]
    auths = [{"Authorization": f"Bearer {t}"} for t in tokens]
    paths = tc.get("/v1/paths", headers=auths[0]).json()["paths"]
    assert any(p["id"] == "uni" and p["quick"] for p in paths)
    code = _lobby(tc, tokens)
    with (tc.websocket_connect(f"/v1/rooms/{code}?token={tokens[0]}") as w0,
          tc.websocket_connect(f"/v1/rooms/{code}?token={tokens[1]}") as w1):
        _join_all([w0, w1])
        w0.send_json({"type": "pick_game", "game": "same_life", "options": {"path_id": "uni", "quick": True}})
        _until(w0, "game_picked")
        w0.send_json({"type": "start"})
        room = _until(w0, "started")["room"]
        _until(w1, "started")
        lives = []
        for a in auths:
            r = tc.post("/v1/lives", json={"mode": "random", "start_year": 2015, "path_id": "uni", "quick": True,
                                           "seed": 1, "room_code": code}, headers=a)
            assert r.status_code == 201, r.text
            lives.append(r.json())
        assert lives[0]["seed"] == lives[1]["seed"] == room["seed"], "the room owns the seed"
        assert lives[0]["character"]["birth_year"] == lives[1]["character"]["birth_year"]
        w1.send_json({"type": "progress", "life_id": lives[1]["id"]})
        rival = _until(w0, "rival")["player"]
        assert rival["life_id"] == lives[1]["id"] and rival["age"] == lives[1]["age"]
        life = lives[0]
        for _ in range(10):
            for ev in life["pending_events"]:
                ch = next((x for x in ev["choices"] if x.get("is_default")), ev["choices"][0])
                life = tc.post(f"/v1/lives/{life['id']}/choices", json={"event_id": ev["id"], "choice_id": ch["id"]},
                               headers=auths[0]).json()["life"]
            if life["age"] >= 25:
                break
            life = tc.post(f"/v1/lives/{life['id']}/age", headers=auths[0]).json()["life"]
        summary = tc.get(f"/v1/lives/{life['id']}/summary", headers=auths[0]).json()
        assert "habit_score" in summary
        over = tc.post(f"/v1/lives/{life['id']}/age", headers=auths[0])
        assert over.status_code == 409 and over.json()["error"] == {
            "code": "finished", "message": "This Quick Life is over", "source": "sim"}
        other = tc.post("/v1/lives", json={"mode": "random", "start_year": 2015, "path_id": "uni", "quick": True,
                                           "room_code": "ZZZZZZ"}, headers=auths[0])
        assert other.status_code == 404


def test_every_offered_character_starts_a_life(tc: TestClient) -> None:
    auth = {"Authorization": f"Bearer {_token(tc, 'characters-device-01')}"}
    chars = tc.get("/v1/characters", params={"seed": 7}).json()
    assert chars["presets"]
    for p in chars["presets"]:
        start = max(2010, p["birth_year"] + 18)
        r = tc.post("/v1/lives", json={"mode": "preset", "preset_id": p["id"], "start_year": min(2024, start),
                                       "seed": 3}, headers=auth)
        assert r.status_code == 201, (p["id"], r.text)
    rnd = chars["random"]
    r = tc.post("/v1/lives", json={"mode": "random", "start_year": min(2026, rnd["birth_year"] + 25), "seed": 7},
                headers=auth)
    assert r.status_code == 201, r.text


def test_shared_names_are_cleaned_and_unique(tc: TestClient) -> None:
    a, b, c = (_token(tc, d) for d in ("names-device-01", "names-device-02", "names-device-03"))
    ha, hb, hc = ({"Authorization": f"Bearer {t}"} for t in (a, b, c))
    r = tc.post("/v1/circles", json={"name": "Flat 4 <b>£</b>‮"}, headers=ha)
    assert r.status_code == 201 and r.json()["name"] == "Flat 4 b£/b"
    assert tc.post("/v1/circles", json={"name": "‮​"}, headers=ha).status_code == 422
    circle = r.json()
    for h in (hb, hc):
        assert tc.post("/v1/circles/join", json={"code": circle["code"]}, headers=h).status_code == 200
    assert tc.post(f"/v1/circles/{circle['id']}/leave", headers=hb).status_code == 204
    assert tc.post("/v1/circles/join", json={"code": circle["code"]}, headers=hb).status_code == 200
    members = tc.get("/v1/circles", headers=ha).json()["circles"][0]["members"]
    names = [m["name"] for m in members]
    assert len(names) == len(set(names)) == 3, names
    recap = tc.get("/v1/circles", headers=ha).json()["circles"][0].get("recap") or ""
    assert "+0" not in recap

    code = _lobby(tc, [a])
    with tc.websocket_connect(f"/v1/rooms/{code}?token={b}") as ws:
        ws.send_json({"type": "join", "name": "Ben‮<i>x</i>"})
        you = _until(ws, "welcome")["you"]
        assert you["name"] == "Beni x/i" or "‮" not in you["name"] and "<" not in you["name"]


def test_wrong_circle_codes_are_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AUTH_RATE_LIMIT_PER_MINUTE", "3")
    from lifeline_api.main import app

    with TestClient(app) as c:
        h = {"Authorization": f"Bearer {_token(c, 'guess-device-01')}"}
        codes = [c.post("/v1/circles/join", json={"code": f"ZZZZZ{i}"}, headers=h).status_code for i in range(5)]
        assert codes[:2] == [404, 404] and 429 in codes
