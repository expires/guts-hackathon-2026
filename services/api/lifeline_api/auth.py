"""HS256 JWT issue and verify. Bearer dependency for protected routes."""

from __future__ import annotations

import hashlib
import time
from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from lifeline_api.errors import unauthorized
from lifeline_api.state import AppState, get_state
from lifeline_contracts.api_models import Token

ISSUER = "lifeline-api"
ALGORITHM = "HS256"

_bearer = HTTPBearer(auto_error=False)


def demo_subject(device_id: str) -> str:
    """Stable, opaque subject for a demo device. The raw device id is not stored in the token."""
    digest = hashlib.sha256(f"demo:{device_id}".encode()).hexdigest()[:24]
    return f"demo_{digest}"


def issue_token(state: AppState, subject: str, now: int | None = None) -> Token:
    ttl = state.settings.jwt_ttl_seconds
    iat = int(time.time()) if now is None else now
    claims = {"sub": subject, "iss": ISSUER, "iat": iat, "exp": iat + ttl}
    token = jwt.encode(claims, state.jwt_secret, algorithm=ALGORITHM)
    return Token(access_token=token, token_type="bearer", expires_in=ttl)  # noqa: S106


def verify_token(state: AppState, token: str) -> str | None:
    """Return the subject, or None if the token is invalid or expired."""
    try:
        claims = jwt.decode(
            token, state.jwt_secret, algorithms=[ALGORITHM], issuer=ISSUER, options={"require": ["sub", "exp", "iat"]}
        )
    except jwt.PyJWTError:
        return None
    sub = claims.get("sub")
    return sub if isinstance(sub, str) and sub else None


def bearer_subject(request: Request) -> str | None:
    """Subject from the Authorization header, or None. Used by the rate limiter (no error raised)."""
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return verify_token(get_state(request), token.strip())


async def require_subject(
    request: Request,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str:
    if creds is None or creds.scheme.lower() != "bearer":
        raise unauthorized()
    sub = verify_token(get_state(request), creds.credentials)
    if sub is None:
        raise unauthorized("Invalid or expired token")
    return sub


async def optional_subject(
    request: Request,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str | None:
    if creds is None:
        return None
    return verify_token(get_state(request), creds.credentials)


Subject = Annotated[str, Depends(require_subject)]
OptionalSubject = Annotated[str | None, Depends(optional_subject)]
