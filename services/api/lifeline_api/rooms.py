"""Same Life rooms (ADR 0029 part 3): state in Redis, events over Redis pub/sub, so it works across replicas.

- A room is one JSON document `lifeline:room:<CODE>` (24 h TTL). Writes take a short Redis lock.
- Each change publishes a WsServerMessage on `lifeline:room:<CODE>:events`. Every WebSocket connection
  (on any replica) subscribes and forwards to its client.
- Without Redis (dev), the same interfaces run in process.
- The server owns the seed and every player's life. Rival numbers come from the stored life, not the client.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import logging
import secrets
import struct
import time
import zlib
from collections import defaultdict
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from typing import Any

import qrcode  # type: ignore[import-untyped]

from lifeline_contracts.api_models import Player, Room
from lifeline_contracts.play import GameOptions

log = logging.getLogger(__name__)

ROOM_TTL_SECONDS = 24 * 3600
# A holder that crashes frees the lock after this. Work under the lock is short (no network I/O).
LOCK_MS = 10_000
RECONNECT_SECONDS = 10 * 60
CODE_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
MAX_PLAYERS = {"duel": 2, "group": 6, "class": 8}
LOBBY_MAX_PLAYERS = 8  # lobby first: the mode (and so the size) is set at start
KEY = "lifeline:room:{code}"
CHANNEL = "lifeline:room:{code}:events"
LOCK = "lifeline:room:{code}:lock"
USER_ROOMS = "lifeline:user-rooms:{sub}"
DRIVER = "lifeline:room:{code}:driver"
ACTIVE_GAMES = "lifeline:rooms:active-games"


def new_code() -> str:
    """Room codes are 4 digits, easy to read aloud (ADR 0064). Uniqueness among live rooms comes from the
    create-if-absent write; rooms expire after 24 hours."""
    return f"{secrets.randbelow(10_000):04d}"


def new_circle_code() -> str:
    """Circle codes stay 6 letters and digits (contract ^[A-Z0-9]{6}$)."""
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))


def join_url(code: str) -> str:
    return f"lifeline://join/{code}"


class RoomBusy(Exception):
    """The room lock could not be taken in time."""


class RoomsUnavailable(Exception):
    """The room store (Redis) cannot be reached. REST answers 503; the WebSocket closes cleanly (V3 F2)."""


@contextmanager
def _redis_errors() -> Iterator[None]:
    try:
        yield
    except (RoomBusy, RoomsUnavailable, asyncio.CancelledError):
        raise
    except Exception as exc:
        log.warning("room store unavailable: %s", type(exc).__name__)
        raise RoomsUnavailable() from exc


class _GuardedRedis:
    """Every awaited Redis call raises RoomsUnavailable instead of a driver error. pubsub() passes through."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._inner, name)
        if name == "pubsub" or not callable(attr):
            return attr

        async def call(*args: Any, **kwargs: Any) -> Any:
            try:
                with _redis_errors():
                    return await attr(*args, **kwargs)
            except RoomsUnavailable:
                await self._reset_pool()
                raise

        return call

    async def _reset_pool(self) -> None:
        """Drop pooled connections on the first failure, so the next call reconnects at once when Redis is
        back instead of reusing dead sockets for 15-20 s (V3 final)."""
        pool = getattr(self._inner, "connection_pool", None)
        if pool is None:
            return
        with contextlib.suppress(Exception):
            await pool.disconnect(inuse_connections=True)


# ---------- QR as PNG (no image library needed) ----------


def qr_png_base64(text: str, scale: int = 8, border: int = 4) -> str:
    qr = qrcode.QRCode(border=border, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(text)
    qr.make(fit=True)
    matrix: list[list[bool]] = qr.get_matrix()
    size = len(matrix) * scale
    rows = bytearray()
    for row in matrix:
        line = bytearray([0])  # filter type 0
        bits = [0 if dark else 1 for dark in row for _ in range(scale)]  # 1 = white
        for i in range(0, size, 8):
            byte = 0
            for j, b in enumerate(bits[i:i + 8]):
                byte |= b << (7 - j)
            line.append(byte)
        rows.extend(bytes(line) * scale)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 1, 0, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(rows), 9)) + chunk(b"IEND", b"")
    return base64.b64encode(png).decode()


# ---------- room document ----------


