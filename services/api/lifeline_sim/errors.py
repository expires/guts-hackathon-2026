"""Sim errors. The API (W4) maps `code` to an HTTP status."""

from __future__ import annotations

from typing import Literal

SimErrorCode = Literal[
    "not_found",
    "pending_events",
    "dead",
    "payment_required",
    "invalid_choice",
    "invalid_action",
    "invalid_input",
    "finished",
]


class SimError(Exception):
    """A rule violation inside the sim. `code` is stable; `message` is plain English."""

    def __init__(self, code: SimErrorCode, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code: SimErrorCode = code
        self.message = message
