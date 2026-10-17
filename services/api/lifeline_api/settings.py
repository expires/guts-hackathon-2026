"""Settings from environment variables. Values are never logged."""

from __future__ import annotations

import logging
import secrets
import sys
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger(__name__)

# `make dev` runs from services/api, so look for .env in the repo root first, then here (later files win).
# Real environment variables always beat both files. Pytest never reads .env files (tests stay hermetic).
_API_DIR = Path(__file__).resolve().parents[1]
ENV_FILES: tuple[Path, ...] | None = (
    None if "pytest" in sys.modules else (_API_DIR.parent.parent / ".env", _API_DIR / ".env")
)

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
    model_config = SettingsConfigDict(env_file=ENV_FILES, extra="ignore", case_sensitive=False)

    app_env: Literal["dev", "test", "prod"] = "dev"
    version: str = "0.1.0"
    database_url: str = ""
    redis_url: str = ""
    public_base_url: str = "http://localhost:8000"
    rate_limit_per_minute: int = Field(default=120, ge=1, le=100_000)
    jwt_secret: SecretStr = SecretStr("")
    jwt_ttl_seconds: int = Field(default=30 * 24 * 3600, ge=60)
    apple_bundle_id: str = "com.lifeline.app"
    credentials_dir: str = "data/private"  # same folder the data hub uses; holds social.json too

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
