"""A slow step inside Penny's answer (a 16 s web search) sends keepalives, so the app's 20 s idle limit never fires."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from lifeline_api.routes import chat as chat_route


@pytest.mark.asyncio
async def test_slow_answer_sends_keepalives(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chat_route, "KEEPALIVE_SECONDS", 0.05)

    async def slow() -> AsyncIterator[str]:
        yield "first"
        await asyncio.sleep(0.18)
        yield "second"

    out = [ev async for ev in chat_route._with_keepalive(slow())]  # type: ignore[arg-type]
    assert out[0] == "first" and out[-1] == "second"
    assert out.count(None) >= 2
