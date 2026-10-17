"""Environment-driven settings. No secrets in code."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    monzo_mode: Literal["mock", "live"] = "mock"
    t212_mode: Literal["mock", "live"] = "mock"
    monzo_access_token: str = ""
    monzo_base_url: str = "https://api.monzo.com"
    # Verified against docs.trading212.com (Oct 2026): key AND secret both required (Basic auth);
    # live https://live.trading212.com/api/v0, demo https://demo.trading212.com/api/v0.
    t212_api_key: str = ""
    t212_base_url: str = "https://live.trading212.com/api/v0"
    t212_api_secret: str = ""
    # Monzo OAuth 2.0 (authorization code flow). Client id/secret come from the Monzo developer
    # portal; the redirect URI must be registered there. Never log or return the secret.
    monzo_client_id: str = ""
    monzo_client_secret: str = ""
    monzo_redirect_uri: str = "http://localhost:8000/v1/connect/monzo/callback"
    # Verified against docs.monzo.com (Oct 2026)
    monzo_auth_url: str = "https://auth.monzo.com/"
    monzo_token_url: str = "https://api.monzo.com/oauth2/token"
    # Time budget for the full history import right after connecting. Monzo only shares the
    # last 90 days once 5 minutes have passed since authentication (docs.monzo.com).
    monzo_initial_sync_timeout_seconds: float = 60.0
    source_timeout_seconds: float = 5.0
    source_max_retries: int = 2
    isa_allowance_pence: int = 2_000_000
    mock_persona: str = "steady_saver"
    anthropic_api_key: str = ""
    explainer_model: str = "claude-sonnet-5-5"
    cache_dir: Path = Path("data/cache")
    credentials_dir: Path = Path("data/private")


@lru_cache
def get_settings() -> Settings:
    return Settings()
