"""Monzo OAuth 2.0 authorization-code flow helpers (no web framework imports).

The state parameter is single use and expires after OUR OWN CSRF window (not a Monzo limit).
Secrets (client secret, codes, tokens) are never logged or placed in exception messages.
"""

import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from playyourself.adapters._http import request_json
from playyourself.adapters.base import SourceError
from playyourself.adapters.credentials import CredentialStore
from playyourself.settings import Settings

# Verified against docs.monzo.com (Oct 2026): auth params, token grants and token response
# fields. Refresh tokens are one-time use (the new one always replaces the old) and only
# confidential clients receive them.
AUTH_PARAMS = ("client_id", "redirect_uri", "response_type", "state")
GRANT_AUTH_CODE = "authorization_code"
GRANT_REFRESH = "refresh_token"
TOKEN_FIELDS = ("access_token", "refresh_token", "expires_in")

STATE_TTL_SECONDS = 600  # our own CSRF window


@dataclass(frozen=True)
class PendingAuth:
    expires: float
    remember: bool = False


class OAuthStateStore:
    """In-memory single-use state values with an expiry."""

    def __init__(
        self, ttl_seconds: float = STATE_TTL_SECONDS, clock: Callable[[], float] = time.time
    ):
        self._ttl = ttl_seconds
        self._clock = clock
        self._states: dict[str, PendingAuth] = {}

    def issue(self, remember: bool = False) -> str:
        now = self._clock()
        self._states = {s: p for s, p in self._states.items() if p.expires > now}
        state = secrets.token_urlsafe(32)
        self._states[state] = PendingAuth(now + self._ttl, remember)
        return state

    def consume(self, state: str | None) -> PendingAuth | None:
        """Single use: returns the pending auth if valid and unexpired, else None."""
        if not state:
            return None
        pending = self._states.pop(state, None)
        return pending if pending is not None and pending.expires > self._clock() else None


def is_configured(settings: Settings) -> bool:
    return bool(settings.monzo_client_id)


def authorize_url(settings: Settings, state: str) -> str:
    params = {
        "client_id": settings.monzo_client_id,
        "redirect_uri": settings.monzo_redirect_uri,
        "response_type": "code",
        "state": state,
    }
    sep = "&" if "?" in settings.monzo_auth_url else "?"
    return settings.monzo_auth_url + sep + urlencode(params)


def _creds_from_token_response(payload: Any, previous_refresh: str | None = None) -> dict:
    if not isinstance(payload, dict) or not isinstance(payload.get("access_token"), str):
        raise SourceError("bad_data", "monzo token response missing access_token")
    creds: dict[str, Any] = {"access_token": payload["access_token"]}
    refresh = payload.get("refresh_token") or previous_refresh
    if isinstance(refresh, str) and refresh:
        creds["refresh_token"] = refresh
    expires_in = payload.get("expires_in")
    if isinstance(expires_in, int | float) and not isinstance(expires_in, bool):
        creds["expires_at"] = time.time() + float(expires_in)  # only if the provider says so
    return creds


async def _post_token(settings: Settings, form: dict[str, str], client: httpx.AsyncClient | None):
    if client is not None:
        return await request_json(
            client, "POST", settings.monzo_token_url, source="monzo", data=form
        )
    async with httpx.AsyncClient(timeout=settings.source_timeout_seconds) as c:
        return await request_json(c, "POST", settings.monzo_token_url, source="monzo", data=form)


async def exchange_code(
    settings: Settings, code: str, client: httpx.AsyncClient | None = None
) -> dict:
    form = {
        "grant_type": GRANT_AUTH_CODE,
        "client_id": settings.monzo_client_id,
        "client_secret": settings.monzo_client_secret,
        "redirect_uri": settings.monzo_redirect_uri,
        "code": code,
    }
    return _creds_from_token_response(await _post_token(settings, form, client))


async def refresh_access_token(
    settings: Settings, store: CredentialStore, client: httpx.AsyncClient | None = None
) -> str | None:
    """Try one refresh. Returns the new access token and updates the store, or None."""
    current = store.get("monzo")
    refresh = current.get("refresh_token") if current else None
    if not refresh or not settings.monzo_client_id:
        return None
    form = {
        "grant_type": GRANT_REFRESH,
        "client_id": settings.monzo_client_id,
        "client_secret": settings.monzo_client_secret,
        "refresh_token": refresh,
    }
    try:
        creds = _creds_from_token_response(
            await _post_token(settings, form, client), previous_refresh=refresh
        )
    except SourceError:
        return None
    store.update("monzo", creds)
    return creds["access_token"]
