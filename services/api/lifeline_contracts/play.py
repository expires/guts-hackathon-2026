"""Play with friends and Play solo, Direction V2 (ADR 0052). BOSS-owned.

Lobby first, game second: the host opens a lobby, friends join, then the host picks Money Quiz, Same Decision
or Same Life. Quick Life is a short Same Life on one student path.
Privacy rule: nothing here carries a user's real £ amounts, balances, income, transactions or merchants.
Game money (Same Decision outcomes, Same Life net worth) is simulated and labelled as game money.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from lifeline_contracts.domain import ShortId
from lifeline_contracts.finance import HabitScore


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


RoomGame = Literal["quiz", "same_decision", "same_life"]


# ---------- student paths and Quick Life ----------


class StudentPath(_M):
    """A Play solo or Quick Life start: university, apprenticeship, job at 18, gap year, master's."""

    id: ShortId
    title: str = Field(max_length=40)
    description: str = Field(max_length=160)
    start_age: int = Field(ge=16, le=30)
    quick: bool = Field(description="Offered in Quick Life (ages 18 to 25 in 5 to 6 taps)")


class PathsResponse(_M):
    paths: list[StudentPath]


class GameOptions(_M):
    """Options on the host's one small sheet."""

    path_id: ShortId | None = Field(default=None, description="Same Life / Quick Life student path")
    quick: bool = Field(default=True, description="Same Life as a Quick Life round")
    start_year: int | None = Field(default=None, ge=1990, le=2026, description="Same Life / Same Decision history year")
    questions: int = Field(default=8, ge=3, le=15, description="Money Quiz length")
    topic: Literal["mixed", "student_finance", "saving", "debt", "tax"] = "mixed"


# ---------- Money Quiz ----------


class QuizChoice(_M):
    id: ShortId
    text: str = Field(max_length=120)


class QuizQuestion(_M):
    """From lessons and the facts table only; each carries its official source (ADR 0058)."""

    id: ShortId
    index: int = Field(ge=0)
    total: int = Field(ge=1)
    text: str = Field(max_length=240)
    choices: list[QuizChoice] = Field(min_length=2, max_length=4)
    answer_ms: int = Field(default=15_000, ge=5_000, le=30_000)
    source_label: str = Field(max_length=120, description="e.g. 'gov.uk · Student loan repayment'")
    source_url: str | None = Field(default=None, max_length=500)


class PlayerScore(_M):
    player_id: str
    name: str
    score: int = Field(ge=0)
    rank: int = Field(ge=1)
    last_correct: bool | None = None


class QuizReveal(_M):
    question_id: ShortId
    correct_choice_id: ShortId
    explanation: str = Field(max_length=200, description="Penny's one line")
    source_label: str = Field(max_length=120)
    source_url: str | None = Field(default=None, max_length=500)
    ranking: list[PlayerScore]


# ---------- Same Decision ----------


class DecisionOption(_M):
    id: ShortId
    label: str = Field(max_length=80)


class DecisionPrompt(_M):
    """One student money decision in one piece of history, the same for everyone."""

    id: ShortId
    year: int = Field(ge=1990, le=2026)
    context: str = Field(max_length=240, description="What was happening that year, from real data")
    text: str = Field(max_length=200)
    options: list[DecisionOption] = Field(min_length=2, max_length=4)
    answer_ms: int = Field(default=20_000, ge=5_000, le=60_000)


class DecisionOutcome(_M):
    option_id: ShortId
    game_money_change: float = Field(description="Simulated game money, never the player's real money")
    note: str = Field(max_length=160)


class PlayerChoice(_M):
    player_id: str
    name: str
    option_id: ShortId | None = Field(default=None, description="None when the player did not answer in time")


class DecisionReveal(_M):
    prompt_id: ShortId
    choices: list[PlayerChoice]
    outcomes: list[DecisionOutcome]
    penny_line: str = Field(max_length=200)
    ranking: list[PlayerScore]


# ---------- Circles (habits, ratios only) ----------


class CircleMember(_M):
    id: str
    name: str = Field(max_length=24)
    habits: HabitScore
    improvement: int | None = Field(default=None, ge=-100, le=100, description="Overall points vs own baseline")
    rank: int | None = Field(default=None, ge=1, description="Rank by improvement, not by score or income")
    is_you: bool = False


class Circle(_M):
    id: ShortId
    name: str = Field(max_length=40)
    code: str = Field(pattern=r"^[A-Z0-9]{6}$")
    members: list[CircleMember] = Field(max_length=30)
    recap: str | None = Field(default=None, max_length=400, description="Penny's weekly recap, ratios only")
    recap_week: str | None = Field(default=None, description="ISO week, e.g. 2026-W42")


class CirclesResponse(_M):
    circles: list[Circle]


class CreateCircleRequest(_M):
    name: str = Field(min_length=1, max_length=40)


class JoinCircleRequest(_M):
    code: str = Field(pattern=r"^[A-Z0-9]{6}$")
