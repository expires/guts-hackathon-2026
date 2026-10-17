"""Local store for imported Monzo transaction history.

This is raw personal financial data. It never leaves the device and lives only in the
gitignored credentials dir (data/private/), written with mode 0600. Merge = upsert by
transaction id (later data wins, since pending transactions change). Deleted on disconnect.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from playyourself.adapters._private_file import write_private_json

FILE_NAME = "monzo_history.json"

# Last full-sync failure per history file, in memory only (a short error code, never a secret).
_LAST_ERRORS: dict[str, str] = {}


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


class MonzoHistory:
    def __init__(self, directory: Path):
        self._path = directory / FILE_NAME

    @property
    def path(self) -> Path:
        return self._path

    def _read(self) -> dict[str, Any] | None:
        try:
            raw = json.loads(self._path.read_text())
        except (OSError, ValueError):
            return None
        if (
            isinstance(raw, dict)
            and isinstance(raw.get("meta"), dict)
            and isinstance(raw.get("transactions"), dict)
        ):
            return raw
        return None

    def meta(self) -> dict[str, Any] | None:
        raw = self._read()
        return dict(raw["meta"]) if raw else None

    def is_full(self) -> bool:
        m = self.meta()
        return bool(m and m.get("full_sync_at"))

    def transactions(self) -> list[dict[str, Any]]:
        raw = self._read()
        return list(raw["transactions"].values()) if raw else []

    def merge(self, account_id: str, txs: list[dict[str, Any]], *, full: bool) -> None:
        """Upsert by id. A different account starts a fresh store."""
        raw = self._read()
        if raw and raw["meta"].get("account_id") == account_id:
            by_id: dict[str, Any] = raw["transactions"]
            full_sync_at = raw["meta"].get("full_sync_at")
        else:
            by_id, full_sync_at = {}, None
        for t in txs:
            by_id[t["id"]] = t
        if full:
            full_sync_at = datetime.now().astimezone().isoformat(timespec="seconds")
        oldest = min((t["ts"] for t in by_id.values()), key=_parse, default=None)
        meta = {
            "account_id": account_id,
            "full_sync_at": full_sync_at,
            "oldest_ts": oldest,
            "count": len(by_id),
        }
        write_private_json(self._path, {"meta": meta, "transactions": by_id})

    # ---- failure record (in memory) ------------------------------------------------------
    def set_error(self, message: str | None) -> None:
        if message:
            _LAST_ERRORS[str(self._path)] = message
        else:
            _LAST_ERRORS.pop(str(self._path), None)

    def last_error(self) -> str | None:
        return _LAST_ERRORS.get(str(self._path))

    def delete(self) -> None:
        self._path.unlink(missing_ok=True)
        self._path.with_suffix(".tmp").unlink(missing_ok=True)
        _LAST_ERRORS.pop(str(self._path), None)

    def status(self) -> dict[str, Any]:
        """Safe to return from the API: no amounts, merchants or ids."""
        m = self.meta() or {}
        oldest = None
        if m.get("oldest_ts"):
            oldest = _parse(m["oldest_ts"]).date().isoformat()
        return {
            "synced": bool(m.get("full_sync_at")),
            "oldest": oldest,
            "count": int(m.get("count") or 0),
            "last_error": self.last_error(),
        }
