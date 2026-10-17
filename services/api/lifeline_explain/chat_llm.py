"""LLM seam for the Ask Penny tool-use loop. Tests pass a scripted fake; production uses AnthropicChatLLM."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from lifeline_explain.config import ExplainSettings

# Anthropic server tool (ADR 0051): runs inside the model call. Results come back as web_search_tool_result blocks.
WEB_SEARCH_TOOL: dict[str, Any] = {"type": "web_search_20260209", "name": "web_search", "max_uses": 2}
MAX_PAUSE_RESUMES = 2
MAX_TOKENS = 700  # two short bubbles of JSON; small for speed


@dataclass(frozen=True)
class ToolUse:
    id: str
    name: str
    input: dict[str, Any]


@dataclass(frozen=True)
class WebResult:
    """One web search result or citation the model saw. Title and text are untrusted.

    `text` is the cited text of a citation (readable page text). Plain search results carry no readable text."""

    url: str
    title: str
    text: str = ""


@dataclass
class LLMStep:
    """One model response. `content` is appended back unchanged as the assistant turn.

    `web_searches`: server web searches the model ran in this response. `web_results`: the pages it got back."""

    stop_reason: str
    text: str = ""
    tool_uses: list[ToolUse] = field(default_factory=list)
    content: Any = None
    web_searches: int = 0
    web_results: list[WebResult] = field(default_factory=list)


class ChatLLM(Protocol):
    async def step(
        self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]], schema: dict[str, Any]
    ) -> LLMStep:
        """Run one Messages API request. Raise on transport or API failure."""
        ...


def _web(content: Any) -> tuple[int, list[WebResult]]:
    searches = 0
    results: list[WebResult] = []
    for b in content or []:
        btype = getattr(b, "type", None)
        if btype == "server_tool_use" and getattr(b, "name", "") == "web_search":
            searches += 1
        elif btype == "web_search_tool_result":
            items = getattr(b, "content", None)
            if isinstance(items, list):  # an error result is an object, not a list
                for r in items:
                    url = getattr(r, "url", None)
                    if isinstance(url, str) and url.startswith("https://"):
                        results.append(WebResult(url=url[:500], title=str(getattr(r, "title", "") or "")[:200]))
        elif btype == "text":
            for c in getattr(b, "citations", None) or []:
                url = getattr(c, "url", None)
                if getattr(c, "type", "") == "web_search_result_location" and isinstance(url, str):
                    results.append(WebResult(url=url[:500], title=str(getattr(c, "title", "") or "")[:200],
                                             text=str(getattr(c, "cited_text", "") or "")[:1000]))  # fmt: skip
    return searches, results


class AnthropicChatLLM:
    """anthropic SDK 1.x (AsyncAnthropic.messages.create with `tools`).

    - Model: CHAT_MODEL (default claude-sonnet-5-5, ADR 0051). Effort low for speed.
    - Key only from env ANTHROPIC_API_KEY, passed explicitly. Never logged.
    - tool_choice stays 'auto' (forced tool use is a 400 on current models).
    - The system prompt is static and carries cache_control, so tools + system are a cached prefix.
    - No output_config.format: web search answers carry citations, which structured outputs reject. The prompt
      asks for JSON and `chat.parse_draft` is tolerant.
    - pause_turn (server tool loop limit) is resumed up to MAX_PAUSE_RESUMES times.
    - Bounded retries: the SDK retries once on 408/409/429/5xx and connection errors.
    """

    def __init__(self, settings: ExplainSettings) -> None:
        from anthropic import AsyncAnthropic

        self._model = settings.chat_model
        # Speed (V1): no thinking for chat. Sonnet 5.5 turns it off with "between_tools"; Haiku with "disabled".
        self._thinking: dict[str, Any] = {}
        if "sonnet-5-5" in self._model:
            self._thinking = {"thinking": {"type": "between_tools"}}
        elif "haiku" in self._model:
            self._thinking = {"thinking": {"type": "disabled"}}
        self._client = AsyncAnthropic(
            api_key=os.environ["ANTHROPIC_API_KEY"], timeout=settings.timeout_seconds, max_retries=1
        )

    def __repr__(self) -> str:
        return f"AnthropicChatLLM(model={self._model!r})"

    supports_stream = True  # Penny passes on_text: the first bubble can go out before the answer is complete

    async def step(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        schema: dict[str, Any],
        on_text: Callable[[str], None] | None = None,
    ) -> LLMStep:
        msgs = list(messages)
        searches = 0
        results: list[WebResult] = []
        content: list[Any] = []
        for _ in range(MAX_PAUSE_RESUMES + 1):
            kwargs: dict[str, Any] = {
                "model": self._model,
                "max_tokens": MAX_TOKENS,
                **self._thinking,
                "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                "messages": msgs,
                "tools": tools,
                "output_config": {"effort": "low"},
            }
            if on_text is None:
                response = await self._client.messages.create(**kwargs)
            else:
                text_so_far = "".join(b.text for b in content if getattr(b, "type", None) == "text")
                async with self._client.messages.stream(**kwargs) as stream:
                    async for event in stream:
                        delta: Any = getattr(event, "delta", None)
                        if event.type == "content_block_delta" and getattr(delta, "type", None) == "text_delta":
                            text_so_far += str(delta.text)
                            on_text(text_so_far)
                    response = await stream.get_final_message()
            n, r = _web(response.content)
            searches, results = searches + n, results + r
            content += list(response.content)
            if response.stop_reason != "pause_turn":
                break
            msgs = [*msgs, {"role": "assistant", "content": response.content}]
        uses = [ToolUse(id=b.id, name=b.name, input=dict(b.input)) for b in content if b.type == "tool_use"]
        text = "".join(b.text for b in content if b.type == "text")
        return LLMStep(
            stop_reason=str(response.stop_reason),
            text=text,
            tool_uses=uses,
            content=content,
            web_searches=searches,
            web_results=results,
        )
