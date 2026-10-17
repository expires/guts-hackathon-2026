"""Settings for the explain layer. Read from the environment at call time. The API key is never logged."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_MODEL = "claude-opus-5-5"  # ADR 0007
DEFAULT_TIMEOUT_SECONDS = 12.0
CACHE_TTL_SECONDS = 30 * 24 * 3600
PROMPT_VERSION = "v1"


@dataclass(frozen=True)
class ExplainSettings:
    model: str
    timeout_seconds: float
    redis_url: str | None
    enabled: bool

    def __repr__(self) -> str:  # never include secrets
        return f"ExplainSettings(model={self.model!r}, timeout_seconds={self.timeout_seconds}, enabled={self.enabled})"


def has_api_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


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
    )
