"""Canonical data schema (spec section 1, Data integration).

Every adapter maps its source to a list of `Observation`.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Status = Literal["live", "cached", "mock", "unavailable"]


class Observation(BaseModel):
    """One value of one series at one date."""

    model_config = ConfigDict(frozen=True)

    series_id: str = Field(description="Source-native series id, e.g. IUMBEDR or d7g7.")
    source: str = Field(description="Source id, e.g. boe, ons, nomis, landregistry, postcodes.")
    date: date
    value: float
    unit: str = Field(description="e.g. percent, gbp, index, count.")
    region: str | None = Field(default=None, description="Canonical region slug or None for UK.")
    fetched_at: datetime
    status: Status


class SourceStatus(BaseModel):
    """Health of one source, as exposed by GET /v1/sources."""

    id: str
    name: str
    status: Status
    fetched_at: datetime | None = None
    ttl_seconds: int
    coverage: str = Field(description="e.g. 'UK', 'England and Wales', 'England'.")
    attribution: str
    licence: str
    needs_key: bool = False
    last_error: str | None = None


# Canonical region slugs. Every adapter maps its native region codes to these.
REGIONS: tuple[str, ...] = (
    "north-east",
    "north-west",
    "yorkshire-and-the-humber",
    "east-midlands",
    "west-midlands",
    "east-of-england",
    "london",
    "south-east",
    "south-west",
    "wales",
    "scotland",
    "northern-ireland",
)
