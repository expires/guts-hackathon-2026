"""Sources hub: "Where Penny's data comes from" (ADR 0073). BOSS-owned.

One card per student-facing source: what it gives Penny, which screens use it, its live or cached status and its
latest values with the official page. No homeowner sources.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from lifeline_contracts.domain import ShortId
from lifeline_contracts.observation import Status


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HubValue(_M):
    label: str = Field(max_length=80, description="e.g. 'Easy-access savings rate'")
    value: str = Field(max_length=40, description="Formatted, e.g. '2.06%' or '£1,723 a year'")
    as_of: str | None = Field(default=None, max_length=40, description="e.g. 'Sep 2026' or an ISO date")


class HubSource(_M):
    id: ShortId
    name: str = Field(max_length=80)
    kind: Literal["statement", "official_facts", "live"]
    status: Status
    updated_at: datetime | None = None
    gives: str = Field(max_length=160, description="One line: what it gives Penny")
    used_in: list[str] = Field(max_length=6, description="Screen names, e.g. 'One thing that helps'")
    latest: list[HubValue] = Field(default_factory=list, max_length=6)
    url: str | None = Field(default=None, max_length=500, description="The official page")


class SourcesHub(_M):
    summary: str = Field(max_length=200, description="'Penny uses your statement plus N live UK sources. ...'")
    live_count: int = Field(ge=0)
    sources: list[HubSource]
