"""Ask Penny about a Learn lesson, W4 side: the server loads the lesson (never its quiz) into the chat context.

Penny (W5) is replaced by a fake that records the context.
"""

from __future__ import annotations

import json

import httpx
import pytest

from lifeline_contracts.chat import ChatBubble, ChatRequest, ChatResponse
from lifeline_explain.chat_tools import ChatToolContext
from lifeline_sim.learn_content import UNITS
from tests.integration.conftest import sign_in

SEEN: list[ChatToolContext] = []
LESSON_ID = "opportunity-cost"


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


def _body(lesson_id: str) -> dict[str, object]:
    return {"message": "Explain this lesson simply",
            "context": {"screen": "learn_lesson", "lesson_id": lesson_id, "title": "What you give up"}}  # fmt: skip


async def test_lesson_is_loaded_without_its_quiz(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "learn-lesson-chat-01")
    r = await client.post("/v1/chat", json=_body(LESSON_ID), headers=auth)
    assert r.status_code == 200, r.text
    scene = SEEN[-1].scene
    assert scene is not None and scene.tool == "learn_lesson"
    spec = next(s for u in UNITS for s in u.lessons if s.id == LESSON_ID)
    result = scene.output.result
    assert result["lesson_id"] == LESSON_ID and len(result["cards"]) == len(spec.cards)
    assert result["facts"][0]["source_url"].startswith("https://www.gov.uk/")
    dumped = json.dumps(result)
    assert "quiz" not in result and all(q.text not in dumped for q in spec.quiz)


async def test_unknown_lesson_is_not_an_error(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "learn-lesson-chat-02")
    r = await client.post("/v1/chat", json=_body("no-such-lesson"), headers=auth)
    assert r.status_code == 200, r.text
    assert SEEN[-1].scene is None
