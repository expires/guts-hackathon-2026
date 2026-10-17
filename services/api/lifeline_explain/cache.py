"""Cache of verified LLM wording. Redis when REDIS_URL works, else an in-memory LRU.

Key: sha256 of (prompt version, model, kind, template id, facts, choice, source text).
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import OrderedDict
from typing import Any, Protocol

log = logging.getLogger(__name__)

PREFIX = "lifeline:explain:"


def cache_key(**parts: Any) -> str:
    blob = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)
    return PREFIX + hashlib.sha256(blob.encode()).hexdigest()


class TextCache(Protocol):
    async def get(self, key: str) -> str | None: ...

    async def set(self, key: str, value: str, ttl: int) -> None: ...


class MemoryCache:
    def __init__(self, max_items: int = 5000) -> None:
        self._data: OrderedDict[str, tuple[float, str]] = OrderedDict()
        self._max = max_items

    async def get(self, key: str) -> str | None:
        item = self._data.get(key)
        if item is None:
            return None
        expires, value = item
        if expires < time.monotonic():
            self._data.pop(key, None)
            return None
        self._data.move_to_end(key)
        return value

    async def set(self, key: str, value: str, ttl: int) -> None:
        self._data[key] = (time.monotonic() + ttl, value)
        self._data.move_to_end(key)
        while len(self._data) > self._max:
            self._data.popitem(last=False)


class RedisCache:
    """Redis with an in-memory fallback. After a Redis error, Redis is skipped for `retry_after` seconds."""

    def __init__(self, url: str, retry_after: float = 30.0, client: Any = None) -> None:
        self._memory = MemoryCache()
        self._retry_after = retry_after
        self._down_until = 0.0
        if client is not None:
            self._redis = client
        else:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(url, socket_connect_timeout=0.3, socket_timeout=0.3)

    def _up(self) -> bool:
        return time.monotonic() >= self._down_until

    def _fail(self, exc: Exception) -> None:
        self._down_until = time.monotonic() + self._retry_after
        log.warning("explain cache: redis unavailable (%s), using memory", type(exc).__name__)

    async def get(self, key: str) -> str | None:
        if self._up():
            try:
                raw = await self._redis.get(key)
                if raw is not None:
                    return raw.decode() if isinstance(raw, bytes) else str(raw)
            except Exception as exc:
                self._fail(exc)
        return await self._memory.get(key)

    async def set(self, key: str, value: str, ttl: int) -> None:
        await self._memory.set(key, value, ttl)
        if self._up():
            try:
                await self._redis.set(key, value, ex=ttl)
            except Exception as exc:
                self._fail(exc)


def make_cache(redis_url: str | None) -> TextCache:
    if not redis_url:
        return MemoryCache()
    try:
        return RedisCache(redis_url)
    except Exception as exc:  # bad URL or missing driver
        log.warning("explain cache: cannot build redis client (%s), using memory", type(exc).__name__)
        return MemoryCache()
