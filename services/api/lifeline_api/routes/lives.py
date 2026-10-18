"""Characters and lives: list, create, get, age, choices, actions, rewind, summary."""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from lifeline_api import challenges, macro, student_challenges
from lifeline_api.auth import OptionalSubject, Subject
from lifeline_api.errors import ApiError, not_found
from lifeline_api.explain_bridge import explain_new_events, explain_outcome
from lifeline_api.money import fill_personal
from lifeline_api.routes.later import has_entitlement
from lifeline_api.sim_bridge import call_pure
from lifeline_api.state import AppState, get_state
from lifeline_api.store import LifeRecord, macro_hash
from lifeline_contracts.api_models import (
    ActionRequest,
    CharactersResponse,
    ChoiceRequest,
    CreateLifeRequest,
    RewindRequest,
)
from lifeline_contracts.domain import (
    ActionResult,
    AgeResult,
    Challenge,
    CharacterSpec,
    ChoiceResult,
    Life,
    LifeSummary,
    RewindResult,
)
from lifeline_contracts.finance import LifeListItem, LivesResponse
from lifeline_contracts.macro import MacroTable
from lifeline_engine import api as engine_api
from lifeline_sim import api as sim_api

router = APIRouter(tags=["lives"])

LIFE_ID_PATTERN = r"^lf_[a-z0-9]{6,32}$"
LifeId = Annotated[str, Path(pattern=LIFE_ID_PATTERN)]
MAX_SEED = 2**31 - 1
PATH_PRESET_PREFIX = "path-"


def new_life_id() -> str:
    return f"lf_{secrets.token_hex(8)}"


def new_seed() -> int:
    return secrets.randbelow(MAX_SEED + 1)


async def _current_macro(state: AppState, *, persist: bool) -> tuple[MacroTable, str]:
    """Current table and its hash. `persist=True` stores the snapshot (life writes need it for replays).

    Read-only routes pass persist=False, so they keep working while Postgres is down.
    """
    table = await macro.table(state)
    digest = macro_hash(table)
    if persist:
        await state.store.put_macro(digest, table)  # StoreUnavailable -> 503 store_unavailable
    return table, digest


async def _load(state: AppState, life_id: str, owner: str) -> tuple[LifeRecord, MacroTable]:
    rec = await state.store.get(life_id, owner)
    if rec is None:
        raise not_found("Life not found")
    table = await state.store.get_macro(rec.macro_hash)
    if table is None:
        # The snapshot is gone (e.g. store reset). Replays may differ, so refuse rather than guess.
        raise ApiError(409, "macro_snapshot_missing", "The data snapshot for this life is no longer available")
    return rec, table


async def _random_character(seed: int, table: MacroTable) -> CharacterSpec:
    """A person from the synthetic population, labelled as simulated (ADR 0027). Same seed, same person."""
    drawn = await call_pure(engine_api.random_character, seed, table)
    return sim_api.label_simulated(drawn)


async def _challenges(state: AppState) -> list[Challenge]:
    cached: list[Challenge] | None = state.memo.get(("challenges",))
    if cached is None:
        cached = await call_pure(sim_api.challenges)
        state.memo[("challenges",)] = cached
    return cached


async def _after_write(state: AppState, sub: str, life: Life, *, reset: bool = False) -> None:
    await challenges.record(state, sub, life, await _challenges(state), reset=reset)


async def _presets() -> list[CharacterSpec]:
    return await call_pure(sim_api.presets)


@router.get("/v1/characters", response_model=CharactersResponse, response_model_exclude_none=True)
async def list_characters(
    request: Request,
    _sub: OptionalSubject,
    seed: Annotated[int | None, Query(ge=0, le=MAX_SEED)] = None,
) -> CharactersResponse:
    state = get_state(request)
    table, _ = await _current_macro(state, persist=False)
    # Student starts only (ADR 0052). Old preset ids still load through sim_api.presets().
    presets = await call_pure(sim_api.offered_presets, table)
    random_char = await _random_character(new_seed() if seed is None else seed, table)
    return CharactersResponse(presets=presets, random=random_char)


def _list_item(life: Life) -> LifeListItem:
    return LifeListItem(
        id=life.id,
        name=life.character.name,
        emoji=life.character.emoji,
        mode=life.mode,
        year=life.year,
        age=life.age,
        alive=life.alive,
        index=life.index.value,
        net_worth=life.finances.net_worth,
        ribbons=len(life.ribbons),
    )


