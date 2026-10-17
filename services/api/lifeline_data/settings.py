"""Data layer settings from environment variables. Values are never logged."""

from __future__ import annotations

from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/129.0 Safari/537.36"
)


class DataSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", case_sensitive=False)

    app_env: str = "dev"
    redis_url: str = ""
    database_url: str = ""
    # Force offline mode in any env (no network). APP_ENV=test is always offline.
    data_offline: bool = False
    http_timeout_seconds: float = Field(default=8.0, gt=0)
    http_retries: int = Field(default=3, ge=1, le=10)
    backoff_base_seconds: float = Field(default=0.5, ge=0)
    breaker_threshold: int = Field(default=3, ge=1)
    breaker_reset_seconds: float = Field(default=60.0, ge=0)
    data_refresh_interval_seconds: float = Field(default=6 * 3600, gt=0)
    # How long DataHub reuses a built MacroTable before it rebuilds it (online mode only).
    macro_table_ttl_seconds: float = Field(default=3600, ge=0)

    @property
    def offline(self) -> bool:
        return self.data_offline or self.app_env == "test"

    @classmethod
    def from_any(cls, obj: Any | None) -> DataSettings:
        """Accept None, a DataSettings, or any settings object (for example W4's Settings).

        Fields missing on `obj` come from the environment.
        """
        if obj is None:
            return cls()
        if isinstance(obj, DataSettings):
            return obj
        overrides = {name: getattr(obj, name) for name in cls.model_fields if hasattr(obj, name)}
        return cls(**overrides)
