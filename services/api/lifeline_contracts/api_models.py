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
from lifeline_contracts.play import (
    DecisionPrompt,
    DecisionReveal,
    GameOptions,
    PlayerScore,
    QuickFeedback,
    QuickPlayerResult,
    QuickQuestion,
    QuizQuestion,
    QuizReveal,
    RoomGame,
)


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
    warming: bool = Field(default=False, description="True while the macro table and engine context build after start")


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
    room_code: str | None = Field(default=None, pattern=r"^[0-9]{4}$")
    path_id: ShortId | None = Field(default=None, description="Student start path (ADR 0052)")
    quick: bool = Field(default=False, description="Quick Life: ages 18 to 25, 2 or 3 events with choices")


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
    life_id: str | None = Field(default=None, description="Set for life challenges; None for scope 'you'")
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
    """Lobby first (ADR 0052): an empty body opens a lobby; the host picks the game later.
    Names come from the account; host_name is only a fallback."""

    mode: RoomMode | None = Field(default=None, description="Omit: 2 players = duel, more = group at start")
    host_name: str | None = Field(default=None, min_length=1, max_length=24)
    preset_id: ShortId | None = None
    start_year: int | None = Field(default=None, ge=1990, le=2026)


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
    code: str = Field(pattern=r"^[0-9]{4}$", description="4-digit room code, easy to read aloud (ADR 0064)")
    mode: RoomMode
    seed: int
    preset_id: str | None = None
    start_year: int | None = None
    game: RoomGame | None = Field(default=None, description="Picked by the host in the lobby")
    options: GameOptions | None = None
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
    type: Literal[
        "join",
        "ready",
        "progress",
        "finish",
        "start",
        "leave",
        "ping",
        "pick_game",
        "answer",
        "end_round",
        "play_again",
    ]
    player_id: str | None = Field(default=None, max_length=64, description="Resume token after a reconnect")
    name: str | None = Field(default=None, max_length=24)
    life_id: str | None = None
    age: int | None = None
    year: int | None = None
    net_worth: float | None = None
    index: float | None = None
    game: RoomGame | None = Field(default=None, description="pick_game (host only)")
    options: GameOptions | None = Field(default=None, description="pick_game (host only)")
    question_id: str | None = Field(default=None, max_length=64, description="answer: quiz question or decision prompt")
    choice_id: str | None = Field(default=None, max_length=64, description="answer")


class WsServerMessage(_M):
    type: Literal[
        "roster",
        "rival",
        "started",
        "finished",
        "error",
        "pong",
        "welcome",
        "game_picked",
        "question",
        "quiz_reveal",
        "decision",
        "decision_reveal",
        "ranking",
        "ql_question",
        "ql_feedback",
        "ql_results",
    ]
    you: Player | None = Field(default=None, description="Sent with 'welcome': your player id for reconnects")
    room: Room | None = None
    player: Player | None = None
    error: ErrorBody | None = None
    question: QuizQuestion | None = None
    quiz_reveal: QuizReveal | None = None
    decision: DecisionPrompt | None = None
    decision_reveal: DecisionReveal | None = None
    ranking: list[PlayerScore] | None = None
    ql_question: QuickQuestion | None = Field(default=None, description="Quick Life: your next question (ADR 0074)")
    ql_feedback: QuickFeedback | None = Field(default=None, description="Quick Life: points for your last answer")
    ql_results: list[QuickPlayerResult] | None = Field(
        default=None, description="Quick Life: final results, sent with 'finished' once everyone is done"
    )
    winner_line: str | None = Field(
        default=None,
        max_length=200,
        description="Penny announces the winner in one line, sent with 'finished' (ADR 0064)",
    )
