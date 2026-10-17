"""Connected personal accounts (Monzo, Trading212): holdings and connection status models.

No response model here carries a secret. Tokens and API keys stay server-side; clients only see a
masked hint such as "…a1b2".
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AssetClass = Literal["equity", "bond", "cash", "property", "commodity", "other"]
Provider = Literal["monzo", "trading212"]


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Holding(_M):
    """One investment position, valued in GBP (the account currency, never the instrument currency)."""

    instrument_id: str
    name: str
    quantity: float
    value: float = Field(ge=0, description="gbp")
    asset_class: AssetClass
    region: str | None = None


class HistoryStatus(_M):
    """State of the imported Monzo history. No amounts, merchants or ids."""

    synced: bool
    oldest: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    count: int = Field(ge=0)
    last_error: str | None = None


class ProviderConnection(_M):
    provider: Provider
    connected: bool
    data_status: Literal["live", "mock"]
    hint: str | None = Field(default=None, description="Masked credential suffix, for example '…a1b2'")
    oauth_available: bool = False
    history: HistoryStatus | None = None
    last_error: str | None = None


class ConnectionsResponse(_M):
    providers: list[ProviderConnection]


class Trading212ConnectRequest(_M):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    api_key: str = Field(min_length=1)
    api_secret: str = Field(min_length=1)


class MonzoTokenRequest(_M):
    """Dev convenience: paste a Monzo playground access token."""

    access_token: str = Field(min_length=1)
