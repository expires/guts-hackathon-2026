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

from lifeline_api import games, macro
from lifeline_api.auth import Subject, _checked_subject
from lifeline_api.errors import ApiError, not_found
from lifeline_api.names import clean_name
from lifeline_api.rooms import LOBBY_MAX_PLAYERS, MAX_PLAYERS, RoomBusy, RoomDoc, join_url, new_code, qr_png_base64
from lifeline_api.routes.lives import new_life_id
from lifeline_api.sim_bridge import call_pure
from lifeline_api.state import AppState, get_state
from lifeline_api.store import LifeRecord, macro_hash
from lifeline_contracts.api_models import CreateRoomRequest, ErrorBody, Room, WsClientMessage, WsServerMessage
from lifeline_contracts.macro import MacroTable
from lifeline_contracts.play import GameOptions
from lifeline_sim import api as sim_api

log = logging.getLogger(__name__)

router = APIRouter(tags=["rooms"])

RoomCode = Annotated[str, Path(pattern=r"^[A-Z0-9]{6}$")]
MIN_PLAYERS_TO_START = 2
CODE_RE = re.compile(r"[A-Z0-9]{6}")


@router.post("/v1/rooms", status_code=201, response_model=Room, response_model_exclude_none=True)
async def create_room(body: CreateRoomRequest, request: Request, sub: Subject) -> Room:
    """Lobby first (ADR 0059): an empty body opens a lobby. The host picks the game later; without a mode the
    room is a duel or a group by the number of players at start."""
    state = get_state(request)
    if body.preset_id is not None and not body.preset_id.startswith("path-"):
        presets = await call_pure(sim_api.presets)
        if not any(p.id == body.preset_id for p in presets):
            raise not_found(f"Unknown preset {body.preset_id}")
    name = await _display_name(state, sub) or clean_name(body.host_name, 24) or "Player 1"
    for _ in range(10):
        code = new_code()
        doc = RoomDoc(code=code, mode=body.mode or "group", seed=secrets_seed(), preset_id=body.preset_id,
                      start_year=body.start_year,
                      max_players=MAX_PLAYERS[body.mode] if body.mode else LOBBY_MAX_PLAYERS,
                      qr=qr_png_base64(join_url(code)), mode_fixed=body.mode is not None)
        if body.preset_id is not None:
            doc.game = "same_life"
        doc.add_player(sub, name, host=True)
        if await state.rooms.create(doc):
            await state.rooms.track(sub, code)
            return doc.public()
    raise ApiError(503, "unavailable", "Could not create a room. Try again.")


async def _display_name(state: AppState, sub: str) -> str | None:
    """Names come from the account (Me.display_name)."""
    try:
        doc = await state.store.get_doc(sub, "account")
    except Exception:
        return None
    return clean_name((doc or {}).get("display_name"), 24)


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
    account_name = await _display_name(state, sub)
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
            player = doc.add_player(sub, account_name or clean_name(msg.name, 24) or f"Player {len(doc.players) + 1}")
        elif clean_name(msg.name, 24) and doc.status == "lobby" and not account_name:
            player["name"] = clean_name(msg.name, 24)
        player["connected"] = True
        player["last_seen"] = time.time()
        await state.rooms.put(doc)
    await state.rooms.track(sub, code)
    await _broadcast_roster(state, doc)
    return {"welcome": _msg("welcome", you=RoomDoc.public_player(player), room=doc.public()), "player_id": player["id"]}


