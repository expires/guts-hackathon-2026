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

from lifeline_api import codeguard, games, macro, money, samples
from lifeline_api.auth import Subject, _checked_subject
from lifeline_api.errors import ApiError, not_found
from lifeline_api.names import clean_name
from lifeline_api.ratelimit import client_ip
from lifeline_api.rooms import (
    LOBBY_MAX_PLAYERS,
    MAX_PLAYERS,
    RoomBusy,
    RoomDoc,
    RoomsUnavailable,
    join_url,
    new_code,
    qr_png_base64,
)
from lifeline_api.routes.lives import new_life_id
from lifeline_api.sim_bridge import call_pure
from lifeline_api.state import AppState, get_state
from lifeline_api.store import LifeRecord, macro_hash
from lifeline_contracts.api_models import CreateRoomRequest, ErrorBody, Room, WsClientMessage, WsServerMessage
from lifeline_contracts.macro import MacroTable
from lifeline_contracts.play import GameOptions, PlayerScore
from lifeline_sim import api as sim_api

log = logging.getLogger(__name__)

router = APIRouter(tags=["rooms"])

RoomCode = Annotated[str, Path(pattern=r"^[0-9]{4}$")]
MIN_PLAYERS_TO_START = 2
CODE_RE = re.compile(r"[0-9]{4}")
ROOMS_DOWN = "Play with friends is unavailable right now. Try again shortly."
CREATE_ATTEMPTS = 50  # 10,000 codes; a few hundred live rooms at most


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
    for _ in range(CREATE_ATTEMPTS):
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
    """Names come from the account (Me.display_name). A demo account has none: then the imported sample
    student's first name is used (V5), else the caller falls back to "Player N"."""
    try:
        doc = await state.store.get_doc(sub, "account")
    except Exception:
        return None
    name = clean_name((doc or {}).get("display_name"), 24)
    if name:
        return name
    try:
        own = await money.stored_snapshot(state, sub)
    except Exception:
        return None
    if own is None or own.source != "sample" or not own.persona:
        return None
    hint = samples.hints(own.persona) or {}
    first = str(hint.get("name") or "").split(" ")[0] or (own.holder.name.split(" ")[0] if own.holder else "")
    return clean_name(first, 24)


def _for_outsider(room: Room) -> Room:
    """Player count only: no names, ids or lives for someone without a seat (V6 final F-1)."""
    players = [p.model_copy(update={"id": f"seat-{i + 1}", "name": f"Player {i + 1}", "life_id": None})
               for i, p in enumerate(room.players)]
    return room.model_copy(update={"players": players})


def secrets_seed() -> int:
    return secrets.randbelow(2**31)


@router.get("/v1/rooms/{code}", response_model=Room, response_model_exclude_none=True)
async def get_room(code: RoomCode, request: Request, sub: Subject) -> Room:
    """The room. A player with a seat sees everyone; anyone else sees only how many players there are."""
    state = get_state(request)
    ip = client_ip(request.scope)
    doc = await state.rooms.get(code)
    if doc is not None and doc.player_of(sub) is not None:
        return doc.public()  # a seated player is never blocked
    await codeguard.guard(state, ip, sub)
    if doc is None:
        await codeguard.record_wrong(state, ip, sub)
        raise not_found("Room not found")
    return _for_outsider(doc.public())
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
    return {"welcome": _msg("welcome", you=RoomDoc.public_player(player), room=doc.public()), "player_id": player["id"],
            # A player who reconnects mid-round gets the open question again (V3 F3).
            "resend": games.open_round_message(doc, _msg) if doc.status == "playing" else None,
            "resume": doc.status == "playing" and doc.game in ("quiz", "same_decision")}


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


async def _create_quick_lives(state: AppState, doc: RoomDoc, opts: GameOptions, table: MacroTable) -> None:
    """Quick Life on a premade student (ADR 0064): every player gets the same student, seed and events."""
    digest = macro_hash(table)
    await state.store.put_macro(digest, table)
    doc.macro_hash = digest
    for p in doc.players:
        life = await call_pure(sim_api.quick_life, new_life_id(), seed=doc.seed, macro=table,
                               quick_student_id=opts.quick_student_id, start_year=opts.start_year)
        life = life.model_copy(update={"room_code": doc.code})
        await state.store.create(LifeRecord(id=life.id, owner=p["sub"], life=life, macro_hash=digest))
        p.update(life_id=life.id, age=life.age, year=life.year, net_worth=round(life.finances.net_worth, 2),
                 index=life.index.value, finished=False)


