"""Penny on game screens, W4 side: the server loads the Life event or room round into the chat context.

Penny (W5) is replaced by a fake that records the context. Rules checked here:
- a new thread takes its title from ChatContext.title;
- a Life event: the event, its choices and their engine game numbers are loaded;
- a room round: only for a player in that room; before the reveal no outcome or game money; an open quiz question
  never carries its answer.
"""

from __future__ import annotations

import base64
import json
from typing import Any

import httpx
import pytest

from lifeline_api.rooms import RoomDoc
from lifeline_contracts.chat import ChatBubble, ChatRequest, ChatResponse
from lifeline_explain.chat_tools import ChatToolContext
from tests.integration.conftest import sign_in

SEEN: list[ChatToolContext] = []

DECISION = {
    "prompt": {"id": "sd_2008_1", "year": 2008, "context": "Bank Rate was 5% before the crash.",
               "text": "You have £1,000 of game money. What do you do?",
               "options": [{"id": "save", "label": "Save it"}, {"id": "spend", "label": "Buy a laptop"}],
               "answer_ms": 20000},
    "outcomes": [{"option_id": "save", "game_money_change": 47.5, "note": "Savings rates were high"},
                 {"option_id": "spend", "game_money_change": -1000.0, "note": "The laptop lost value"}],
    "penny_line": "In 2008, “Save it” came out best in game money.",
}  # fmt: skip
QUIZ = {
    "question": {"id": "q_loan_1", "index": 0, "total": 3, "text": "When do Plan 5 student loan repayments start?",
                 "choices": [{"id": "a", "text": "Over £25,000 a year"}, {"id": "b", "text": "From the first pay"}],
                 "answer_ms": 15000, "source_label": "gov.uk"},
    "correct": "a",
    "explanation": "Repayments start once you earn over the threshold.",
}  # fmt: skip


async def fake_answer(req: ChatRequest, ctx: ChatToolContext) -> ChatResponse:
    SEEN.append(ctx)
    return ChatResponse(thread_id=ctx.thread_id or "", message_id="pm_1", reply_to=ctx.user_message_id or "",
                        reaction="brain", bubbles=[ChatBubble(id="b1", kind="answer", text="ok")], confidence=0.9,
                        verified=True)  # fmt: skip


@pytest.fixture(autouse=True)
def fake_penny(monkeypatch: pytest.MonkeyPatch) -> None:
    from lifeline_api.routes import chat as chat_routes

    SEEN.clear()
    monkeypatch.setattr(chat_routes.penny, "answer", fake_answer)


def _sub(auth: dict[str, str]) -> str:
    payload = auth["Authorization"].split()[1].split(".")[1]
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    return str(claims["sub"])


async def _room(code: str, player_sub: str, kind: str, item: dict[str, Any], round_: int) -> None:
    from lifeline_api.main import app

    doc = RoomDoc(code=code, mode="group", seed=7, preset_id=None, start_year=2008, max_players=8, status="playing",
                  game="quiz" if kind == "quiz" else "same_decision")  # fmt: skip
    doc.add_player(player_sub, "Sam", host=True)
    doc.add_player("someone-else", "Alex")
    doc.game_state = {"kind": kind, "items": [item], "round": round_, "round_id": None, "scores": {}}
    await app.state.lifeline.rooms.put(doc)


def _ask_room(code: str, round_id: str) -> dict[str, Any]:
    return {"message": "Which option should I pick?",
            "context": {"screen": "room_round", "room_code": code, "round_id": round_id, "multiplayer": True,
                        "title": "Same Decision, 2008"}}  # fmt: skip


async def test_new_thread_title_from_context(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "game-title-0001")
    body = {"message": "Explain this simply", "context": {"screen": "why", "title": "Safety fund, age 19"}}
    r = await client.post("/v1/chat", json=body, headers=auth)
    assert r.status_code == 200, r.text
    thread = (await client.get(f"/v1/chat/threads/{r.json()['thread_id']}", headers=auth)).json()
    assert thread["title"] == "Safety fund, age 19"


