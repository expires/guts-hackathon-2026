"""Concepts, the Real-life Decision and its evaluation (Tier 1)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Request

from lifeline_api.auth import OptionalSubject, Subject
from lifeline_api.money import fill_personal
from lifeline_api.sim_bridge import call_pure
from lifeline_api.state import get_state
from lifeline_api.store import macro_hash
from lifeline_contracts.api_models import ConceptsResponse, DecisionRequest
from lifeline_contracts.domain import Concept, Decision, Evaluation
from lifeline_engine import api as engine_api
from lifeline_sim import api as sim_api

router = APIRouter(tags=["learn"])


def utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@router.get("/v1/concepts", response_model=ConceptsResponse, response_model_exclude_none=True)
async def list_concepts(request: Request, sub: OptionalSubject) -> ConceptsResponse:
    state = get_state(request)
    table = await state.hub.macro_table()
    key = ("concepts", macro_hash(table))
    concepts: list[Concept] | None = state.memo.get(key)
    if concepts is None:
        concepts = await call_pure(sim_api.concepts, table)
        state.memo[key] = concepts
    if sub is not None:
        concepts = [c.model_copy(update={"lesson": await fill_personal(state, sub, c.lesson)}) for c in concepts]
    return ConceptsResponse(concepts=concepts)


@router.post("/v1/decisions", tags=["decision"], response_model=Decision, response_model_exclude_none=True)
async def create_decision(body: DecisionRequest, request: Request, sub: Subject) -> Decision:
    state = get_state(request)
    table = await state.hub.macro_table()
    now = datetime.now(UTC)
    decision = await call_pure(engine_api.decide, body.profile, table, now.year)
    # The engine has no clock. The server time replaces its placeholder.
    return decision.model_copy(update={"generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")})


@router.get("/v1/evaluation", tags=["decision"], response_model=Evaluation, response_model_exclude_none=True)
async def get_evaluation(request: Request) -> Evaluation:
    state = get_state(request)
    table = await state.hub.macro_table()
    key = ("evaluation", macro_hash(table))
    ev: Evaluation | None = state.memo.get(key)
    if ev is None:
        ev = await call_pure(engine_api.evaluate, table)
        state.memo[key] = ev
    return ev