@router.get("/v1/lives", response_model=LivesResponse, response_model_exclude_none=True)
async def list_lives(request: Request, sub: Subject) -> LivesResponse:
    records = await get_state(request).store.list_by_owner(sub)
    return LivesResponse(lives=[_list_item(r.life) for r in records])


@router.post("/v1/lives", status_code=201, response_model=Life, response_model_exclude_none=True)
async def create_life(body: CreateLifeRequest, request: Request, sub: Subject) -> Life:
    state = get_state(request)
    seed = new_seed() if body.seed is None else body.seed
    start_year = body.start_year
    if body.room_code is not None:
        # In a room the server owns the seed (and the start year the host picked), so everyone gets the same life.
        room = await state.rooms.get(body.room_code)
        if room is None or room.player_of(sub) is None:
            raise not_found("Room not found")
        seat = room.player_of(sub)
        if seat is not None and seat.get("life_id"):
            # The server already made this player's room life at start: return it, never a second one (V5).
            rec = await state.store.get(seat["life_id"], sub)
            if rec is not None:
                return rec.life
        seed = room.seed
        start_year = (room.options or {}).get("start_year") or room.start_year or start_year
        quick_student_id = (room.options or {}).get("quick_student_id")
        if quick_student_id:
            # The host picked a premade Quick Life student: everyone plays the same one (ADR 0064).
            table, digest = await _current_macro(state, persist=True)
            life = await call_pure(sim_api.quick_life, new_life_id(), seed=seed, macro=table,
                                   quick_student_id=quick_student_id, start_year=(room.options or {}).get("start_year"))
            return await _store_new(state, sub, body, life, digest)
    table, digest = await _current_macro(state, persist=True)

    path_id = body.path_id
    if path_id is None and body.mode == "preset" and (body.preset_id or "").startswith(PATH_PRESET_PREFIX):
        path_id = (body.preset_id or "").removeprefix(PATH_PRESET_PREFIX)  # offered path characters (W3)
    if path_id is not None:
        # Student path (ADR 0052): Same Life and Quick Life. The account name names the character.
        acct = await state.store.get_doc(sub, "account") or {}
        life = await call_pure(sim_api.new_path_life, new_life_id(), path_id, start_year, seed, table,
                               quick=body.quick, mode=body.mode, name=acct.get("display_name"))
        return await _store_new(state, sub, body, life, digest)

    character: CharacterSpec
    if body.mode == "preset":
        if not body.preset_id:
            raise ApiError(422, "validation_error", "preset_id: required when mode is preset")
        if body.preset_id == student_challenges.YOU:
            # Student challenges (scope "you") are scored on the user's own money, not on a game life.
            raise ApiError(422, "validation_error", "This challenge uses your own money, not a game life")
        match = next((p for p in await _presets() if p.id == body.preset_id), None)
        if match is None:
            raise not_found(f"Unknown preset {body.preset_id}")
        character = match
    elif body.mode == "random":
        # Same person as GET /v1/characters?seed=N: random_character(seed, same macro table).
        character = await _random_character(seed, table)
    else:
        if body.character is None:
            raise ApiError(422, "validation_error", f"character: required when mode is {body.mode}")
        character = body.character

    life = await call_pure(sim_api.new_life, new_life_id(), character, body.mode, start_year, seed, table)
    return await _store_new(state, sub, body, life, digest)


async def _store_new(state: AppState, sub: str, body: CreateLifeRequest, life: Life, digest: str) -> Life:
    if body.room_code is not None and life.room_code != body.room_code:
        life = life.model_copy(update={"room_code": body.room_code})
    life, _ = await explain_new_events(None, life)
    await state.store.create(LifeRecord(id=life.id, owner=sub, life=life, macro_hash=digest))
    await _after_write(state, sub, life)
    return life


async def _load_readable(state: AppState, life_id: str, sub: str) -> LifeRecord:
    """Read access: the owner, or a player in the same live room as the owner when the life was started in
    that room (Same Life results). Everyone else gets 404, so existence is not revealed. Read only."""
    rec = await state.store.get(life_id, sub)
    if rec is not None:
        return rec
    other = await state.store.get_any(life_id)
    code = other.life.room_code if other is not None else None
    if other is None or not code:
        raise not_found("Life not found")
    room = await state.rooms.get(code)  # None once the room has expired
    if room is None or room.player_of(sub) is None or room.player_of(other.owner) is None:
        raise not_found("Life not found")
    return other