@dataclass
class RoomDoc:
    """Server-side room. `players[*].sub` never leaves the server."""

    code: str
    mode: str
    seed: int
    preset_id: str | None
    start_year: int | None
    max_players: int
    status: str = "lobby"
    qr: str = ""
    players: list[dict[str, Any]] = field(default_factory=list)
    macro_hash: str | None = None
    mode_fixed: bool = False  # False: decided at start (2 players = duel, more = group)
    game: str | None = None
    options: dict[str, Any] | None = None
    game_state: dict[str, Any] = field(default_factory=dict)  # server only: answers, correct ids, scores

    def to_json(self) -> str:
        return json.dumps(self.__dict__)

    @classmethod
    def from_json(cls, raw: str | bytes) -> RoomDoc:
        data = json.loads(raw)
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in known})

    def player(self, player_id: str) -> dict[str, Any] | None:
        return next((p for p in self.players if p["id"] == player_id), None)

    def player_of(self, sub: str) -> dict[str, Any] | None:
        return next((p for p in self.players if p["sub"] == sub), None)

    def add_player(self, sub: str, name: str, *, host: bool = False) -> dict[str, Any]:
        p = {"id": f"pl_{secrets.token_hex(6)}", "sub": sub, "name": name[:24], "is_host": host, "ready": False,
             "connected": False, "life_id": None, "age": None, "year": None, "net_worth": None, "index": None,
             "finished": False, "last_seen": time.time()}
        self.players.append(p)
        return p

    def drop_stale(self, now: float) -> None:
        """In the lobby, players gone longer than the reconnect window leave the room."""
        if self.status != "lobby":
            return
        self.players = [p for p in self.players if p["connected"] or now - p["last_seen"] < RECONNECT_SECONDS]
        if self.players and not any(p["is_host"] for p in self.players):
            self.players[0]["is_host"] = True

    @staticmethod
    def public_player(p: dict[str, Any]) -> Player:
        return Player.model_validate({k: v for k, v in p.items() if k not in ("sub", "last_seen")})

    def public(self) -> Room:
        return Room(
            code=self.code, mode=self.mode, seed=self.seed, preset_id=self.preset_id,
            start_year=self.start_year, max_players=self.max_players, game=self.game,
            options=None if self.options is None else GameOptions.model_validate(self.options),
            players=[self.public_player(p) for p in self.players], join_url=join_url(self.code),
            qr_png_base64=self.qr, status=self.status,
        )


# ---------- storage and fan-out ----------


