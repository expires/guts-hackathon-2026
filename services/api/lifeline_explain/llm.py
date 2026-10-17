"""LLM client. The LLM rewrites wording only; it never decides outcomes or numbers.

`LLMClient` is the seam for tests: pass a fake that implements `complete`.
"""

from __future__ import annotations

import os
from typing import Any, Protocol

from lifeline_explain.config import ExplainSettings


class LLMRefusal(Exception):
    """The model declined, or returned no text."""


class LLMClient(Protocol):
    async def complete(self, system: str, user: str, schema: dict[str, Any]) -> str:
        """Return the model's JSON text for `schema`. Raise on any failure."""
        ...


class AnthropicLLM:
    """Anthropic Messages API client (anthropic SDK 1.x, AsyncAnthropic).

    - Key: env ANTHROPIC_API_KEY only. Passed explicitly so the SDK does not pick up other credentials.
    - No SDK retries: the caller has a hard deadline and a template fallback.
    - Claude Opus 5.5 does not accept temperature or disabled thinking; effort 'low' keeps latency down.
    """

    def __init__(self, settings: ExplainSettings) -> None:
        from anthropic import AsyncAnthropic

        self._model = settings.model
        self._client = AsyncAnthropic(
            api_key=os.environ["ANTHROPIC_API_KEY"],
            timeout=settings.timeout_seconds,
            max_retries=0,
        )

    def __repr__(self) -> str:
        return f"AnthropicLLM(model={self._model!r})"

    async def complete(self, system: str, user: str, schema: dict[str, Any]) -> str:
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
        )
        if response.stop_reason in {"refusal", "max_tokens"}:
            raise LLMRefusal(str(response.stop_reason))
        text = next((b.text for b in response.content if b.type == "text"), "")
        if not text.strip():
            raise LLMRefusal("empty")
        return text
