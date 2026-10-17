"""Encryption at rest for per-user data (ADR 0028, V6 T2-F5). Fernet (AES-128-CBC + HMAC-SHA256).

Key: env TOKEN_ENCRYPTION_KEY. A valid Fernet key (32 url-safe base64 bytes) is used as is; any other
non-empty value is stretched with SHA-256 into a Fernet key. The key is never logged.
- Live mode or APP_ENV=prod/production with no key: `Sealer.required()` refuses (EncryptionKeyMissing);
  nothing is stored in plaintext.
- Demo and test with no key: an ephemeral per-process key (data does not survive a restart).

Bank tokens (Yaffy's provider store, arriving with the merge) must use the same Sealer.
"""

from __future__ import annotations

import base64
import hashlib
from collections.abc import Mapping

from cryptography.fernet import Fernet, InvalidToken

KEY_ENV = "TOKEN_ENCRYPTION_KEY"


class StoreUnavailable(Exception):
    """The per-user store could not complete the operation. The API answers 503."""


class EncryptionKeyMissing(StoreUnavailable):
    """No TOKEN_ENCRYPTION_KEY where one is required. Nothing was stored."""


def _fernet_key(raw: str) -> bytes:
    candidate = raw.strip().encode()
    try:
        if len(base64.urlsafe_b64decode(candidate)) == 32:
            Fernet(candidate)
            return candidate
    except (ValueError, TypeError):
        pass
    return base64.urlsafe_b64encode(hashlib.sha256(candidate).digest())


class Sealer:
    def __init__(self, env: Mapping[str, str], *, strict: bool) -> None:
        raw = (env.get(KEY_ENV) or "").strip()
        self.has_key = bool(raw)
        self.strict = strict
        self.ephemeral = not raw and not strict
        if raw:
            self._fernet: Fernet | None = Fernet(_fernet_key(raw))
        elif self.ephemeral:
            self._fernet = Fernet(Fernet.generate_key())
        else:
            self._fernet = None

    def seal(self, plaintext: str) -> str:
        if self._fernet is None:
            raise EncryptionKeyMissing(f"{KEY_ENV} not set; refusing to store personal data unencrypted")
        return self._fernet.encrypt(plaintext.encode()).decode()

    def open(self, token: str) -> str:
        """Decrypt. Raises InvalidToken for a wrong key or tampered data, EncryptionKeyMissing without a key."""
        if self._fernet is None:
            raise EncryptionKeyMissing(f"{KEY_ENV} not set")
        return self._fernet.decrypt(token.encode()).decode()


__all__ = ["KEY_ENV", "EncryptionKeyMissing", "InvalidToken", "Sealer", "StoreUnavailable"]
