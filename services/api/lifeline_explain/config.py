"""Settings for the explain layer. Read from the environment at call time. The API key is never logged."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_MODEL = "claude-opus-5-5"  # ADR 0007: engine text rewording (LLM_MODEL)
DEFAULT_CHAT_MODEL = "claude-sonnet-5-5"  # ADR 0051: Ask Penny (CHAT_MODEL), first bubble under 3 s
DEFAULT_CHAT_TIMEOUT_SECONDS = 12.0  # V3 final: a whole Ask Penny answer, retries included
DEFAULT_TIMEOUT_SECONDS = 12.0
CACHE_TTL_SECONDS = 30 * 24 * 3600
PROMPT_VERSION = "v2"  # v2: Move.action is no longer reworded


@dataclass(frozen=True)
class ExplainSettings:
    model: str
    timeout_seconds: float
    redis_url: str | None
    enabled: bool
    chat_model: str = DEFAULT_CHAT_MODEL
    chat_timeout_seconds: float = DEFAULT_CHAT_TIMEOUT_SECONDS

    @property
    def chat_deadline(self) -> float:
        """Total time for one Ask Penny answer before the fallback reply: at most CHAT_TIMEOUT_SECONDS (12 s),
        whatever LLM_TIMEOUT_SECONDS is."""
        return min(self.chat_timeout_seconds, 2 * self.timeout_seconds)

    def __repr__(self) -> str:  # never include secrets
        return (
            f"ExplainSettings(model={self.model!r}, chat_model={self.chat_model!r}, "
            f"timeout_seconds={self.timeout_seconds}, enabled={self.enabled})"
        )


def has_api_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def _positive(raw: str | None, default: float) -> float:
    try:
        value = float(raw) if raw not in (None, "") else default
    except ValueError:
        return default
    return value if value > 0 else default


def load_settings() -> ExplainSettings:
    try:
        timeout = float(os.environ.get("LLM_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS))
    except ValueError:
        timeout = DEFAULT_TIMEOUT_SECONDS
    if timeout <= 0:
        timeout = DEFAULT_TIMEOUT_SECONDS
    return ExplainSettings(
        model=os.environ.get("LLM_MODEL", "").strip() or DEFAULT_MODEL,
        timeout_seconds=timeout,
        redis_url=os.environ.get("REDIS_URL", "").strip() or None,
        enabled=os.environ.get("LLM_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"},
        chat_model=os.environ.get("CHAT_MODEL", "").strip() or DEFAULT_CHAT_MODEL,
        chat_timeout_seconds=_positive(os.environ.get("CHAT_TIMEOUT_SECONDS"), DEFAULT_CHAT_TIMEOUT_SECONDS),
    )
