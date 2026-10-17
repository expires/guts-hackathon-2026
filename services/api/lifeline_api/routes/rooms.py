"""Same Life rooms: POST/GET /v1/rooms and the WebSocket /v1/rooms/{code}?token=.

WebSocket flow (contract x-websocket):
1. Client sends `join` (name; `player_id` to resume after sleep). Server answers `welcome` (you, room)
   and broadcasts `roster`.
2. `ready` marks the player ready. The host sends `start` once at least 2 players are ready: the server
   creates every player's life from the room preset and seed, then broadcasts `started`.
3. After each AGE the client sends `progress`. The server reads that player's stored life and broadcasts
   `rival` with the server's numbers. `finish` ends that player's run; when all have finished the server
   broadcasts `finished` (the results comparison).
4. `leave` leaves the lobby (or disconnects during play). A dropped connection keeps the seat for 10 min.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
import secrets
import time
from typing import Annotated, Any

from fastapi import APIRouter, Path, Request, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from lifeline_api.auth import Subject, _checked_subject
from lifeline_api.errors import ApiError, not_found
from lifeline_api.rooms import MAX_PLAYERS, RoomBusy, RoomDoc, join_url, new_code, qr_png_base64
from lifeline_api.routes.lives import new_life_id
from lifeline_api.sim_bridge import call_pure
from lifeline_api.state import AppState, get_state
from lifeline_api.store import LifeRecord, macro_hash
from lifeline_contracts.api_models import CreateRoomRequest, ErrorBody, Room, WsClientMessage, WsServerMessage
from lifeline_contracts.macro import MacroTable
from lifeline_sim import api as sim_api

log = logging.getLogger(__name__)

router = APIRouter(tags=["rooms"])

RoomCode = Annotated[str, Path(pattern=r"^[A-Z0-9]{6}$")]
MIN_PLAYERS_TO_START = 2
CODE_RE = re.compile(r"[A-Z0-9]{6}")


@router.post("/v1/rooms", status_code=201, response_model=Room, response_model_exclude_none=True)
async def create_room(body: CreateRoomRequest, request: Request, sub: Subject) -> Room:
    state = get_state(request)
    presets = await call_pure(sim_api.presets)
    if not any(p.id == body.preset_id for p in presets):
        raise not_found(f"Unknown preset {body.preset_id}")
    for _ in range(10):
        code = new_code()
        doc = RoomDoc(code=code, mode=body.mode, seed=secrets_seed(), preset_id=body.preset_id,
                      start_year=body.start_year, max_players=MAX_PLAYERS[body.mode], qr=qr_png_base64(join_url(code)))
        doc.add_player(sub, body.host_name, host=True)
        if await state.rooms.create(doc):
            return doc.public()
    raise ApiError(503, "unavailable", "Could not create a room. Try again.")


def secrets_seed() -> int:
    return secrets.randbelow(2**31)


@router.get("/v1/rooms/{code}", response_model=Room, response_model_exclude_none=True)
async def get_room(code: RoomCode, request: Request, sub: Subject) -> Room:
    doc = await get_state(request).rooms.get(code)
    if doc is None:
        raise not_found("Room not found")
    return doc.public()


# ---------- WebSocket ----------


def _msg(type_: str, **kw: Any) -> dict[str, Any]:
    return WsServerMessage(type=type_, **kw).model_dump(mode="json", exclude_none=True)


def _error(code: str, message: str) -> dict[str, Any]:
    return _msg("error", error=ErrorBody(code=code, message=message, source="rooms"))


class RoomError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


async def _broadcast_roster(state: AppState, doc: RoomDoc) -> None:
    await state.rooms.publish(doc.code, _msg("roster", room=doc.public()))


async def _join(state: AppState, code: str, sub: str, msg: WsClientMessage) -> dict[str, Any]:
    """Seat the caller. Resumes the caller's seat (by player_id or by account) when it exists."""
    async with state.rooms.lock(code):
        doc = await state.rooms.get(code)
        if doc is None:
            raise RoomError("not_found", "Room not found")
        doc.drop_stale(time.time())
        player = doc.player(msg.player_id) if msg.player_id else None
        if player is not None and player["sub"] != sub:
            raise RoomError("forbidden", "That seat belongs to someone else")
        player = player or doc.player_of(sub)
        if player is None:
            if doc.status != "lobby":
                raise RoomError("already_started", "This game has already started")
            if len(doc.players) >= doc.max_players:
                raise RoomError("room_full", "This room is full")
            player = doc.add_player(sub, msg.name or "Player")
        elif msg.name and doc.status == "lobby":
            player["name"] = msg.name[:24]
        player["connected"] = True
        player["last_seen"] = time.time()
        await state.rooms.put(doc)
    await _broadcast_roster(state, doc)
    return {"welcome": _msg("welcome", you=RoomDoc.public_player(player), room=doc.public()), "player_id": player["id"]}


async def _create_lives(state: AppState, doc: RoomDoc, table: MacroTable) -> None:
    """The server owns the seed and the state: one life per player, same preset, seed and start year."""
    presets = await call_pure(sim_api.presets)
    character = next(p for p in presets if p.id == doc.preset_id)
    digest = macro_hash(table)
    await state.store.put_macro(digest, table)
    doc.macro_hash = digest
    for p in doc.players:
        life = await call_pure(sim_api.new_life, new_life_id(), character, "preset", doc.start_year, doc.seed, table)
        life = life.model_copy(update={"room_code": doc.code})
        await state.store.create(LifeRecord(id=life.id, owner=p["sub"], life=life, macro_hash=digest))
        p.update(life_id=life.id, age=life.age, year=life.year, net_worth=round(life.finances.net_worth, 2),
                 index=life.index.value)


