"""LLM seam for the Ask Penny tool-use loop. Tests pass a scripted fake; production uses AnthropicChatLLM."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Protocol, cast

from lifeline_explain.config import ExplainSettings


@dataclass(frozen=True)
class ToolUse:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class LLMStep:
    """One model response. `content` is appended back unchanged as the assistant turn."""

    stop_reason: str
    text: str = ""
    tool_uses: list[ToolUse] = field(default_factory=list)
    content: Any = None


class ChatLLM(Protocol):
    async def step(
        self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]], schema: dict[str, Any]
    ) -> LLMStep:
        """Run one Messages API request. Raise on transport or API failure."""
        ...


class AnthropicChatLLM:
    """anthropic SDK 1.x (AsyncAnthropic.messages.create with `tools`).

    - Key only from env ANTHROPIC_API_KEY, passed explicitly. Never logged.
    - tool_choice stays 'auto' (forced tool use is a 400 on Claude Opus 5.5).
    - The final answer is JSON constrained by `output_config.format`.
    - Bounded retries: the SDK retries once on 408/409/429/5xx and connection errors.
    """

    def __init__(self, settings: ExplainSettings) -> None:
        from anthropic import AsyncAnthropic

        self._model = settings.model
        self._client = AsyncAnthropic(
            api_key=os.environ["ANTHROPIC_API_KEY"], timeout=settings.timeout_seconds, max_retries=1
        )

    def __repr__(self) -> str:
        return f"AnthropicChatLLM(model={self._model!r})"

    async def step(
        self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]], schema: dict[str, Any]
    ) -> LLMStep:
        output_config: Any = {"effort": "low", "format": {"type": "json_schema", "schema": schema}}
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=system,
            messages=cast(Any, messages),
            tools=cast(Any, tools),
            output_config=output_config,
        )
        uses = [ToolUse(id=b.id, name=b.name, input=dict(b.input)) for b in response.content if b.type == "tool_use"]
        text = "".join(b.text for b in response.content if b.type == "text")
        return LLMStep(stop_reason=str(response.stop_reason), text=text, tool_uses=uses, content=response.content)
