"""Tier 2 endpoints. They validate input, then answer 501 not_implemented until their tier."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Query

from lifeline_api.auth import Subject
from lifeline_api.errors import not_implemented
from lifeline_contracts.api_models import (
    BankAuthLink,
    BankSummary,
    ChallengesResponse,
    CreateRoomRequest,
    PurchaseVerifyRequest,
    PurchaseVerifyResponse,
    Room,
)

router = APIRouter()

RoomCode = Annotated[str, Path(pattern=r"^[A-Z0-9]{6}$")]


@router.get("/v1/challenges", tags=["learn"], response_model=ChallengesResponse, response_model_exclude_none=True)
async def list_challenges() -> ChallengesResponse:
    raise not_implemented("Challenges")


@router.post("/v1/rooms", tags=["rooms"], status_code=201, response_model=Room, response_model_exclude_none=True)
async def create_room(body: CreateRoomRequest, sub: Subject) -> Room:
    raise not_implemented("Rooms")


@router.get("/v1/rooms/{code}", tags=["rooms"], response_model=Room, response_model_exclude_none=True)
async def get_room(code: RoomCode, sub: Subject) -> Room:
    raise not_implemented("Rooms")


@router.get("/v1/bank/auth-link", tags=["bank"], response_model=BankAuthLink, response_model_exclude_none=True)
async def get_bank_auth_link(sub: Subject) -> BankAuthLink:
    raise not_implemented("Bank connection")


@router.get("/v1/bank/callback", tags=["bank"])
async def bank_callback(
    state: Annotated[str, Query(max_length=256)],
    code: Annotated[str | None, Query(max_length=2048)] = None,
    error: Annotated[str | None, Query(max_length=256)] = None,
) -> None:
    raise not_implemented("Bank connection")


@router.get("/v1/bank/summary", tags=["bank"], response_model=BankSummary, response_model_exclude_none=True)
async def get_bank_summary(session: Annotated[str, Query(max_length=128)], sub: Subject) -> BankSummary:
    raise not_implemented("Bank connection")


@router.post("/v1/purchases/verify", tags=["store"], response_model=PurchaseVerifyResponse,
             response_model_exclude_none=True)
async def verify_purchase(body: PurchaseVerifyRequest, sub: Subject) -> PurchaseVerifyResponse:
    raise not_implemented("Purchases")