class RoomHub:
    """Redis when available (shared by all replicas), else process memory."""

    def __init__(self, redis: Any | None) -> None:
        self.redis: Any | None = _GuardedRedis(redis) if redis is not None else None
        self._docs: dict[str, str] = {}
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._queues: defaultdict[str, set[asyncio.Queue[str]]] = defaultdict(set)
        self._user_rooms: defaultdict[str, set[str]] = defaultdict(set)
        self._beats: dict[str, float] = {}
        self._active: set[str] = set()

    async def get(self, code: str) -> RoomDoc | None:
        raw = await self.redis.get(KEY.format(code=code)) if self.redis is not None else self._docs.get(code)
        return None if raw is None else RoomDoc.from_json(raw)

    async def put(self, doc: RoomDoc) -> None:
        if self.redis is not None:
            await self.redis.set(KEY.format(code=doc.code), doc.to_json(), ex=ROOM_TTL_SECONDS)
        else:
            self._docs[doc.code] = doc.to_json()

    async def delete(self, code: str) -> None:
        if self.redis is not None:
            await self.redis.delete(KEY.format(code=code))
        else:
            self._docs.pop(code, None)

    # Rooms a subject has a seat in, so a demo reset can clear them (judge mode, ADR 0049).

    async def track(self, sub: str, code: str) -> None:
        if self.redis is not None:
            key = USER_ROOMS.format(sub=sub)
            await self.redis.sadd(key, code)
            await self.redis.expire(key, ROOM_TTL_SECONDS)
        else:
            self._user_rooms[sub].add(code)

    async def rooms_of(self, sub: str) -> set[str]:
        if self.redis is not None:
            raw = await self.redis.smembers(USER_ROOMS.format(sub=sub))
            return {c.decode() if isinstance(c, bytes) else str(c) for c in raw}
        return set(self._user_rooms.get(sub, set()))

    async def untrack_all(self, sub: str) -> None:
        if self.redis is not None:
            await self.redis.delete(USER_ROOMS.format(sub=sub))
        else:
            self._user_rooms.pop(sub, None)

    async def create(self, doc: RoomDoc) -> bool:
        """False when the code is taken."""
        if self.redis is not None:
            return bool(await self.redis.set(KEY.format(code=doc.code), doc.to_json(), ex=ROOM_TTL_SECONDS, nx=True))
        if doc.code in self._docs:
            return False
        self._docs[doc.code] = doc.to_json()
        return True

    @asynccontextmanager
    async def lock(self, code: str) -> AsyncIterator[None]:
        """Short exclusive section for read-modify-write of one room (works across replicas)."""
        async with self._locks[code]:
            if self.redis is None:
                yield
                return
            key, token = LOCK.format(code=code), secrets.token_hex(8)
            deadline = time.monotonic() + LOCK_MS / 1000
            while not await self.redis.set(key, token, nx=True, px=LOCK_MS):
                if time.monotonic() > deadline:
                    raise RoomBusy()
                await asyncio.sleep(0.03)
            try:
                yield
            finally:
                with contextlib.suppress(RoomsUnavailable):  # the lock expires by itself if Redis went away
                    if (await self.redis.get(key)) in (token, token.encode()):
                        await self.redis.delete(key)

    # A game driver's heartbeat: present while some replica drives the room's game (V3 F3).

    async def heartbeat(self, code: str, ttl_ms: int) -> None:
        if self.redis is not None:
            await self.redis.set(DRIVER.format(code=code), "1", px=ttl_ms)
        else:
            self._beats[code] = time.monotonic() + ttl_ms / 1000

    async def heartbeat_alive(self, code: str) -> bool:
        if self.redis is not None:
            return bool(await self.redis.exists(DRIVER.format(code=code)))
        return self._beats.get(code, 0.0) > time.monotonic()

    async def set_active(self, code: str, active: bool) -> None:
        """Index of playing quiz and decision rooms, for the watchdog on every replica."""
        if self.redis is not None:
            if active:
                await self.redis.sadd(ACTIVE_GAMES, code)
            else:
                await self.redis.srem(ACTIVE_GAMES, code)
        elif active:
            self._active.add(code)
        else:
            self._active.discard(code)

    async def active_games(self) -> set[str]:
        if self.redis is not None:
            raw = await self.redis.smembers(ACTIVE_GAMES)
            return {c.decode() if isinstance(c, bytes) else str(c) for c in raw}
        return set(self._active)

    async def claim_driver(self, code: str, ttl_ms: int) -> bool:
        """One replica wins: the heartbeat key is set only when absent."""
        if self.redis is not None:
            return bool(await self.redis.set(DRIVER.format(code=code), "1", px=ttl_ms, nx=True))
        if self._beats.get(code, 0.0) > time.monotonic():
            return False
        self._beats[code] = time.monotonic() + ttl_ms / 1000
        return True

    async def publish(self, code: str, message: dict[str, Any]) -> None:
        text = json.dumps(message)
        if self.redis is not None:
            await self.redis.publish(CHANNEL.format(code=code), text)
            return
        for q in list(self._queues[code]):
            q.put_nowait(text)

    @asynccontextmanager
    async def subscribe(self, code: str) -> AsyncIterator[asyncio.Queue[str]]:
        queue: asyncio.Queue[str] = asyncio.Queue()
        if self.redis is None:
            self._queues[code].add(queue)
            try:
                yield queue
            finally:
                self._queues[code].discard(queue)
            return
        pubsub = self.redis.pubsub()
        with _redis_errors():
            await pubsub.subscribe(CHANNEL.format(code=code))

        async def pump() -> None:
            # Poll with a short timeout: the shared Redis client has a 1 s socket timeout, so a blocking
            # listen() would fail on a quiet room.
            while True:
                try:
                    msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.5)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    if "timeout" not in type(exc).__name__.lower():
                        log.warning("room pubsub read failed: %s", type(exc).__name__)
                        await asyncio.sleep(0.5)
                    continue
                if msg and msg.get("type") == "message":
                    data = msg["data"]
                    queue.put_nowait(data.decode() if isinstance(data, bytes) else str(data))

        task = asyncio.create_task(pump())
        try:
            yield queue
        finally:
            task.cancel()
            try:
                await pubsub.unsubscribe(CHANNEL.format(code=code))
                await pubsub.aclose()
            except Exception:  # noqa: S110 - best effort cleanup of a closed connection
                pass
