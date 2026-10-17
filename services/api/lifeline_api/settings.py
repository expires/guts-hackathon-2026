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


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", case_sensitive=False)

    app_env: Literal["dev", "test", "prod"] = "dev"
    version: str = "0.1.0"
    database_url: str = ""
    redis_url: str = ""
    public_base_url: str = "http://localhost:8000"
    rate_limit_per_minute: int = Field(default=120, ge=1, le=100_000)
    jwt_secret: SecretStr = SecretStr("")
    jwt_ttl_seconds: int = Field(default=30 * 24 * 3600, ge=60)
    apple_bundle_id: str = "com.lifeline.app"

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"

    def signing_secret(self) -> str:
        """JWT_SECRET. Test mode uses a fixed test secret. Dev uses a per-process random secret. Prod fails."""
        secret = self.jwt_secret.get_secret_value()
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
