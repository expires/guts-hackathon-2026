"""Sign in with Apple: verify the identity token against Apple's public keys (JWKS).

- Keys come from https://appleid.apple.com/auth/keys and are cached for 24 hours. An unknown key id
  triggers one refresh (at most once a minute).
- Checks: RS256 signature, issuer https://appleid.apple.com, audience APPLE_BUNDLE_ID, expiry.
- Test mode never calls the network: tests load a fixture JWKS with `set_keys`.
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

import httpx
import jwt

log = logging.getLogger(__name__)

APPLE_ISSUER = "https://appleid.apple.com"
APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"
KEYS_TTL_SECONDS = 24 * 3600
REFRESH_MIN_SECONDS = 60


class AppleTokenError(Exception):
    """The identity token is not valid. The message is safe to show."""


class AppleVerifier:
    def __init__(self, audience: str, *, offline: bool) -> None:
        self.audience = audience
        self.offline = offline
        self._keys: dict[str, Any] = {}
        self._fetched_at = 0.0

    def set_keys(self, jwks: dict[str, Any]) -> None:
        """Load a JWKS document (tests, or a pre-fetched copy)."""
        self._keys = {k["kid"]: jwt.PyJWK(k).key for k in jwks.get("keys", []) if "kid" in k}
        self._fetched_at = time.monotonic()

    async def _refresh(self) -> None:
        if self.offline or time.monotonic() - self._fetched_at < REFRESH_MIN_SECONDS:
            return
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(APPLE_JWKS_URL)
                r.raise_for_status()
                self.set_keys(r.json())
        except Exception as exc:
            log.warning("apple jwks fetch failed: %s", type(exc).__name__)
            self._fetched_at = time.monotonic()  # Back off; keep the old keys.

    async def _key(self, kid: str) -> Any:
        if kid not in self._keys or time.monotonic() - self._fetched_at > KEYS_TTL_SECONDS:
            await self._refresh()
        key = self._keys.get(kid)
        if key is None:
            raise AppleTokenError("Unknown signing key")
        return key

    async def verify(self, token: str) -> dict[str, Any]:
        """Return the verified claims. Raises AppleTokenError."""
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise AppleTokenError("Malformed identity token") from exc
        if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
            raise AppleTokenError("Unexpected token algorithm")
        key = await self._key(header["kid"])
        try:
            claims: dict[str, Any] = jwt.decode(
                token, key, algorithms=["RS256"], audience=self.audience, issuer=APPLE_ISSUER,
                options={"require": ["sub", "iss", "aud", "exp", "iat"]},
            )
        except jwt.PyJWTError as exc:
            raise AppleTokenError("Identity token rejected") from exc
        if not isinstance(claims.get("sub"), str) or not claims["sub"]:
            raise AppleTokenError("Identity token has no subject")
        return claims


def apple_subject(apple_sub: str) -> str:
    """Stable, opaque subject for an Apple user. The raw Apple id is not stored in our token."""
    return "apple_" + hashlib.sha256(f"apple:{apple_sub}".encode()).hexdigest()[:24]