async def _life_results(state: AppState, doc: RoomDoc) -> tuple[list[PlayerScore], str]:
    """Same Life / Quick Life result (ADR 0064): rank by INDEX, then habit score. Score = INDEX points.
    The winner line is a template; every number comes from the result."""
    rows: list[tuple[float, int, dict[str, Any]]] = []
    for p in doc.players:
        habit = -1
        rec = await state.store.get(p["life_id"], p["sub"]) if p.get("life_id") else None
        if rec is not None:
            table = await state.store.get_macro(rec.macro_hash)
            hs = await call_pure(sim_api.habit_score, rec.life, table)
            habit = hs.overall if hs is not None and hs.overall is not None else -1
        rows.append((float(p.get("index") or 0.0), habit, p))
    rows.sort(key=lambda r: (-r[0], -r[1], r[2]["name"]))
    ranking: list[PlayerScore] = []
    for i, (index, habit, p) in enumerate(rows):
        tie = i > 0 and (rows[i - 1][0], rows[i - 1][1]) == (index, habit)
        ranking.append(PlayerScore(player_id=p["id"], name=p["name"], score=max(0, round(index)),
                                   rank=ranking[-1].rank if tie else i + 1))
    if not rows:
        return ranking, ""
    index, habit, winner = rows[0]
    line = f"{winner['name']} wins with an INDEX of {index:.0f}"
    line += f" and a habit score of {habit} out of 100." if habit >= 0 else "."
    return ranking, line


def _finished_msg(doc: RoomDoc, line: str) -> dict[str, Any]:
    """`finished` with the room and Penny's one-line winner announcement (template, numbers from the result)."""
    return _msg("finished", room=doc.public(), winner_line=line[:200] or None)


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
    start_driver = False
    restart = False
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
            if doc.status == "playing" and doc.game in ("quiz", "same_decision"):
                # The host restarts a stuck game (its driver died, e.g. an API restart), V3 F3.
                restart = True
            elif doc.status != "lobby":
                return _error("already_started", "This game has already started")
            else:
                p["ready"] = True  # the host's Start is the host's ready; the app shows the host as ready
                ready = [x for x in doc.players if x["ready"]]
                if len(ready) < MIN_PLAYERS_TO_START or len(ready) != len(doc.players):
                    return _error("not_ready", f"Everyone must be ready, and at least {MIN_PLAYERS_TO_START} players")
                if not doc.mode_fixed:
                    doc.mode = "duel" if len(doc.players) == 2 else "group"
                opts = GameOptions.model_validate(doc.options or {})
                game = doc.game or "same_life"
                doc.game_state = {"scores": {x["id"]: 0 for x in doc.players}}
                try:
                    if game == "quiz":
                        games.store_quiz(doc, await call_pure(games.quiz_items, opts, doc.seed))
                    elif game == "same_decision":
                        assert table is not None
                        games.store_decision(doc, await call_pure(games.decision_item, opts, doc.seed, table))
                    elif opts.quick_student_id is not None:
                        assert table is not None
                        await _create_quick_lives(state, doc, opts, table)  # same premade student for everyone
                    elif doc.preset_id is not None:
                        assert table is not None
                        await _create_lives(state, doc, table)  # preset rooms: the server creates every life
                    # Path rooms (Same Life, Quick Life): each client creates its own life with the room seed
                    # and room_code, then names it in its first `progress`.
                except (games.GameUnavailable, ApiError) as exc:
                    return _error("game_unavailable", str(exc))
                doc.game = game
                doc.status = "playing"
                restart = False
                out.append(_msg("started", room=doc.public()))
            start_driver = doc.game in ("quiz", "same_decision")
            if restart and start_driver and games.local_driver_running(state, code):
                return _error("already_started", "This game is running")
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
                ranking, line = await _life_results(state, doc)
                out.append(_msg("ranking", ranking=ranking))
                out.append(_finished_msg(doc, line))
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
    if msg.type == "start" and start_driver:
        await state.rooms.set_active(code, True)
        if restart:
            await games.restart_driver(state, code, _msg)  # the host restarts a stalled game at once
        else:
            await games.ensure_driver(state, code, _msg)  # timing is server-side, after `started` went out
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

    try:
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
                            ip = client_ip(websocket.scope)
                            existing = await state.rooms.get(code)
                            seated = existing is not None and existing.player_of(sub) is not None
                            if not seated and await codeguard.is_blocked(state, ip, sub):
                                raise RoomError("rate_limited", "Too many wrong codes. Try again in a minute.")
                            try:
                                joined = await _join(state, code, sub, msg)
                            except RoomError as exc:
                                if exc.code == "not_found":
                                    await codeguard.record_wrong(state, ip, sub)
                                raise
                            player_id = joined["player_id"]
                            await websocket.send_json(joined["welcome"])
                            if joined["resend"] is not None:
                                await websocket.send_json(joined["resend"])
                            if joined["resume"]:
                                await games.ensure_driver(state, code, _msg)  # after an API restart
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
                        if exc.code in ("not_found", "room_full", "already_started", "forbidden", "rate_limited"):
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
    except RoomsUnavailable:
        # Redis is down (V3 F2): say so and close cleanly; the client offers to try again.
        with contextlib.suppress(Exception):
            await websocket.send_json(_error("rooms_unavailable", ROOMS_DOWN))
            await websocket.close(code=1011)
        return
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


def start_watchdog(state: AppState) -> asyncio.Task[None]:
    """Every replica re-claims games whose driver died (V3 final)."""
    return asyncio.create_task(games.watchdog(state, _msg))
