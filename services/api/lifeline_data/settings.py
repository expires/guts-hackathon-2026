"""Data layer settings from environment variables. Values are never logged."""

from __future__ import annotations

from typing import Any, Literal

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
    # ADR 0027. "demo": fixtures and labelled mock fallback (local dev, tests). "live": no mock data
    # anywhere; sources without real data report "unavailable". Railway sets DATA_MODE=live.
    data_mode: Literal["demo", "live"] = "demo"
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

    # Personal accounts (Monzo OAuth, Trading212). Secrets are excluded from repr.
    monzo_client_id: str = ""
    monzo_client_secret: str = Field(default="", repr=False)
    monzo_redirect_uri: str = "http://localhost:8000/v1/bank/callback"
    monzo_auth_url: str = "https://auth.monzo.com/"
    monzo_token_url: str = "https://api.monzo.com/oauth2/token"  # noqa: S105 - a URL, not a secret
    monzo_base_url: str = "https://api.monzo.com"
    monzo_initial_sync_timeout_seconds: float = Field(default=60.0, gt=0)
    # Env fallback for Trading212 (dev only; a stored per-user credential always wins).
    t212_api_key: str = Field(default="", repr=False)
    t212_api_secret: str = Field(default="", repr=False)
    t212_base_url: str = "https://live.trading212.com/api/v0"
    # Encrypted store of connected-account tokens and imported history (gitignored).
    credentials_dir: str = "data/private"

    @property
    def live_mode(self) -> bool:
        return self.data_mode == "live"

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
