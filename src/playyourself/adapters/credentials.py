"""Per-source credential store. Secrets live in memory, optionally in a 0600 local file.

Secrets are never logged, never returned by `status()` (only a masked hint) and never put in
exception messages. With nothing stored, env-var settings are the fallback.
"""

import json
import logging
import threading
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from playyourself.adapters._private_file import write_private_json
from playyourself.adapters.monzo_history import MonzoHistory
from playyourself.settings import Settings

log = logging.getLogger(__name__)

SOURCES = ("monzo", "trading212")
FILE_NAME = "credentials.json"
_ALLOWED_KEYS = {
    "monzo": {"access_token", "refresh_token", "expires_at"},
    "trading212": {"api_key", "api_secret"},
}
_PRIMARY = {"monzo": "access_token", "trading212": "api_key"}
_HINT_MIN_LEN = 12  # shorter secrets get no suffix at all


class CredentialStatus(BaseModel):
    connected: bool
    hint: str | None = None
    remembered: bool = False
    origin: Literal["stored", "env"] | None = None


def mask(secret: str) -> str:
    """Masked hint such as '…a1b2'. Very short secrets reveal nothing."""
    return "…" + secret[-4:] if len(secret) >= _HINT_MIN_LEN else "…"


class CredentialStore:
    def __init__(self, directory: Path | None = None, settings: Settings | None = None):
        self._dir = directory
        self._settings = settings
        self._creds: dict[str, dict[str, Any]] = {}
        self._remembered: set[str] = set()
        self._lock = threading.Lock()
        self._load()

    # ---- persistence ---------------------------------------------------------------------
    @property
    def _path(self) -> Path | None:
        return self._dir / FILE_NAME if self._dir is not None else None

    def _load(self) -> None:
        path = self._path
        if path is None:
            return
        try:
            raw = json.loads(path.read_text())
        except (OSError, ValueError):
            return
        if not isinstance(raw, dict):
            return
        for source, creds in raw.items():
            if source in SOURCES and isinstance(creds, dict):
                clean = {k: v for k, v in creds.items() if k in _ALLOWED_KEYS[source] and v}
                if clean.get(_PRIMARY[source]):
                    self._creds[source] = clean
                    self._remembered.add(source)

    def _persist(self) -> None:
        path = self._path
        if path is None:
            return
        payload = {s: self._creds[s] for s in SOURCES if s in self._remembered and s in self._creds}
        if not payload:
            path.unlink(missing_ok=True)
            return
        write_private_json(path, payload)

    # ---- API -----------------------------------------------------------------------------
    def set(self, source: str, creds: dict[str, Any], remember: bool = False) -> None:
        if source not in SOURCES:
            raise ValueError(f"unknown source {source!r}")
        clean = {k: v for k, v in creds.items() if k in _ALLOWED_KEYS[source] and v}
        if not clean.get(_PRIMARY[source]):
            raise ValueError("missing primary credential")
        with self._lock:
            self._creds[source] = clean
            was = source in self._remembered
            if remember:
                self._remembered.add(source)
            else:
                self._remembered.discard(source)
            if remember or was:
                self._persist()

    def update(self, source: str, creds: dict[str, Any]) -> None:
        """Replace stored creds (e.g. after a token refresh), keeping the remember choice."""
        self.set(source, creds, remember=source in self._remembered)

    def forget(self, source: str) -> None:
        if source == "monzo" and self._dir is not None:
            MonzoHistory(self._dir).delete()  # imported history is personal data: remove it too
        with self._lock:
            self._creds.pop(source, None)
            if source in self._remembered:
                self._remembered.discard(source)
                self._persist()

    def get(self, source: str) -> dict[str, Any] | None:
        """Stored credentials only (no env fallback)."""
        c = self._creds.get(source)
        return dict(c) if c else None

    def _from_env(self, source: str) -> dict[str, Any] | None:
        s = self._settings
        if s is None:
            return None
        if source == "monzo" and s.monzo_access_token:
            return {"access_token": s.monzo_access_token}
        if source == "trading212" and s.t212_api_key:
            return {"api_key": s.t212_api_key, "api_secret": s.t212_api_secret}
        return None

    def resolve(self, source: str) -> dict[str, Any] | None:
        """Stored credentials, else env fallback."""
        return self.get(source) or self._from_env(source)

    def has_credentials(self, source: str) -> bool:
        return self.resolve(source) is not None

    def status(self, source: str) -> CredentialStatus:
        stored = self.get(source)
        if stored:
            return CredentialStatus(
                connected=True,
                hint=mask(str(stored[_PRIMARY[source]])),
                remembered=source in self._remembered,
                origin="stored",
            )
        env = self._from_env(source)
        if env:
            return CredentialStatus(
                connected=True, hint=mask(str(env[_PRIMARY[source]])), origin="env"
            )
        return CredentialStatus(connected=False)
