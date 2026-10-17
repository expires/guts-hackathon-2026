"""Shared FastAPI dependencies. Override these in tests via app.dependency_overrides."""

from datetime import date, timedelta
from functools import lru_cache

import httpx
from fastapi import Depends

from playyourself.adapters.aggregator import build_adapters, fetch_snapshot
from playyourself.adapters.base import FinanceAdapter
from playyourself.adapters.credentials import CredentialStore
from playyourself.adapters.monzo_oauth import OAuthStateStore
from playyourself.decision.returns import ReturnSeries, load_returns
from playyourself.domain.models import Snapshot
from playyourself.settings import Settings, get_settings

HISTORY_DAYS = 13 * 31


@lru_cache
def get_returns() -> ReturnSeries:
    return load_returns()


@lru_cache
def _credential_store() -> CredentialStore:
    settings = get_settings()
    return CredentialStore(settings.credentials_dir, settings)


def get_credential_store() -> CredentialStore:
    """Process-wide singleton. Tests override this dependency."""
    return _credential_store()


@lru_cache
def _oauth_states() -> OAuthStateStore:
    return OAuthStateStore()


def get_oauth_states() -> OAuthStateStore:
    return _oauth_states()


def get_http_client() -> httpx.AsyncClient | None:
    """None means each adapter opens its own client. Tests override with a MockTransport."""
    return None


def get_adapters(
    settings: Settings = Depends(get_settings),
    store: CredentialStore = Depends(get_credential_store),
    client: httpx.AsyncClient | None = Depends(get_http_client),
) -> list[FinanceAdapter]:
    return build_adapters(settings, store, client)


async def get_snapshot(
    settings: Settings = Depends(get_settings),
    adapters: list[FinanceAdapter] = Depends(get_adapters),
) -> Snapshot:
    return await fetch_snapshot(
        adapters,
        date.today() - timedelta(days=HISTORY_DAYS),
        settings.source_timeout_seconds,
        settings.source_max_retries,
        settings.cache_dir,
    )
