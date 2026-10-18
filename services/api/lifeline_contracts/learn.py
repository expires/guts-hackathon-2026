"""Learn: the financial literacy course on the Play tab (ADR 0068). BOSS-owned.

Six units in student-lifecycle order. A lesson opens only when the previous one is passed.
Lesson text is fixed (written, not AI-generated); every lesson carries at least one real UK number from the
facts table with its official source. The server grades the quiz, so the answers never reach the client first.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from lifeline_contracts.domain import ShortId


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


LessonStatus = Literal["locked", "open", "passed"]


class LessonCard(_M):
    """One idea per card."""

    title: str = Field(max_length=60)
    text: str = Field(max_length=280)


class LessonFact(_M):
    """A real UK number from the facts table (lifeline_engine/rules.py), with its official source."""

    text: str = Field(max_length=200, description="e.g. 'You repay 9% of what you earn above £25,000 a year.'")
    source_label: str = Field(max_length=120, description="e.g. 'gov.uk · Repaying your student loan'")
    source_url: str = Field(max_length=500)
    checked: str = Field(description="ISO date the fact was checked against the source")


class LessonChoice(_M):
    id: ShortId
    text: str = Field(max_length=120)


class LessonQuestion(_M):
    """No answer here: the server grades it (POST /v1/learn/lessons/{id}/attempts)."""

    id: ShortId
    text: str = Field(max_length=240)
    choices: list[LessonChoice] = Field(min_length=2, max_length=4)


class LessonSummary(_M):
    id: ShortId
    unit_id: ShortId
    index: int = Field(ge=0, description="Position in the unit, from 0")
    title: str = Field(max_length=60)
    icon: str = Field(max_length=60, description="SF Symbol name that matches the concept")
    status: LessonStatus
    locked_reason: str | None = Field(default=None, max_length=120, description="'Finish <previous lesson> first'")
    life_bonus: bool = Field(default=False, description="Also earned as a bonus in a Life game")
    concept_id: str | None = Field(default=None, description="Life game concept this lesson teaches, if any")


class Unit(_M):
    id: ShortId
    index: int = Field(ge=0)
    title: str = Field(max_length=40)
    description: str = Field(max_length=160)
    lessons: list[LessonSummary]
    done: int = Field(ge=0)
    total: int = Field(ge=1)


class LearnPath(_M):
    units: list[Unit] = Field(min_length=1, max_length=8)
    next_lesson_id: ShortId | None = Field(default=None, description="First open lesson; None when all are passed")
    done: int = Field(ge=0)
    total: int = Field(ge=1)


class LearnLesson(_M):
    """A full lesson. A locked lesson returns 409 `lesson_locked` instead."""

    summary: LessonSummary
    cards: list[LessonCard] = Field(min_length=2, max_length=3)
    facts: list[LessonFact] = Field(min_length=1, max_length=3)
    quiz: list[LessonQuestion] = Field(min_length=3, max_length=3)
    pass_mark: int = Field(default=2, ge=1, le=3)


class LessonAttemptRequest(_M):
    answers: dict[str, str] = Field(description="question id -> choice id", max_length=3)


class LessonAnswerResult(_M):
    question_id: ShortId
    correct: bool
    correct_choice_id: ShortId
    explanation: str = Field(max_length=200)


class LessonAttemptResult(_M):
    passed: bool
    correct: int = Field(ge=0, le=3)
    pass_mark: int = Field(ge=1, le=3)
    results: list[LessonAnswerResult]
    unlocked_lesson_id: ShortId | None = Field(default=None, description="The next lesson, opened by this pass")
    path: LearnPath