@router.get("/v1/lives/{id}", response_model=Life, response_model_exclude_none=True)
async def get_life(id: LifeId, request: Request, sub: Subject) -> Life:  # noqa: A002
    rec = await _load_readable(get_state(request), id, sub)
    return rec.life


@router.post("/v1/lives/{id}/age", response_model=AgeResult, response_model_exclude_none=True)
async def age_life(id: LifeId, request: Request, sub: Subject) -> AgeResult:  # noqa: A002
    state = get_state(request)
    async with state.life_locks[id]:
        rec, table = await _load(state, id, sub)
        if rec.life.pending_events:
            raise ApiError(409, "pending_events", "Answer the open events before you age", source="sim")
        result = await call_pure(sim_api.age, rec.life, table)
        life, events = await explain_new_events(rec.life, result.life, result.events)
        result = result.model_copy(update={"life": life, "events": events})
        rec.life = result.life
        await state.store.save(rec)
        await _after_write(state, sub, rec.life)
    return result.model_copy(update={"lesson": await fill_personal(state, sub, result.lesson)})


@router.post("/v1/lives/{id}/choices", response_model=ChoiceResult, response_model_exclude_none=True)
async def choose_life(id: LifeId, body: ChoiceRequest, request: Request, sub: Subject) -> ChoiceResult:  # noqa: A002
    state = get_state(request)
    async with state.life_locks[id]:
        rec, table = await _load(state, id, sub)
        result = await call_pure(sim_api.choose, rec.life, body.event_id, body.choice_id, table)
        life, _ = await explain_new_events(rec.life, result.life)
        outcome = await explain_outcome(rec.life, body.event_id, result.outcome)
        result = result.model_copy(update={"life": life, "outcome": outcome})
        rec.life = result.life
        await state.store.save(rec)
        await _after_write(state, sub, rec.life)
    return result.model_copy(update={"lesson": await fill_personal(state, sub, result.lesson)})


@router.post("/v1/lives/{id}/actions", response_model=ActionResult, response_model_exclude_none=True)
async def act_life(id: LifeId, body: ActionRequest, request: Request, sub: Subject) -> ActionResult:  # noqa: A002
    state = get_state(request)
    async with state.life_locks[id]:
        rec, table = await _load(state, id, sub)
        result = await call_pure(sim_api.act, rec.life, body.tab, body.action_id, dict(body.params), table)
        life, _ = await explain_new_events(rec.life, result.life)
        result = result.model_copy(update={"life": life})
        rec.life = result.life
        await state.store.save(rec)
        await _after_write(state, sub, rec.life)
    return result.model_copy(update={"lesson": await fill_personal(state, sub, result.lesson)})


@router.post("/v1/lives/{id}/rewind", response_model=RewindResult, response_model_exclude_none=True)
async def rewind_life(id: LifeId, body: RewindRequest, request: Request, sub: Subject) -> RewindResult:  # noqa: A002
    state = get_state(request)
    async with state.life_locks[id]:
        rec, table = await _load(state, id, sub)
        if not rec.life.rewind.has_pass and await has_entitlement(state, sub, "rewind_pass"):
            rec.life = rec.life.model_copy(update={"rewind": rec.life.rewind.model_copy(update={"has_pass": True})})
        result = await call_pure(sim_api.rewind, rec.life, body.decision_id, table)
        life, _ = await explain_new_events(rec.life, result.life)
        result = result.model_copy(update={"life": life})
        rec.life = result.life
        await state.store.save(rec)
        await _after_write(state, sub, rec.life, reset=True)
    return result


@router.get("/v1/lives/{id}/summary", response_model=LifeSummary, response_model_exclude_none=True)
async def get_life_summary(id: LifeId, request: Request, sub: Subject) -> LifeSummary:  # noqa: A002
    state = get_state(request)
    rec = await _load_readable(state, id, sub)
    table = await state.store.get_macro(rec.macro_hash)  # the life's pinned table, for the habit score
    return await call_pure(sim_api.summary, rec.life, table)
