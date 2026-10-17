"""POST /v1/auth/demo and POST /v1/auth/apple. Logout lives in routes/account.py."""

from __future__ import annotations

import math

from fastapi import APIRouter, Request

from lifeline_api import account
from lifeline_api.apple import AppleTokenError, apple_subject
from lifeline_api.auth import demo_subject, issue_token
from lifeline_api.errors import ApiError, unauthorized
from lifeline_api.ratelimit import client_ip
from lifeline_api.state import get_state
from lifeline_contracts.api_models import AppleSignInRequest, DemoSignInRequest, Token

router = APIRouter(tags=["auth"])


@router.post("/v1/auth/demo", response_model=Token, response_model_exclude_none=True)
async def sign_in_demo(body: DemoSignInRequest, request: Request) -> Token:
    state = get_state(request)
    if state.auth_limiter is not None:
        wait = await state.auth_limiter.take(f"auth:{client_ip(request.scope)}")
        if wait > 0:
            raise ApiError(429, "rate_limited", "Too many sign-ins. Try again shortly.",
                           headers={"Retry-After": str(max(1, math.ceil(wait)))})
    sub = demo_subject(body.device_id)
    await account.ensure_quietly(state, sub)
    return issue_token(state, sub)


@router.post("/v1/auth/apple", response_model=Token, response_model_exclude_none=True)
async def sign_in_with_apple(body: AppleSignInRequest, request: Request) -> Token:
    """Verify the Apple identity token (RS256, Apple JWKS, audience APPLE_BUNDLE_ID), then issue our token."""
    state = get_state(request)
    if state.apple is None:
        raise unauthorized("Sign in with Apple is not configured")
    try:
        claims = await state.apple.verify(body.identity_token)
    except AppleTokenError as exc:
        raise unauthorized(f"Sign in with Apple failed: {exc}") from exc
    sub = apple_subject(claims["sub"])
    await account.ensure_quietly(state, sub)
    return issue_token(state, sub)
