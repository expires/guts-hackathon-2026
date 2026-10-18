"""Learn: the financial literacy course on the Play tab (ADR 0068).

GET /v1/learn, GET /v1/learn/lessons/{lesson_id} (409 lesson_locked), POST .../attempts (graded here).
Lesson content is memoised in lifeline_sim.learn; only the user's progress is read per request.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from lifeline_api import learn_progress
from lifeline_api.auth import Subject
from lifeline_api.errors import ApiError, not_found
from lifeline_api.state import get_state
from lifeline_contracts.learn import LearnLesson, LearnPath, LessonAttemptRequest, LessonAttemptResult
from lifeline_sim import learn as sim_learn

router = APIRouter(tags=["learn"])


def _locked(lesson_id: str, passed: list[str], language: str) -> ApiError:
    path = sim_learn.build_lesson(lesson_id, passed, (), language)
    reason = path.summary.locked_reason or "Finish the lesson before this one first"
    return ApiError(409, "lesson_locked", reason, source="learn")


@router.get("/v1/learn", response_model=LearnPath, response_model_exclude_none=True)
async def get_learn_path(request: Request, sub: Subject, language: str = "en") -> LearnPath:
    state = get_state(request)
    passed = await learn_progress.passed(state, sub)
    bonus = await learn_progress.life_bonus(state, sub)
    return sim_learn.build_path(passed, bonus, language)


@router.get("/v1/learn/lessons/{lesson_id}", response_model=LearnLesson, response_model_exclude_none=True)
async def get_learn_lesson(lesson_id: str, request: Request, sub: Subject, language: str = "en") -> LearnLesson:
    if not sim_learn.has_lesson(lesson_id):
        raise not_found(f"Unknown lesson {lesson_id[:64]}")
    state = get_state(request)
    passed = await learn_progress.passed(state, sub)
    if sim_learn.status_of(lesson_id, passed) == "locked":
        raise _locked(lesson_id, passed, language)
    bonus = await learn_progress.life_bonus(state, sub)
    return sim_learn.build_lesson(lesson_id, passed, bonus, language)


@router.post("/v1/learn/lessons/{lesson_id}/attempts", response_model=LessonAttemptResult,
             response_model_exclude_none=True)
async def attempt_learn_lesson(lesson_id: str, body: LessonAttemptRequest, request: Request, sub: Subject,
                               language: str = "en") -> LessonAttemptResult:
    if not sim_learn.has_lesson(lesson_id):
        raise not_found(f"Unknown lesson {lesson_id[:64]}")
    state = get_state(request)
    async with state.subject_locks[f"{sub}:{learn_progress.DOC_LEARN}"]:
        passed = await learn_progress.passed(state, sub)
        if sim_learn.status_of(lesson_id, passed) == "locked":
            raise _locked(lesson_id, passed, language)
        bonus = await learn_progress.life_bonus(state, sub)
        result, after = sim_learn.grade(lesson_id, body.answers, passed, bonus, language)
        if after != passed:
            await learn_progress.save(state, sub, after)
    return result