async def test_room_outsider_gets_no_round_data(client: httpx.AsyncClient) -> None:
    owner = await sign_in(client, "game-room-owner-01")
    outsider = await sign_in(client, "game-room-outsider-01")
    await _room("4821", _sub(owner), "decision", DECISION, round_=1)  # revealed: outcomes exist in the room
    r = await client.post("/v1/chat", json=_ask_room("4821", "sd_2008_1"), headers=outsider)
    assert r.status_code == 200, r.text
    assert SEEN[-1].scene is None, "a non-player never sees the room's round"
    r = await client.post("/v1/chat", json=_ask_room("9999", "sd_2008_1"), headers=owner)
    assert r.status_code == 200 and SEEN[-1].scene is None, "an unknown room is not an error and gives nothing"


async def test_room_decision_before_reveal_has_no_outcomes(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "game-room-player-01")
    await _room("5310", _sub(auth), "decision", DECISION, round_=0)
    r = await client.post("/v1/chat", json=_ask_room("5310", "sd_2008_1"), headers=auth)
    assert r.status_code == 200, r.text
    scene = SEEN[-1].scene
    assert scene is not None and not scene.revealed and scene.options == ("Save it", "Buy a laptop")
    sent = json.dumps(scene.output.model_dump(mode="json"))
    assert "outcomes" not in sent and "47.5" not in sent and "Savings rates were high" not in sent
    assert not any("game_money" in f.id for f in scene.output.facts)
    assert "came out best" not in sent

    await _room("5311", _sub(auth), "decision", DECISION, round_=1)
    await client.post("/v1/chat", json=_ask_room("5311", "sd_2008_1"), headers=auth)
    after = SEEN[-1].scene
    assert after is not None and after.revealed
    assert {f.id: f.value for f in after.output.facts if "game_money" in f.id} == {
        "room.save.game_money_change": 47.5, "room.spend.game_money_change": -1000.0}


async def test_open_quiz_question_never_carries_the_answer(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "game-quiz-player-01")
    await _room("6120", _sub(auth), "quiz", QUIZ, round_=0)
    r = await client.post("/v1/chat", json=_ask_room("6120", "q_loan_1"), headers=auth)
    assert r.status_code == 200, r.text
    scene = SEEN[-1].scene
    assert scene is not None and scene.quiz_open
    sent = json.dumps(scene.output.model_dump(mode="json"))
    assert "correct" not in sent and "threshold" not in sent and '"a"' not in sent

    await _room("6121", _sub(auth), "quiz", QUIZ, round_=1)
    await client.post("/v1/chat", json=_ask_room("6121", "q_loan_1"), headers=auth)
    after = SEEN[-1].scene
    assert after is not None and not after.quiz_open
    assert after.output.result["correct_choice"] == "Over £25,000 a year"


async def test_life_event_scene_has_choices_and_game_numbers(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "game-life-event-01")
    r = await client.post("/v1/lives", json={"mode": "preset", "preset_id": "nurse-leeds", "start_year": 2006,
                                             "seed": 4}, headers=auth)  # fmt: skip
    life = r.json()
    for _ in range(4):
        if life["pending_events"]:
            break
        life = (await client.post(f"/v1/lives/{life['id']}/age", headers=auth)).json()["life"]
    ev = life["pending_events"][0]
    body = {"message": "Which option should I pick?",
            "context": {"screen": "life_event", "life_id": life["id"], "event_id": ev["id"]}}  # fmt: skip
    r = await client.post("/v1/chat", json=body, headers=auth)
    assert r.status_code == 200, r.text
    scene = SEEN[-1].scene
    assert scene is not None and scene.tool == "event_choices"
    assert scene.options == tuple(c["label"] for c in ev["choices"])
    result = scene.output.result
    assert result["event"]["text"] == ev["text"] and [c["choice_id"] for c in result["choices"]] == [
        c["id"] for c in ev["choices"]]
    ids = {f.id for f in scene.output.facts}
    assert {f"{ev['id']}.{c['id']}.net_worth_change" for c in ev["choices"]} <= ids
