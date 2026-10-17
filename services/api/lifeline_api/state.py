"""Per-process application state, created in the lifespan."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from fastapi import Request

from lifeline_api.ratelimit import Limiter
from lifeline_api.settings import Settings
from lifeline_api.store import LifeStore
from lifeline_contracts.interfaces import DataHub


@dataclass
class AppState:
    settings: Settings
    store: LifeStore
    hub: DataHub
    limiter: Limiter
    jwt_secret: str
    redis: Any | None = None
    life_locks: defaultdict[str, asyncio.Lock] = field(default_factory=lambda: defaultdict(asyncio.Lock))
    # Per-subject locks for read-modify-write on per-subject documents (budgets, goals, guesses, plan).
    subject_locks: defaultdict[str, asyncio.Lock] = field(default_factory=lambda: defaultdict(asyncio.Lock))
    # Pure results keyed by (name, macro hash). The same table always gives the same result.
    memo: dict[tuple[str, str], Any] = field(default_factory=dict)


def get_state(request: Request) -> AppState:
    state: AppState = request.app.state.lifeline
    return state
