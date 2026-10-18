"""Per-subject server-side store for provider credentials, Monzo history and the last good snapshot.

Layout under the credentials dir (default data/private, gitignored):
  <sha256(subject)[:32]>/credentials.json, monzo_history.json, finance_snapshot.json
Every file is ENCRYPTED with the account system's Sealer (Fernet, TOKEN_ENCRYPTION_KEY, same as the user
snapshot store), then written atomically with mode 0600. With no key in live mode or prod, nothing is written
(EncryptionKeyMissing). A file that cannot be decrypted (wrong key) reads as absent. The subject (JWT `sub`)
is hashed so it can never escape the directory. Tokens never leave the server; `hint()` is the only derived value.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from lifeline_data.crypto import Sealer

PROVIDERS = ("monzo", "trading212")
_ALLOWED_KEYS = {
    "monzo": {"access_token", "refresh_token", "expires_at"},
    "trading212": {"api_key", "api_secret"},
}
_PRIMARY = {"monzo": "access_token", "trading212": "api_key"}
_HINT_MIN_LEN = 12  # shorter secrets reveal nothing


def mask(secret: str) -> str:
    """Masked hint such as '…a1b2'. Very short secrets reveal nothing."""
    return "…" + secret[-4:] if len(secret) >= _HINT_MIN_LEN else "…"


def subject_dirname(subject: str) -> str:
    return hashlib.sha256(subject.encode()).hexdigest()[:32]


def write_private_json(path: Path, payload: Any, sealer: Sealer) -> None:
    """Encrypt, then atomic write: temp file created 0600, then renamed over the target."""
    text = sealer.seal(json.dumps(payload))
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def _read_json(path: Path, sealer: Sealer) -> Any:
    try:
        return json.loads(sealer.open(path.read_text()))
    except Exception:  # missing file, wrong key, tampered data, no key
        return None


class ProviderStore:
    def __init__(self, directory: Path | str, sealer: Sealer | None = None) -> None:
        self._root = Path(directory)
        self._sealer = sealer or Sealer({}, strict=False)  # ephemeral key: tests only
        self._lock = threading.RLock()
        self._errors: dict[tuple[str, str], str] = {}  # (subject dir, provider) -> short error code

    def dir_for(self, subject: str) -> Path:
        return self._root / subject_dirname(subject)

    # ---- credentials -----------------------------------------------------------------------
    def _read_creds(self, subject: str) -> dict[str, Any]:
        raw = _read_json(self.dir_for(subject) / "credentials.json", self._sealer)
        return raw if isinstance(raw, dict) else {}

    def get(self, subject: str, provider: str) -> dict[str, Any] | None:
        creds = self._read_creds(subject).get(provider)
        if not isinstance(creds, dict) or not creds.get(_PRIMARY.get(provider, "")):
            return None
        return dict(creds)

    def set(self, subject: str, provider: str, creds: dict[str, Any]) -> None:
        if provider not in PROVIDERS:
            raise ValueError(f"unknown provider {provider!r}")
        clean = {k: v for k, v in creds.items() if k in _ALLOWED_KEYS[provider] and v}
        if not clean.get(_PRIMARY[provider]):
            raise ValueError("missing primary credential")
        with self._lock:
            doc = self._read_creds(subject)
            doc[provider] = clean
            write_private_json(self.dir_for(subject) / "credentials.json", doc, self._sealer)

    def forget(self, subject: str, provider: str) -> None:
        """Delete the credentials; for Monzo also the imported history. Drops the cached snapshot."""
        with self._lock:
            d = self.dir_for(subject)
            doc = self._read_creds(subject)
            doc.pop(provider, None)
            if doc:
                write_private_json(d / "credentials.json", doc, self._sealer)
            else:
                (d / "credentials.json").unlink(missing_ok=True)
            if provider == "monzo":
                (d / "monzo_history.json").unlink(missing_ok=True)
            (d / "finance_snapshot.json").unlink(missing_ok=True)
            self._errors.pop((d.name, provider), None)
            if d.is_dir() and not any(d.iterdir()):
                shutil.rmtree(d, ignore_errors=True)

    def hint(self, subject: str, provider: str) -> str | None:
        creds = self.get(subject, provider)
        return mask(str(creds[_PRIMARY[provider]])) if creds else None

    # ---- last error (memory only, short codes) ---------------------------------------------
    def set_error(self, subject: str, provider: str, code: str | None) -> None:
        key = (subject_dirname(subject), provider)
        if code:
            self._errors[key] = code
        else:
            self._errors.pop(key, None)

    def last_error(self, subject: str, provider: str) -> str | None:
        return self._errors.get((subject_dirname(subject), provider))

    # ---- Monzo history ---------------------------------------------------------------------
    def _read_history(self, subject: str) -> dict[str, Any] | None:
        raw = _read_json(self.dir_for(subject) / "monzo_history.json", self._sealer)
        if isinstance(raw, dict) and isinstance(raw.get("meta"), dict) and isinstance(raw.get("transactions"), dict):
            return raw
        return None

    def history_is_full(self, subject: str) -> bool:
        raw = self._read_history(subject)
        return bool(raw and raw["meta"].get("full_sync_at"))

    def history_account_id(self, subject: str) -> str | None:
        raw = self._read_history(subject)
        return str(raw["meta"].get("account_id")) if raw else None

    def history_transactions(self, subject: str) -> list[dict[str, Any]]:
        raw = self._read_history(subject)
        return list(raw["transactions"].values()) if raw else []

    def merge_history(self, subject: str, account_id: str, txs: list[dict[str, Any]], *, full: bool) -> None:
        """Upsert by id (later data wins; pending transactions change). A different account starts fresh."""
        with self._lock:
            raw = self._read_history(subject)
            if raw and raw["meta"].get("account_id") == account_id:
                by_id: dict[str, Any] = raw["transactions"]
                full_sync_at = raw["meta"].get("full_sync_at")
            else:
                by_id, full_sync_at = {}, None
            for t in txs:
                by_id[t["id"]] = t
            if full:
                full_sync_at = datetime.now().astimezone().isoformat(timespec="seconds")
            oldest = min((t["date"] for t in by_id.values()), default=None)
            meta = {"account_id": account_id, "full_sync_at": full_sync_at, "oldest": oldest, "count": len(by_id)}
            payload = {"meta": meta, "transactions": by_id}
            write_private_json(self.dir_for(subject) / "monzo_history.json", payload, self._sealer)

    def history_status(self, subject: str) -> dict[str, Any]:
        """Safe to return from the API: no amounts, merchants or ids."""
        raw = self._read_history(subject)
        meta = raw["meta"] if raw else {}
        return {
            "synced": bool(meta.get("full_sync_at")),
            "oldest": meta.get("oldest"),
            "count": int(meta.get("count") or 0),
            "last_error": self.last_error(subject, "monzo"),
        }

    # ---- last good live snapshot -----------------------------------------------------------
    def save_snapshot(self, subject: str, snapshot: dict[str, Any]) -> None:
        write_private_json(self.dir_for(subject) / "finance_snapshot.json", snapshot, self._sealer)

    def load_snapshot(self, subject: str) -> dict[str, Any] | None:
        raw = _read_json(self.dir_for(subject) / "finance_snapshot.json", self._sealer)
        return raw if isinstance(raw, dict) else None
