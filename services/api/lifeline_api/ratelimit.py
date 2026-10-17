"""Token bucket rate limit per client IP and per token subject.

Capacity is RATE_LIMIT_PER_MINUTE tokens. Refill is capacity / 60 tokens per second.
The Redis bucket uses WATCH/MULTI so it works without Lua. If Redis fails, the limiter
falls back to a process-local bucket, so a Redis outage never blocks requests.
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable
from typing import Any, Protocol

from starlette.types import ASGIApp, Receive, Scope, Send

from lifeline_api.errors import error_response

log = logging.getLogger(__name__)

EXEMPT_PATHS = frozenset({"/v1/health"})


class Limiter(Protocol):
    async def take(self, key: str) -> float:
        """Take one token. Return 0 if allowed, else seconds until a token is available."""
        ...


class MemoryBucket:
    def __init__(self, per_minute: int, clock: Callable[[], float] = time.monotonic, max_keys: int = 50_000) -> None:
        self.capacity = float(per_minute)
        self.rate = per_minute / 60.0
        self._clock = clock
        self._max_keys = max_keys
        self._buckets: dict[str, tuple[float, float]] = {}

    async def take(self, key: str) -> float:
        now = self._clock()
        tokens, ts = self._buckets.get(key, (self.capacity, now))
        tokens = min(self.capacity, tokens + (now - ts) * self.rate)
        if tokens >= 1.0:
            self._store(key, tokens - 1.0, now)
            return 0.0
        self._store(key, tokens, now)
        return (1.0 - tokens) / self.rate

    def _store(self, key: str, tokens: float, now: float) -> None:
        if key not in self._buckets and len(self._buckets) >= self._max_keys:
            # Drop full buckets first; they carry no state worth keeping.
            for k in [k for k, (t, _) in self._buckets.items() if t >= self.capacity][: self._max_keys // 10 or 1]:
                del self._buckets[k]
        self._buckets[key] = (tokens, now)


class RedisBucket:
    """Token bucket in a Redis hash. Optimistic transaction with WATCH; falls back to memory on error."""

    PREFIX = "rl:"

    def __init__(self, redis: Any, per_minute: int, fallback: MemoryBucket | None = None,
                 clock: Callable[[], float] = time.time) -> None:
        self._redis = redis
        self.capacity = float(per_minute)
        self.rate = per_minute / 60.0
        self._clock = clock
        self._fallback = fallback or MemoryBucket(per_minute)
        self._ttl = max(2, math.ceil(self.capacity / self.rate) + 1)

    async def take(self, key: str) -> float:
        try:
            return await self._take(self.PREFIX + key)
        except Exception as exc:  # Redis down or misbehaving: never block requests on it.
            log.warning("rate limiter falling back to memory: %s", type(exc).__name__)
            return await self._fallback.take(key)

    async def _take(self, rkey: str) -> float:
        from redis.exceptions import WatchError

        for _ in range(5):
            async with self._redis.pipeline(transaction=True) as pipe:
                try:
                    await pipe.watch(rkey)
                    raw = await pipe.hmget(rkey, "t", "ts")
                    now = self._clock()
                    tokens = float(raw[0]) if raw[0] is not None else self.capacity
                    ts = float(raw[1]) if raw[1] is not None else now
                    tokens = min(self.capacity, tokens + max(0.0, now - ts) * self.rate)
                    wait = 0.0
                    if tokens >= 1.0:
                        tokens -= 1.0
                    else:
                        wait = (1.0 - tokens) / self.rate
                    pipe.multi()
                    pipe.hset(rkey, mapping={"t": tokens, "ts": now})
                    pipe.expire(rkey, self._ttl)
                    await pipe.execute()
                    return wait
                except WatchError:
                    continue
        return 1.0 / self.rate


def client_ip(scope: Scope) -> str:
    """The address the rate limiter keys on.

    Behind Railway's edge, uvicorn runs with --forwarded-allow-ips='*' and sets scope["client"] from the
    LEFTMOST X-Forwarded-For entry, which the client controls. The RIGHTMOST entry is the one our edge
    appended (the address that connected to it), so it is used when the header is present.
    """
    for name, value in scope.get("headers", []):
        if name == b"x-forwarded-for":
            parts = [p.strip() for p in value.decode("latin-1").split(",") if p.strip()]
            if parts:
                return str(parts[-1])[:64]
    client = scope.get("client")
    return str(client[0]) if client else "unknown"


class RateLimitMiddleware:
    """Applies the limiters to /v1 paths except health: ip:<addr> (abuse guard), then per subject
    read:<subject> for GET and HEAD or sub:<subject> for writes. Every 429 carries Retry-After."""

    def __init__(self, app: ASGIApp, subject_of: Callable[[Scope], str | None]) -> None:
        self.app = app
        self._subject_of = subject_of

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith("/v1/") or scope["path"] in EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return
        state = scope["app"].state.lifeline
        checks: list[tuple[Limiter, str]] = [(state.ip_limiter or state.limiter, f"ip:{client_ip(scope)}")]
        sub = self._subject_of(scope)
        if sub:
            if scope.get("method") in ("GET", "HEAD") and state.read_limiter is not None:
                checks.append((state.read_limiter, f"read:{sub}"))
            else:
                checks.append((state.limiter, f"sub:{sub}"))
        wait = 0.0
        for limiter, key in checks:
            wait = max(wait, await limiter.take(key))
        if wait > 0:
            retry = str(max(1, math.ceil(wait)))
            resp = error_response(429, "rate_limited", "Too many requests. Try again shortly.",
                                  headers={"Retry-After": retry})
            await resp(scope, receive, send)
            return
        await self.app(scope, receive, send)
