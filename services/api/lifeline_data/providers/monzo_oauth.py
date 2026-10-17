"""Monzo OAuth 2.0 authorization-code flow helpers (no web framework imports).

Verified against docs.monzo.com (Oct 2026): the authorize URL takes client_id, redirect_uri,
response_type=code and state; the token endpoint takes a form-encoded POST for the
authorization_code grant (client_id, client_secret, redirect_uri, code) and the refresh_token grant
(client_id, client_secret, refresh_token). Only Confidential clients receive refresh tokens, and a
refresh invalidates the previous refresh token, so the new one always replaces the old.

The state value is single use and expires after OUR OWN CSRF window (10 minutes, not a Monzo limit).
Secrets (client secret, codes, tokens) are never logged or placed in exception messages.
"""

from __future__ import annotations

import json
import secrets
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

from lifeline_data.providers._http import ProviderError, request_json
from lifeline_data.settings import DataSettings

GRANT_AUTH_CODE = "authorization_code"
GRANT_REFRESH = "refresh_token"
STATE_TTL_SECONDS = 600


@dataclass(frozen=True)
class PendingAuth:
    expires: float
    subject: str
    remember: bool = True


class OAuthStateStore:
    """Single-use state values with an expiry. Maps state -> subject.

    With a `path`, pending sign-ins are also saved to disk (0600) so a server restart mid sign-in
    (e.g. `--reload` picking up a code change while the user waits for Monzo's email) doesn't turn
    a valid sign-in into "bad state"."""

    def __init__(
        self,
        ttl_seconds: float = STATE_TTL_SECONDS,
        clock: Callable[[], float] = time.time,
        path: Path | None = None,
    ) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._path = path
        self._states: dict[str, PendingAuth] = self._load()

    def _load(self) -> dict[str, PendingAuth]:
        if self._path is None:
            return {}
        try:
            raw = json.loads(self._path.read_text())
            return {s: PendingAuth(**p) for s, p in raw.items()}
        except (OSError, ValueError, TypeError):
            return {}

    def _save(self) -> None:
        if self._path is not None:
            from lifeline_data.providers.store import write_private_json  # avoid an import cycle

            write_private_json(self._path, {s: asdict(p) for s, p in self._states.items()})

    def issue(self, subject: str, remember: bool = True) -> str:
        now = self._clock()
        self._states = {s: p for s, p in self._states.items() if p.expires > now}
        state = secrets.token_urlsafe(32)
        self._states[state] = PendingAuth(now + self._ttl, subject, remember)
        self._save()
        return state

    def consume(self, state: str | None) -> PendingAuth | None:
        """Single use: the pending auth if valid and unexpired, else None."""
        if not state:
            return None
        pending = self._states.pop(state, None)
        self._save()
        return pending if pending is not None and pending.expires > self._clock() else None


def is_configured(settings: DataSettings) -> bool:
    return bool(settings.monzo_client_id and settings.monzo_client_secret)


def authorize_url(settings: DataSettings, state: str) -> str:
    params = {
        "client_id": settings.monzo_client_id,
        "redirect_uri": settings.monzo_redirect_uri,
        "response_type": "code",
        "state": state,
    }
    sep = "&" if "?" in settings.monzo_auth_url else "?"
    return settings.monzo_auth_url + sep + urlencode(params)


def _creds_from_token_response(payload: Any, previous_refresh: str | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict) or not isinstance(payload.get("access_token"), str):
        raise ProviderError("bad_data", "monzo token response missing access_token", source="monzo")
    creds: dict[str, Any] = {"access_token": payload["access_token"]}
    refresh = payload.get("refresh_token") or previous_refresh
    if isinstance(refresh, str) and refresh:
        creds["refresh_token"] = refresh
    expires_in = payload.get("expires_in")
    if isinstance(expires_in, int | float) and not isinstance(expires_in, bool):
        creds["expires_at"] = time.time() + float(expires_in)
    return creds


async def _post_token(settings: DataSettings, form: dict[str, str], client: httpx.AsyncClient) -> Any:
    return await request_json(client, "POST", settings.monzo_token_url, source="monzo", data=form)


async def exchange_code(settings: DataSettings, code: str, client: httpx.AsyncClient) -> dict[str, Any]:
    form = {
        "grant_type": GRANT_AUTH_CODE,
        "client_id": settings.monzo_client_id,
        "client_secret": settings.monzo_client_secret,
        "redirect_uri": settings.monzo_redirect_uri,
        "code": code,
    }
    return _creds_from_token_response(await _post_token(settings, form, client))


async def refresh(settings: DataSettings, refresh_token: str, client: httpx.AsyncClient) -> dict[str, Any]:
    """One refresh. The returned creds carry the NEW refresh token (the old one is now invalid)."""
    form = {
        "grant_type": GRANT_REFRESH,
        "client_id": settings.monzo_client_id,
        "client_secret": settings.monzo_client_secret,
        "refresh_token": refresh_token,
    }
    return _creds_from_token_response(await _post_token(settings, form, client), previous_refresh=refresh_token)
