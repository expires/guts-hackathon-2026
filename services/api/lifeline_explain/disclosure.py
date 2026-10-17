"""'How Penny uses AI' (ADR 0043): one text for the You tab, the README and docs/RESPONSIBLE_AI.md.

The source of truth is ai_disclosure.json next to this file. A unit test keeps RESPONSIBLE_AI.md in step with it.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

DISCLOSURE_PATH = Path(__file__).with_name("ai_disclosure.json")


@cache
def ai_disclosure() -> dict[str, Any]:
    """{"title": str, "sections": [{"heading": str, "points": [str, ...]}]}"""
    data: dict[str, Any] = json.loads(DISCLOSURE_PATH.read_text(encoding="utf-8"))
    return data
