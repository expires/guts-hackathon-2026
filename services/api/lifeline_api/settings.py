"""Settings from environment variables. Values are never logged."""

from __future__ import annotations

import logging
import secrets
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger(__name__)

# Used only when APP_ENV=test and JWT_SECRET is not set. Never used in dev or prod.
_TEST_JWT_SECRET = "test-only-jwt-secret-not-for-production-use"  # noqa: S105


# Known placeholder values. Prod refuses them (case-insensitive).
PLACEHOLDER_SECRETS = frozenset({"change-me-dev-only", "changeme", "change-me", "secret", "dev", "test", "password"})
MIN_PROD_SECRET_LENGTH = 32


def weak_secret_reason(secret: str) -> str | None:
    """Why `secret` is not acceptable in prod, or None if it is. The reason never contains the value."""
    if not secret:
        return "it is not set"
    if secret.strip().lower() in PLACEHOLDER_SECRETS:
        return "it is a known placeholder value"
    if len(secret) < MIN_PROD_SECRET_LENGTH:
        return f"it is shorter than {MIN_PROD_SECRET_LENGTH} characters"
    return None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", case_sensitive=False)

    app_env: Literal["dev", "test", "prod"] = "dev"
    version: str = "0.1.0"
    database_url: str = ""
    redis_url: str = ""
    public_base_url: str = "http://localhost:8000"
    # Per signed-in user: writes (POST, PUT, DELETE) use RATE_LIMIT_PER_MINUTE, reads (GET) the larger
    # READ_RATE_LIMIT_PER_MINUTE (the app fans out several reads per screen). The per-IP limit is only an
    # abuse guard, so it is high.
    rate_limit_per_minute: int = Field(default=120, ge=1, le=100_000)
    read_rate_limit_per_minute: int = Field(default=300, ge=1, le=100_000)
    ip_rate_limit_per_minute: int = Field(default=1200, ge=1, le=1_000_000)
    # Ask Penny: per user, on top of the general limit (each message may call the LLM several times).
    chat_rate_limit_per_minute: int = Field(default=6, ge=1, le=1000)
    # Demo sign-in per IP, so rotating device ids cannot mint fresh per-user buckets.
    auth_rate_limit_per_minute: int = Field(default=20, ge=1, le=10_000)
    # Wrong room or circle codes per minute (V6 final F-1). Codes are short. Per ACCOUNT is the real limit;
    # per IP is only a flood guard, high enough for a whole venue on one Wi-Fi (V3 final).
    wrong_code_per_minute: int = Field(default=10, ge=1, le=10_000)
    wrong_code_ip_per_minute: int = Field(default=120, ge=1, le=100_000)
    # Proxies in front of the API whose X-Forwarded-For entry we trust. None: 1 in prod (Railway), else 0.
    trusted_proxy_hops: int | None = Field(default=None, ge=0, le=5)
    jwt_secret: SecretStr = SecretStr("")
    jwt_ttl_seconds: int = Field(default=30 * 24 * 3600, ge=60)
    apple_bundle_id: str = "com.lifeline.app"

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"

    def signing_secret(self) -> str:
        """JWT_SECRET. Test mode uses a fixed test secret. Dev uses a per-process random secret.

        Prod refuses to start when the secret is missing, a known placeholder, or shorter than 32 characters.
        """
        secret = self.jwt_secret.get_secret_value()
        if self.app_env == "prod":
            problem = weak_secret_reason(secret)
            if problem is not None:
                # Never include the value in the message.
                raise RuntimeError(f"JWT_SECRET is not safe for prod: {problem}")
            return secret
        if secret:
            return secret
        if self.is_test:
            return _TEST_JWT_SECRET
        if self.app_env == "dev":
            log.warning("JWT_SECRET is not set; using a random per-process secret (tokens reset on restart)")
            generated = secrets.token_urlsafe(48)
            self.jwt_secret = SecretStr(generated)
            return generated
        raise RuntimeError("JWT_SECRET is not set")