async def _create_lives(state: AppState, doc: RoomDoc, table: MacroTable) -> None:
    """The server owns the seed and the state: one life per player, same preset, seed and start year."""
    presets = await call_pure(sim_api.presets)
    path_id = (doc.preset_id or "").removeprefix("path-") if (doc.preset_id or "").startswith("path-") else None
    character = next((p for p in presets if p.id == doc.preset_id), None)
    if (character is None and path_id is None) or doc.start_year is None:
        raise RoomError("game_unavailable", "Pick a start for Same Life first")
    digest = macro_hash(table)
    await state.store.put_macro(digest, table)
    doc.macro_hash = digest
    for p in doc.players:
        if path_id is not None:
            life = await call_pure(sim_api.new_path_life, new_life_id(), path_id, doc.start_year, doc.seed, table,
                                   mode="preset")
        else:
            assert character is not None
            life = await call_pure(sim_api.new_life, new_life_id(), character, "preset", doc.start_year, doc.seed,
                                   table)
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
    driver: Any = None
    # Slow I/O (the macro table may need a live fetch) happens before the room lock is taken.
    table = await macro.table(state) if msg.type == "start" else None
    async with state.rooms.lock(code):
        doc = await state.rooms.get(code)
        if doc is None:
            raise RoomError("not_found", "Room not found")
        p = doc.player(player_id)
        if p is None:
            raise RoomError("not_in_room", "You are not in this room")
        p["last_seen"] = time.time()
        if msg.type == "pick_game":
            if not p["is_host"]:
                return _error("not_host", "Only the host can pick the game")
            if doc.status != "lobby":
                return _error("already_started", "This game has already started")
            if msg.game is None:
                return _error("validation_error", "game: required")
            opts = msg.options or GameOptions()
            doc.game = msg.game
            doc.options = opts.model_dump(mode="json")
            if opts.start_year is not None:
                doc.start_year = opts.start_year
            out.append(_msg("game_picked", room=doc.public()))
        elif msg.type == "answer":
            if doc.status != "playing" or doc.game not in ("quiz", "same_decision"):
                return _error("not_open", "There is no question to answer")
            err = games.record_answer(doc, player_id, msg.question_id, msg.choice_id)
            if err is not None:
                return _error(err, "That answer was not counted")
        elif msg.type == "ready":
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
            if not doc.mode_fixed:
                doc.mode = "duel" if len(doc.players) == 2 else "group"
            opts = GameOptions.model_validate(doc.options or {})
            game = doc.game or "same_life"
            try:
                if game == "quiz":
                    items = await call_pure(games.quiz_items, opts, doc.seed)
                    driver = games.run_quiz(state, code, items, _msg)
                elif game == "same_decision":
                    assert table is not None
                    item = await call_pure(games.decision_item, opts, doc.seed, table)
                    driver = games.run_decision(state, code, item, _msg)
                elif doc.preset_id is not None:
                    assert table is not None
                    await _create_lives(state, doc, table)  # preset rooms: the server creates every life
                # Path rooms (Same Life, Quick Life): each client creates its own life with the room seed and
                # room_code, then names it in its first `progress`.
            except (games.GameUnavailable, ApiError) as exc:
                return _error("game_unavailable", str(exc))
            doc.game = game
            doc.game_state = {"scores": {x["id"]: 0 for x in doc.players}}
            doc.status = "playing"
            out.append(_msg("started", room=doc.public()))
        elif msg.type in ("progress", "finish"):
            if doc.status == "lobby":
                return _error("not_started", "The game has not started")
            if msg.life_id and msg.life_id != p.get("life_id"):
                rec = await state.store.get(msg.life_id, p["sub"])
                if rec is None or rec.life.room_code != code:
                    return _error("not_found", "That life is not yours in this room")
                p["life_id"] = msg.life_id
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
    if msg.type == "start" and driver is not None:
        games.launch(state, driver)  # timing is server-side, after `started` went out
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


async def leave_all_rooms(state: AppState, sub: str) -> None:
    """Judge mode reset: take the user out of every room and lobby. Empty rooms are deleted; a new host is
    chosen when the host leaves. Other players get a roster update."""
    for code in await state.rooms.rooms_of(sub):
        async with state.rooms.lock(code):
            doc = await state.rooms.get(code)
            if doc is None or doc.player_of(sub) is None:
                continue
            was_host = bool(doc.player_of(sub)["is_host"])  # type: ignore[index]
            doc.players = [p for p in doc.players if p["sub"] != sub]
            if not doc.players:
                await state.rooms.delete(code)
                continue
            if was_host:
                doc.players[0]["is_host"] = True
            await state.rooms.put(doc)
        await _broadcast_roster(state, doc)
    await state.rooms.untrack_all(sub)
