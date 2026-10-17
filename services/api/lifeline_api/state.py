"""Per-process application state, created in the lifespan."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from fastapi import Request

from lifeline_api.apple import AppleVerifier
from lifeline_api.ratelimit import Limiter
from lifeline_api.rooms import RoomHub
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
    # Pure results and short-lived caches keyed by (name, ...). Same inputs give the same result.
    # Revoked token ids -> expiry (epoch seconds). Local copy; Redis holds the shared denylist.
    revoked_local: dict[str, float] = field(default_factory=dict)
    apple: AppleVerifier | None = None
    rooms: RoomHub = field(default_factory=lambda: RoomHub(None))
    chat_limiter: Limiter | None = None
    read_limiter: Limiter | None = None
    ip_limiter: Limiter | None = None
    auth_limiter: Limiter | None = None
    # Subject -> epoch ms. Tokens issued before it are rejected (account deleted). Redis + Postgres hold it too.
    revoked_before_local: dict[str, int] = field(default_factory=dict)
    memo: dict[tuple[str, ...], Any] = field(default_factory=dict)


def get_state(request: Request) -> AppState:
    state: AppState = request.app.state.lifeline
    return state
