"""Request and response envelopes for the HTTP API. Mirrors contracts/openapi.yaml."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from lifeline_contracts.domain import (
    Challenge,
    CharacterSpec,
    Concept,
    DecisionProfile,
    LifeMode,
    ParamKey,
    ParamText,
    ShortId,
    Tab,
)
from lifeline_contracts.observation import SourceStatus, Status


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorBody(_M):
    code: str = Field(description="Stable machine code, e.g. not_found, validation_error, rate_limited")
    message: str
    source: str = Field(description="Component or data source that raised it, e.g. api, sim, boe")


class Error(_M):
    error: ErrorBody


class Health(_M):
    status: Literal["ok", "degraded"]
    version: str
    product: str
    time: str
    checks: dict[str, Literal["ok", "down", "skipped"]]


class SourcesResponse(_M):
    sources: list[SourceStatus]


class CharactersResponse(_M):
    presets: list[CharacterSpec]
    random: CharacterSpec


class CreateLifeRequest(_M):
    mode: LifeMode
    start_year: int = Field(ge=1990, le=2026)
    preset_id: ShortId | None = Field(default=None, description="Required when mode=preset")
    character: CharacterSpec | None = Field(default=None, description="Required when mode=self or god")
    seed: int | None = Field(default=None, ge=0, le=2**31 - 1, description="Omit for a random seed")
    room_code: str | None = Field(default=None, pattern=r"^[A-Z0-9]{6}$")


class ChoiceRequest(_M):
    event_id: str = Field(min_length=1, max_length=64)
    choice_id: str = Field(min_length=1, max_length=64)


class ActionRequest(_M):
    tab: Tab
    action_id: str = Field(min_length=1, max_length=64)
    params: dict[ParamKey, float | ParamText] = Field(default_factory=dict, max_length=10)


class RewindRequest(_M):
    decision_id: str = Field(min_length=1, max_length=64)


class ConceptsResponse(_M):
    concepts: list[Concept]


class ChallengeProgress(_M):
    challenge_id: str
    life_id: str
    status: Literal["in_progress", "won", "lost"]
    detail: str | None = Field(default=None, max_length=200)


class ChallengesResponse(_M):
    challenges: list[Challenge]
    progress: list[ChallengeProgress] = Field(default_factory=list, description="Caller's progress, when signed in")


class DecisionRequest(_M):
    profile: DecisionProfile
    life_id: ShortId | None = Field(default=None, description="Optional 'Play yourself' life that reached the present")


RoomMode = Literal["duel", "group", "class"]


class CreateRoomRequest(_M):
    mode: RoomMode
    host_name: str = Field(min_length=1, max_length=24)
    preset_id: ShortId
    start_year: int = Field(ge=1990, le=2026)


class Player(_M):
    id: str
    name: str
    is_host: bool
    ready: bool = False
    connected: bool = True
    life_id: str | None = None
    age: int | None = None
    year: int | None = None
    net_worth: float | None = None
    index: float | None = None
    finished: bool = False


class Room(_M):
    code: str = Field(pattern=r"^[A-Z0-9]{6}$")
    mode: RoomMode
    seed: int
    preset_id: str
    start_year: int
    max_players: int = Field(ge=2, le=8)
    players: list[Player]
    join_url: str
    qr_png_base64: str
    status: Literal["lobby", "playing", "finished"]


class BankAuthLink(_M):
    url: str
    state: str
    provider: str
    status: Status


class BankSummary(_M):
    status: Status
    provider: str
    profile: DecisionProfile
    accounts: int


class PurchaseVerifyRequest(_M):
    product_id: Literal["lifeline.rewindpass", "lifeline.godmode", "lifeline.bossmode"]
    transaction_jws: str | None = Field(default=None, max_length=20000)
    demo: bool = True


class PurchaseVerifyResponse(_M):
    product_id: str
    entitlement: Literal["rewind_pass", "god_mode", "boss_mode"]
    active: bool
    demo: bool
    label: str


class AppleSignInRequest(_M):
    identity_token: str = Field(min_length=10, max_length=8000)


class DemoSignInRequest(_M):
    device_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9-]+$")


class Token(_M):
    access_token: str
    token_type: Literal["bearer"]
    expires_in: int


# WebSocket messages (documented in openapi as x-websocket on /v1/rooms/{code}).


class WsClientMessage(_M):
    type: Literal["join", "ready", "progress", "finish", "start", "leave", "ping"]
    player_id: str | None = Field(default=None, max_length=64, description="Resume token after a reconnect")
    name: str | None = Field(default=None, max_length=24)
    life_id: str | None = None
    age: int | None = None
    year: int | None = None
    net_worth: float | None = None
    index: float | None = None


class WsServerMessage(_M):
    type: Literal["roster", "rival", "started", "finished", "error", "pong", "welcome"]
    you: Player | None = Field(default=None, description="Sent with 'welcome': your player id for reconnects")
    room: Room | None = None
    player: Player | None = None
    error: ErrorBody | None = None
