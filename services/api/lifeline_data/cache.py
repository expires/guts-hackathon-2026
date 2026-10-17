"""Two cache layers.

- `ObservationCache`: Redis, with an in-memory fallback when Redis is missing or down. Each entry stores
  the time it was written, so the hub can tell fresh (inside the source TTL) from stale.
- `SnapshotStore`: Postgres last-good snapshot (table `observations_snapshot`) via SQLAlchemy async.
  When `DATABASE_URL` is unset or Postgres is down, it uses an in-process store.

Neither class raises to the caller on backend failure.
"""

from __future__ import annotations

import contextlib
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import TypeAdapter
from sqlalchemy import Column, DateTime, MetaData, String, Table, Text, delete, insert, select
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from lifeline_contracts.observation import Observation

log = logging.getLogger(__name__)

OBS_LIST = TypeAdapter(list[Observation])

# Redis keeps entries well past the source TTL so a stale copy is available as "cached".
# Must stay above the longest source TTL (postcodes, 30 days); postcode entries pass 2 x TTL.
STALE_KEEP_SECONDS = 60 * 24 * 3600
REDIS_RETRY_SECONDS = 30.0


@dataclass(frozen=True)
class CacheEntry:
    stored_at: float  # unix seconds
    payload: Any

    def age(self, now: float) -> float:
        return now - self.stored_at


def obs_key(source: str, series_id: str, region: str | None) -> str:
    return f"lifeline:obs:{source}:{series_id}:{region or 'all'}"


class ObservationCache:
    def __init__(self, redis: Any | None = None, url: str = "", clock: Callable[[], float] = time.time) -> None:
        self._redis = redis
        self._url = url
        self._clock = clock
        self._memory: dict[str, tuple[float, str]] = {}  # key -> (expires_at, json)
        self._redis_down_until = 0.0

    def _client(self) -> Any | None:
        if self._redis is None and self._url:
            try:
                import redis.asyncio as aioredis

                self._redis = aioredis.from_url(self._url, socket_timeout=2, socket_connect_timeout=2)
            except Exception as exc:
                log.warning("redis unavailable (%s); using in-memory cache", type(exc).__name__)
                self._url = ""
        if self._redis is None or time.monotonic() < self._redis_down_until:
            return None
        return self._redis

    def _mark_down(self, exc: Exception) -> None:
        log.warning("redis error (%s); using in-memory cache for %ss", type(exc).__name__, REDIS_RETRY_SECONDS)
        self._redis_down_until = time.monotonic() + REDIS_RETRY_SECONDS

    async def get_raw(self, key: str) -> CacheEntry | None:
        raw: str | bytes | None = None
        client = self._client()
        if client is not None:
            try:
                raw = await client.get(key)
            except Exception as exc:
                self._mark_down(exc)
        if raw is None:
            hit = self._memory.get(key)
            if hit is not None and hit[0] > self._clock():
                raw = hit[1]
        if raw is None:
            return None
        try:
            doc = json.loads(raw)
            return CacheEntry(float(doc["stored_at"]), doc["payload"])
        except (ValueError, KeyError, TypeError):
            return None

    async def set_raw(self, key: str, payload: Any, keep_seconds: int = STALE_KEEP_SECONDS) -> None:
        now = self._clock()
        doc = json.dumps({"stored_at": now, "payload": payload}, default=str)
        self._memory[key] = (now + keep_seconds, doc)
        client = self._client()
        if client is not None:
            try:
                await client.set(key, doc, ex=keep_seconds)
            except Exception as exc:
                self._mark_down(exc)

    async def get(self, key: str) -> tuple[float, list[Observation]] | None:
        """Returns (stored_at, observations) or None."""
        entry = await self.get_raw(key)
        if entry is None:
            return None
        try:
            return entry.stored_at, OBS_LIST.validate_python(entry.payload)
        except ValueError:
            return None

    async def set(self, key: str, observations: list[Observation]) -> None:
        await self.set_raw(key, OBS_LIST.dump_python(observations, mode="json"))

    async def aclose(self) -> None:
        if self._redis is not None:
            with contextlib.suppress(Exception):
                await self._redis.aclose()


metadata = MetaData()
snapshot_table = Table(
    "observations_snapshot",
    metadata,
    Column("series_key", String(255), primary_key=True),
    Column("source", String(64), nullable=False),
    Column("payload", Text, nullable=False),
    Column("fetched_at", DateTime(timezone=True), nullable=False),
)


class SnapshotStore:
    """Last-good observations per series. Postgres when available, else in-process."""

    def __init__(self, engine: AsyncEngine | None = None, url: str = "") -> None:
        self._engine = engine
        self._url = url
        self._ready = False
        self._disabled = False
        self._memory: dict[str, list[Observation]] = {}

    async def _db(self) -> AsyncEngine | None:
        if self._disabled:
            return None
        if self._engine is None and self._url:
            try:
                self._engine = create_async_engine(self._url, pool_pre_ping=True)
            except Exception as exc:
                log.warning("snapshot DB unavailable (%s); using in-process store", type(exc).__name__)
                self._disabled = True
                return None
        if self._engine is None:
            return None
        if not self._ready:
            try:
                async with self._engine.begin() as conn:
                    await conn.run_sync(metadata.create_all)
                self._ready = True
            except Exception as exc:
                log.warning("snapshot DB unavailable (%s); using in-process store", type(exc).__name__)
                return None
        return self._engine

    async def put(self, key: str, observations: list[Observation]) -> None:
        if not observations:
            return
        self._memory[key] = observations
        engine = await self._db()
        if engine is None:
            return
        payload = OBS_LIST.dump_json(observations).decode()
        try:
            async with engine.begin() as conn:
                await conn.execute(delete(snapshot_table).where(snapshot_table.c.series_key == key))
                await conn.execute(
                    insert(snapshot_table).values(
                        series_key=key, source=observations[0].source, payload=payload, fetched_at=datetime.now(UTC)
                    )
                )
        except Exception as exc:
            log.warning("snapshot write failed (%s)", type(exc).__name__)

    async def get(self, key: str) -> list[Observation] | None:
        engine = await self._db()
        if engine is not None:
            try:
                async with engine.connect() as conn:
                    row = (
                        await conn.execute(select(snapshot_table.c.payload).where(snapshot_table.c.series_key == key))
                    ).first()
                if row is not None:
                    return OBS_LIST.validate_json(row[0])
            except Exception as exc:
                log.warning("snapshot read failed (%s)", type(exc).__name__)
        return self._memory.get(key)

    async def aclose(self) -> None:
        if self._engine is not None:
            with contextlib.suppress(Exception):
                await self._engine.dispose()
