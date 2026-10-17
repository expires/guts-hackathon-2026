"""Lives store. Postgres JSONB in dev and prod, in-memory in tests.

Each life keeps the hash of the MacroTable it was created with. The table itself is stored
once per hash, so AGE, choices and rewinds always replay with the same numbers (ADR 0005).
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import json
import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy import exc as sa_exc
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from lifeline_api.errors import ApiError
from lifeline_contracts.domain import Life
from lifeline_contracts.macro import MacroTable

log = logging.getLogger(__name__)

# Seconds. Fail fast when Postgres is down instead of hanging the request.
CONNECT_TIMEOUT = 3.0
POOL_TIMEOUT = 3.0


class StoreUnavailable(ApiError):
    """The lives store cannot be reached. Rendered as 503 `store_unavailable`."""

    def __init__(self) -> None:
        super().__init__(503, "store_unavailable", "Saving is down. Try again in a minute.",
                         source="store")


def _is_unavailable(exc: BaseException) -> bool:
    """Connection-level failures only. Data errors (e.g. a duplicate key) stay real errors."""
    if isinstance(exc, sa_exc.IntegrityError | sa_exc.DataError | sa_exc.ProgrammingError):
        return False
    return isinstance(
        exc, sa_exc.OperationalError | sa_exc.InterfaceError | sa_exc.DisconnectionError | sa_exc.TimeoutError
        | sa_exc.DBAPIError | OSError | TimeoutError,
    )


def _guarded[**P, R](fn: Callable[P, Coroutine[Any, Any, R]]) -> Callable[P, Coroutine[Any, Any, R]]:
    """Turn connection-level failures into StoreUnavailable (503)."""

    @functools.wraps(fn)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return await fn(*args, **kwargs)
        except Exception as exc:
            if _is_unavailable(exc):
                log.warning("lives store unavailable in %s: %s", fn.__name__, type(exc).__name__)
                raise StoreUnavailable() from exc
            raise

    return wrapper


def macro_hash(table: MacroTable) -> str:
    """Stable sha256 of the table content. Key order does not change the hash."""
    payload = json.dumps(table.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


@dataclass
class LifeRecord:
    id: str
    owner: str
    life: Life
    macro_hash: str
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class LifeStore(Protocol):
    async def start(self) -> None: ...

    async def close(self) -> None: ...

    async def ping(self) -> bool: ...

    async def create(self, record: LifeRecord) -> None: ...

    async def get(self, life_id: str, owner: str) -> LifeRecord | None:
        """Return the record only if `owner` owns it. Other owners get None (shown as 404)."""
        ...

    async def save(self, record: LifeRecord) -> None: ...

    async def put_macro(self, digest: str, table: MacroTable) -> None: ...

    async def get_macro(self, digest: str) -> MacroTable | None: ...

    async def list_by_owner(self, owner: str, limit: int = 100) -> list[LifeRecord]:
        """Most recently updated first."""
        ...

    async def get_doc(self, owner: str, kind: str) -> Any | None:
        """Per-subject JSON document (budgets, goals, guesses, plan, latest next move). None if absent."""
        ...

    async def put_doc(self, owner: str, kind: str, doc: Any) -> None: ...

    async def delete_doc(self, owner: str, kind: str) -> None: ...

    async def list_docs(self, owner: str, prefix: str) -> dict[str, Any]:
        """Documents of `owner` whose kind starts with `prefix`, keyed by kind."""
        ...

    async def delete_owner(self, owner: str, keep: tuple[str, ...] = ()) -> int:
        """Delete every life and document of `owner`, except document kinds in `keep`. Returns rows deleted."""
        ...


class MemoryLifeStore:
    """Process-local store for tests and for dev without DATABASE_URL."""

    def __init__(self) -> None:
        self._lives: dict[str, LifeRecord] = {}
        self._macros: dict[str, MacroTable] = {}
        self._docs: dict[tuple[str, str], str] = {}

    async def start(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def ping(self) -> bool:
        return True

    async def create(self, record: LifeRecord) -> None:
        if record.id in self._lives:
            raise KeyError(f"duplicate life id {record.id}")
        self._lives[record.id] = record

    async def get(self, life_id: str, owner: str) -> LifeRecord | None:
        rec = self._lives.get(life_id)
        if rec is None or rec.owner != owner:
            return None
        return rec

    async def save(self, record: LifeRecord) -> None:
        record.updated_at = datetime.now(UTC)
        self._lives[record.id] = record

    async def put_macro(self, digest: str, table: MacroTable) -> None:
        self._macros.setdefault(digest, table)

    async def get_macro(self, digest: str) -> MacroTable | None:
        return self._macros.get(digest)

    async def list_by_owner(self, owner: str, limit: int = 100) -> list[LifeRecord]:
        mine = [r for r in self._lives.values() if r.owner == owner]
        return sorted(mine, key=lambda r: r.updated_at, reverse=True)[:limit]

    async def get_doc(self, owner: str, kind: str) -> Any | None:
        raw = self._docs.get((owner, kind))
        return None if raw is None else json.loads(raw)

    async def put_doc(self, owner: str, kind: str, doc: Any) -> None:
        # Stored as JSON text, so callers never share mutable state with the store (same as Postgres).
        self._docs[(owner, kind)] = json.dumps(doc)

    async def delete_doc(self, owner: str, kind: str) -> None:
        self._docs.pop((owner, kind), None)

    async def list_docs(self, owner: str, prefix: str) -> dict[str, Any]:
        return {k: json.loads(v) for (o, k), v in self._docs.items() if o == owner and k.startswith(prefix)}

    async def delete_owner(self, owner: str, keep: tuple[str, ...] = ()) -> int:
        lives = [k for k, r in self._lives.items() if r.owner == owner]
        docs = [key for key in self._docs if key[0] == owner and key[1] not in keep]
        for k in lives:
            del self._lives[k]
        for key in docs:
            del self._docs[key]
        return len(lives) + len(docs)


_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS lives (
        id TEXT PRIMARY KEY,
        owner TEXT NOT NULL,
        life JSONB NOT NULL,
        macro_hash TEXT NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS lives_owner_idx ON lives (owner)",
    """
    CREATE TABLE IF NOT EXISTS macro_tables (
        hash TEXT PRIMARY KEY,
        tbl JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_docs (
        owner TEXT NOT NULL,
        kind TEXT NOT NULL,
        doc JSONB NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (owner, kind)
    )
    """,
)


class PostgresLifeStore:
    """Postgres store. Tables are created on start if missing. A small in-process cache holds macro tables."""

    def __init__(self, database_url: str) -> None:
        self._url = database_url
        self._engine: AsyncEngine | None = None
        self._ready = False
        self._lock = asyncio.Lock()
        self._macro_cache: dict[str, MacroTable] = {}

    def _eng(self) -> AsyncEngine:
        if self._engine is None:
            self._engine = create_async_engine(
                self._url,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=5,
                pool_timeout=POOL_TIMEOUT,
                connect_args={"timeout": CONNECT_TIMEOUT},
            )
        return self._engine

    async def _ensure_schema(self) -> None:
        if self._ready:
            return
        async with self._lock:
            if self._ready:
                return
            async with self._eng().begin() as conn:
                for stmt in _SCHEMA:
                    await conn.execute(text(stmt))
            self._ready = True

    @_guarded
    async def start(self) -> None:
        await self._ensure_schema()

    async def close(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None

    async def ping(self) -> bool:
        try:
            async with self._eng().connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    @_guarded
    async def create(self, record: LifeRecord) -> None:
        await self._ensure_schema()
        async with self._eng().begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO lives (id, owner, life, macro_hash, updated_at) "
                    "VALUES (:id, :owner, CAST(:life AS JSONB), :macro_hash, :updated_at)"
                ),
                self._params(record),
            )

    @_guarded
    async def get(self, life_id: str, owner: str) -> LifeRecord | None:
        await self._ensure_schema()
        async with self._eng().connect() as conn:
            row = (
                await conn.execute(
                    text("SELECT id, owner, life, macro_hash, updated_at FROM lives WHERE id = :id AND owner = :owner"),
                    {"id": life_id, "owner": owner},
                )
            ).first()
        if row is None:
            return None
        life_raw: Any = row.life
        life = Life.model_validate_json(life_raw) if isinstance(life_raw, str) else Life.model_validate(life_raw)
        return LifeRecord(id=row.id, owner=row.owner, life=life, macro_hash=row.macro_hash, updated_at=row.updated_at)

    @_guarded
    async def save(self, record: LifeRecord) -> None:
        await self._ensure_schema()
        record.updated_at = datetime.now(UTC)
        async with self._eng().begin() as conn:
            await conn.execute(
                text(
                    "UPDATE lives SET life = CAST(:life AS JSONB), macro_hash = :macro_hash, updated_at = :updated_at "
                    "WHERE id = :id AND owner = :owner"
                ),
                self._params(record),
            )

    @_guarded
    async def put_macro(self, digest: str, table: MacroTable) -> None:
        await self._ensure_schema()
        self._macro_cache[digest] = table
        async with self._eng().begin() as conn:
            await conn.execute(
                text("INSERT INTO macro_tables (hash, tbl) VALUES (:hash, CAST(:tbl AS JSONB)) ON CONFLICT DO NOTHING"),
                {"hash": digest, "tbl": table.model_dump_json()},
            )

    @_guarded
    async def get_macro(self, digest: str) -> MacroTable | None:
        hit = self._macro_cache.get(digest)
        if hit is not None:
            return hit
        await self._ensure_schema()
        async with self._eng().connect() as conn:
            query = text("SELECT tbl FROM macro_tables WHERE hash = :hash")
            row = (await conn.execute(query, {"hash": digest})).first()
        if row is None:
            return None
        raw: Any = row.tbl
        table = MacroTable.model_validate_json(raw) if isinstance(raw, str) else MacroTable.model_validate(raw)
        self._macro_cache[digest] = table
        return table

    @_guarded
    async def list_by_owner(self, owner: str, limit: int = 100) -> list[LifeRecord]:
        await self._ensure_schema()
        async with self._eng().connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT id, owner, life, macro_hash, updated_at FROM lives WHERE owner = :owner "
                        "ORDER BY updated_at DESC LIMIT :limit"
                    ),
                    {"owner": owner, "limit": limit},
                )
            ).all()
        out: list[LifeRecord] = []
        for row in rows:
            raw: Any = row.life
            life = Life.model_validate_json(raw) if isinstance(raw, str) else Life.model_validate(raw)
            out.append(LifeRecord(id=row.id, owner=row.owner, life=life, macro_hash=row.macro_hash,
                                  updated_at=row.updated_at))
        return out

    @_guarded
    async def get_doc(self, owner: str, kind: str) -> Any | None:
        await self._ensure_schema()
        async with self._eng().connect() as conn:
            row = (
                await conn.execute(
                    text("SELECT doc FROM user_docs WHERE owner = :owner AND kind = :kind"),
                    {"owner": owner, "kind": kind},
                )
            ).first()
        if row is None:
            return None
        raw: Any = row.doc
        return json.loads(raw) if isinstance(raw, str) else raw

    @_guarded
    async def put_doc(self, owner: str, kind: str, doc: Any) -> None:
        await self._ensure_schema()
        async with self._eng().begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO user_docs (owner, kind, doc, updated_at) VALUES (:owner, :kind, CAST(:doc AS JSONB), "
                    "now()) ON CONFLICT (owner, kind) DO UPDATE SET doc = EXCLUDED.doc, updated_at = now()"
                ),
                {"owner": owner, "kind": kind, "doc": json.dumps(doc)},
            )

    @_guarded
    async def delete_doc(self, owner: str, kind: str) -> None:
        await self._ensure_schema()
        async with self._eng().begin() as conn:
            await conn.execute(text("DELETE FROM user_docs WHERE owner = :owner AND kind = :kind"),
                               {"owner": owner, "kind": kind})

    @_guarded
    async def list_docs(self, owner: str, prefix: str) -> dict[str, Any]:
        await self._ensure_schema()
        pattern = prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        async with self._eng().connect() as conn:
            rows = (
                await conn.execute(
                    text("SELECT kind, doc FROM user_docs WHERE owner = :owner AND kind LIKE :pattern"),
                    {"owner": owner, "pattern": pattern},
                )
            ).all()
        out: dict[str, Any] = {}
        for row in rows:
            raw: Any = row.doc
            out[row.kind] = json.loads(raw) if isinstance(raw, str) else raw
        return out

    @_guarded
    async def delete_owner(self, owner: str, keep: tuple[str, ...] = ()) -> int:
        await self._ensure_schema()
        async with self._eng().begin() as conn:
            lives = await conn.execute(text("DELETE FROM lives WHERE owner = :owner"), {"owner": owner})
            docs = await conn.execute(
                text("DELETE FROM user_docs WHERE owner = :owner AND NOT (kind = ANY(:keep))"),
                {"owner": owner, "keep": list(keep)},
            )
        return int(lives.rowcount or 0) + int(docs.rowcount or 0)

    @staticmethod
    def _params(record: LifeRecord) -> dict[str, Any]:
        return {
            "id": record.id,
            "owner": record.owner,
            "life": record.life.model_dump_json(),
            "macro_hash": record.macro_hash,
            "updated_at": record.updated_at,
        }
