"""HS256 JWT issue and verify. Bearer dependency for protected routes."""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
from typing import Annotated, Any

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from lifeline_api.errors import unauthorized
from lifeline_api.state import AppState, get_state
from lifeline_contracts.api_models import Token

ISSUER = "lifeline-api"
ALGORITHM = "HS256"
REVOKED_PREFIX = "lifeline:revoked:"

log = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)


def demo_subject(device_id: str) -> str:
    """Stable, opaque subject for a demo device. The raw device id is not stored in the token."""
    digest = hashlib.sha256(f"demo:{device_id}".encode()).hexdigest()[:24]
    return f"demo_{digest}"


def issue_token(state: AppState, subject: str, now: int | None = None) -> Token:
    ttl = state.settings.jwt_ttl_seconds
    iat = int(time.time()) if now is None else now
    iat_ms = int(time.time() * 1000) if now is None else now * 1000
    claims = {"sub": subject, "iss": ISSUER, "iat": iat, "exp": iat + ttl, "jti": secrets.token_hex(12),
              "iatm": iat_ms}
    token = jwt.encode(claims, state.jwt_secret, algorithm=ALGORITHM)
    return Token(access_token=token, token_type="bearer", expires_in=ttl)  # noqa: S106


def decode_token(state: AppState, token: str) -> dict[str, Any] | None:
    """Verified claims, or None if the token is invalid or expired. Does not check revocation."""
    try:
        claims: dict[str, Any] = jwt.decode(
            token, state.jwt_secret, algorithms=[ALGORITHM], issuer=ISSUER, options={"require": ["sub", "exp", "iat"]}
        )
    except jwt.PyJWTError:
        return None
    sub = claims.get("sub")
    return claims if isinstance(sub, str) and sub else None


def verify_token(state: AppState, token: str) -> str | None:
    """Return the subject, or None if the token is invalid or expired. Sync: no revocation check."""
    claims = decode_token(state, token)
    return None if claims is None else str(claims["sub"])


def _revocation_id(claims: dict[str, Any], token: str) -> str:
    jti = claims.get("jti")
    return str(jti) if isinstance(jti, str) and jti else hashlib.sha256(token.encode()).hexdigest()[:32]


async def revoke(state: AppState, token: str) -> None:
    """Add the token to the denylist until it expires (Redis, so every replica sees it)."""
    claims = decode_token(state, token)
    if claims is None:
        return
    rid = _revocation_id(claims, token)
    ttl = max(1, int(claims["exp"]) - int(time.time()))
    state.revoked_local[rid] = time.time() + ttl
    if state.redis is not None:
        try:
            await state.redis.set(f"{REVOKED_PREFIX}{rid}", "1", ex=ttl)
        except Exception as exc:
            log.warning("token denylist write failed: %s", type(exc).__name__)


async def is_revoked(state: AppState, claims: dict[str, Any], token: str) -> bool:
    rid = _revocation_id(claims, token)
    until = state.revoked_local.get(rid)
    if until is not None and until > time.time():
        return True
    if state.redis is not None:
        try:
            return bool(await state.redis.exists(f"{REVOKED_PREFIX}{rid}"))
        except Exception as exc:
            log.warning("token denylist read failed: %s", type(exc).__name__)
    return False


DOC_REVOKED_BEFORE = "revoked_before"
REVOKED_BEFORE_PREFIX = "lifeline:revoked-before:"


def _issued_ms(claims: dict[str, Any]) -> int:
    iatm = claims.get("iatm")
    return int(iatm) if isinstance(iatm, int) else int(claims["iat"]) * 1000


async def revoke_all(state: AppState, sub: str) -> None:
    """Reject every token of `sub` issued before now (account deletion). Redis for every replica,
    Postgres so it survives a Redis flush. Raises StoreUnavailable when Postgres cannot record it."""
    now_ms = int(time.time() * 1000)
    state.revoked_before_local[sub] = now_ms
    if state.redis is not None:
        try:
            await state.redis.set(f"{REVOKED_BEFORE_PREFIX}{sub}", str(now_ms), ex=state.settings.jwt_ttl_seconds)
        except Exception as exc:
            log.warning("revoked-before write to redis failed: %s", type(exc).__name__)
    await state.store.put_doc(sub, DOC_REVOKED_BEFORE, {"ms": now_ms})


async def _revoked_before(state: AppState, sub: str) -> int | None:
    """Cut-off for `sub`, or None. With Redis, Redis is the shared answer (the key lives as long as any token
    can). Without Redis (dev), the Postgres record is read."""
    local = state.revoked_before_local.get(sub)
    if state.redis is not None:
        try:
            raw = await state.redis.get(f"{REVOKED_BEFORE_PREFIX}{sub}")
            return local if raw is None else max(int(raw), local or 0)
        except Exception as exc:
            log.warning("revoked-before read from redis failed: %s", type(exc).__name__)
    try:
        doc = await state.store.get_doc(sub, DOC_REVOKED_BEFORE)
    except Exception:
        return local
    return local if doc is None else max(int(doc["ms"]), local or 0)


async def _checked_subject(state: AppState, token: str) -> str | None:
    claims = decode_token(state, token)
    if claims is None or await is_revoked(state, claims, token):
        return None
    sub = str(claims["sub"])
    cutoff = await _revoked_before(state, sub)
    if cutoff is not None and _issued_ms(claims) < cutoff:
        return None
    return sub


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
    sub = await _checked_subject(get_state(request), creds.credentials)
    if sub is None:
        raise unauthorized("Invalid or expired token")
    return sub


async def optional_subject(
    request: Request,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str | None:
    if creds is None:
        return None
    return await _checked_subject(get_state(request), creds.credentials)


Subject = Annotated[str, Depends(require_subject)]
OptionalSubject = Annotated[str | None, Depends(optional_subject)]
