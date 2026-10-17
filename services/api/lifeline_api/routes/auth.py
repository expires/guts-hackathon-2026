"""POST /v1/auth/demo. POST /v1/auth/apple is Tier 2 (501 for now)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from lifeline_api.auth import demo_subject, issue_token
from lifeline_api.errors import not_implemented
from lifeline_api.state import get_state
from lifeline_contracts.api_models import AppleSignInRequest, DemoSignInRequest, Token

router = APIRouter(tags=["auth"])


@router.post("/v1/auth/demo", response_model=Token, response_model_exclude_none=True)
async def sign_in_demo(body: DemoSignInRequest, request: Request) -> Token:
    return issue_token(get_state(request), demo_subject(body.device_id))


@router.post("/v1/auth/apple", response_model=Token, response_model_exclude_none=True)
async def sign_in_with_apple(body: AppleSignInRequest) -> Token:
    raise not_implemented("Sign in with Apple")