async def _refresh_from_life(state: AppState, p: dict[str, Any]) -> None:
    if not p.get("life_id"):
        return
    rec = await state.store.get(p["life_id"], p["sub"])
    if rec is None:
        return
    life = rec.life
    p.update(age=life.age, year=life.year, net_worth=round(life.finances.net_worth, 2), index=life.index.value)
    if not life.alive:
        p["finished"] = True


async def _handle(state: AppState, code: str, player_id: str, msg: WsClientMessage) -> dict[str, Any] | None:
    """Apply one client message. Returns a direct reply for the sender, if any. Broadcasts go via pub/sub."""
    if msg.type == "ping":
        return _msg("pong")
    if msg.type == "join":
        return _error("already_joined", "You are already in this room")
    out: list[dict[str, Any]] = []
    # Slow I/O (the macro table may need a live fetch) happens before the room lock is taken.
    table = await state.hub.macro_table() if msg.type == "start" else None
    async with state.rooms.lock(code):
        doc = await state.rooms.get(code)
        if doc is None:
            raise RoomError("not_found", "Room not found")
        p = doc.player(player_id)
        if p is None:
            raise RoomError("not_in_room", "You are not in this room")
        p["last_seen"] = time.time()
        if msg.type == "ready":
            if doc.status != "lobby":
                return _error("already_started", "This game has already started")
            p["ready"] = True
            out.append(_msg("roster", room=doc.public()))
        elif msg.type == "start":
            if not p["is_host"]:
                return _error("not_host", "Only the host can start")
            if doc.status != "lobby":
                return _error("already_started", "This game has already started")
            ready = [x for x in doc.players if x["ready"]]
            if len(ready) < MIN_PLAYERS_TO_START or len(ready) != len(doc.players):
                return _error("not_ready", f"Everyone must be ready, and at least {MIN_PLAYERS_TO_START} players")
            assert table is not None
            await _create_lives(state, doc, table)
            doc.status = "playing"
            out.append(_msg("started", room=doc.public()))
        elif msg.type in ("progress", "finish"):
            if doc.status == "lobby":
                return _error("not_started", "The game has not started")
            await _refresh_from_life(state, p)
            if msg.type == "finish":
                p["finished"] = True
            out.append(_msg("rival", player=RoomDoc.public_player(p)))
            if doc.status == "playing" and all(x["finished"] for x in doc.players):
                doc.status = "finished"
                for x in doc.players:
                    await _refresh_from_life(state, x)
                out.append(_msg("finished", room=doc.public()))
        elif msg.type == "leave":
            if doc.status == "lobby":
                was_host = p["is_host"]
                doc.players = [x for x in doc.players if x["id"] != player_id]
                if was_host and doc.players:
                    doc.players[0]["is_host"] = True
            else:
                p["connected"] = False
            out.append(_msg("roster", room=doc.public()))
        await state.rooms.put(doc)
    for m in out:
        await state.rooms.publish(code, m)
    return None


async def _disconnected(state: AppState, code: str, player_id: str) -> None:
    async with state.rooms.lock(code):
        doc = await state.rooms.get(code)
        if doc is None:
            return
        p = doc.player(player_id)
        if p is None:
            return
        p["connected"] = False
        p["last_seen"] = time.time()
        await state.rooms.put(doc)
    await _broadcast_roster(state, doc)


@router.websocket("/v1/rooms/{code}")
async def room_socket(websocket: WebSocket, code: str) -> None:
    state: AppState = websocket.app.state.lifeline
    token = websocket.query_params.get("token", "")
    sub = await _checked_subject(state, token) if token else None
    await websocket.accept()
    if sub is None:
        await websocket.send_json(_error("unauthorized", "Missing or invalid token"))
        await websocket.close(code=4401)
        return
    if not CODE_RE.fullmatch(code):
        await websocket.send_json(_error("not_found", "Room not found"))
        await websocket.close(code=4404)
        return

    async with state.rooms.subscribe(code) as queue:
        player_id: str | None = None

        async def forward() -> None:
            while True:
                await websocket.send_text(await queue.get())

        pump = asyncio.create_task(forward())
        try:
            while True:
                try:
                    raw = await websocket.receive_text()
                    msg = WsClientMessage.model_validate(json.loads(raw))
                except (ValidationError, json.JSONDecodeError):
                    await websocket.send_json(_error("validation_error", "Message does not match WsClientMessage"))
                    continue
                try:
                    if player_id is None:
                        if msg.type != "join":
                            await websocket.send_json(_error("join_first", "Send join first"))
                            continue
                        joined = await _join(state, code, sub, msg)
                        player_id = joined["player_id"]
                        await websocket.send_json(joined["welcome"])
                        continue
                    reply = await _handle(state, code, player_id, msg)
                    if reply is not None:
                        await websocket.send_json(reply)
                    if msg.type == "leave":
                        break
                except RoomBusy:
                    await websocket.send_json(_error("busy", "The room is busy. Try again."))
                except RoomError as exc:
                    await websocket.send_json(_error(exc.code, exc.message))
                    if exc.code in ("not_found", "room_full", "already_started", "forbidden"):
                        break
        except WebSocketDisconnect:
            pass
        finally:
            pump.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await pump
            if player_id is not None:
                with contextlib.suppress(Exception):
                    await _disconnected(state, code, player_id)
    with contextlib.suppress(Exception):
        await websocket.close()
