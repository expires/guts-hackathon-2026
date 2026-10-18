"""Concepts, the Real-life Decision and its evaluation (Tier 1)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Request

from lifeline_api import challenges, macro, money, student_challenges
from lifeline_api.auth import OptionalSubject, Subject
from lifeline_api.errors import ApiError
from lifeline_api.money import fill_personal
from lifeline_api.sim_bridge import call_pure
from lifeline_api.state import get_state
from lifeline_api.store import StoreUnavailable, macro_hash
from lifeline_contracts.api_models import ChallengeProgress, ChallengesResponse, ConceptsResponse, DecisionRequest
from lifeline_contracts.domain import Concept, Decision, Evaluation
from lifeline_contracts.play import PathsResponse
from lifeline_engine import api as engine_api
from lifeline_sim import api as sim_api

router = APIRouter(tags=["learn"])


def utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@router.get("/v1/concepts", response_model=ConceptsResponse, response_model_exclude_none=True)
async def list_concepts(request: Request, sub: OptionalSubject) -> ConceptsResponse:
    state = get_state(request)
    table = await macro.table(state)
    key = ("concepts", macro_hash(table))
    concepts: list[Concept] | None = state.memo.get(key)
    if concepts is None:
        try:
            concepts = await call_pure(sim_api.concepts, table)
        except ApiError as exc:
            if exc.code != "data_unavailable":
                raise
            concepts = await call_pure(sim_api.concepts, None)  # Lessons without a real-data chart.
        state.memo[key] = concepts
    if sub is not None:
        concepts = [c.model_copy(update={"lesson": await fill_personal(state, sub, c.lesson)}) for c in concepts]
    return ConceptsResponse(concepts=concepts)


@router.post("/v1/decisions", tags=["decision"], response_model=Decision, response_model_exclude_none=True)
async def create_decision(body: DecisionRequest, request: Request, sub: Subject) -> Decision:
    state = get_state(request)
    table = await macro.table(state)
    now = datetime.now(UTC)
    decision = await call_pure(engine_api.decide, body.profile, table, now.year)
    # The engine has no clock. The server time replaces its placeholder.
    return decision.model_copy(update={"generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")})


@router.get("/v1/evaluation", tags=["decision"], response_model=Evaluation, response_model_exclude_none=True)
async def get_evaluation(request: Request, sub: OptionalSubject) -> Evaluation:
    """"How good is the advice?". The mortgage backtest covers mortgage moves. A student's moves (budget,
    safety fund, debt, Lifetime ISA) have no past periods to test against yet, so a student gets an honest
    "not enough history" result (n=0) instead of a mortgage backtest that does not apply to them."""
    state = get_state(request)
    if sub is not None:
        snap = await money.maybe_snapshot(state, sub)
        if snap is not None and snap.is_student and snap.mortgage is None:
            return Evaluation(method=STUDENT_EVALUATION_TEXT, n=0, hit_rate=0.0, baseline_hit_rate=0.0,
                              baseline="None yet", periods=[], generated_at=utc_now_iso())
    table = await macro.table(state)
    key = ("evaluation", macro_hash(table))
    ev: Evaluation | None = state.memo.get(key)
    if ev is None:
        ev = await call_pure(engine_api.evaluate, table)
        state.memo[key] = ev
    return ev


STUDENT_EVALUATION_TEXT = (
    "Not enough history yet. Student moves are checked against your own months of data, and there are no "
    "past periods to test them on. The mortgage backtest does not apply to you."
)


@router.get("/v1/challenges", response_model=ChallengesResponse, response_model_exclude_none=True)
async def list_challenges(request: Request, sub: OptionalSubject) -> ChallengesResponse:
    """Student challenges (ADR 0052) scored on the caller's own money data, plus W3's student-path life
    challenges scored after every life write. Old character challenges are no longer offered."""
    state = get_state(request)
    today = datetime.now(UTC).date()
    life_items = [c for c in await call_pure(sim_api.challenges) if c.character_id.startswith("path-")]
    items = [*student_challenges.challenges(today), *life_items]
    if sub is None:
        return ChallengesResponse(challenges=items)
    progress: list[ChallengeProgress] = []
    snap = await money.maybe_snapshot(state, sub)
    if snap is not None:
        for c in student_challenges.challenges(today):
            status, detail = student_challenges.evaluate(c, snap, today)
            progress.append(ChallengeProgress(challenge_id=c.id, life_id=None,
                                              status=status, detail=detail[:200]))
    try:
        entries = await challenges.progress(state, sub)
    except StoreUnavailable:
        entries = []  # The list still works while saving is down.
    life_ids = {c.id for c in life_items}
    progress += [ChallengeProgress(challenge_id=e["challenge_id"], life_id=e["life_id"], status=e["status"],
                                   detail=(e.get("detail") or None) and str(e["detail"])[:200])
                 for e in entries if e["challenge_id"] in life_ids]
    return ChallengesResponse(challenges=items, progress=progress)


@router.get("/v1/paths", tags=["play"], response_model=PathsResponse, response_model_exclude_none=True)
async def list_paths(sub: Subject) -> PathsResponse:
    """Student start paths (W3): university, apprenticeship, job at 18, gap year, master's; and the premade
    Quick Life students the host can pick (ADR 0064)."""
    return PathsResponse(paths=await call_pure(sim_api.paths), quick_students=await call_pure(sim_api.quick_students))
