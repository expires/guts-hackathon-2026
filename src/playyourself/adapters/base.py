"""Adapter protocol, errors and record-validation helper."""

import logging
from collections.abc import Iterable
from datetime import date
from enum import StrEnum
from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, ValidationError

from playyourself.domain.models import Balance, Holding, Transaction

log = logging.getLogger(__name__)

M = TypeVar("M", bound=BaseModel)


class Capability(StrEnum):
    BALANCES = "balances"
    TRANSACTIONS = "transactions"
    HOLDINGS = "holdings"


class SourceError(Exception):
    """code: timeout | auth | rate_limited | bad_data | unavailable"""

    def __init__(
        self,
        code: str,
        message: str = "",
        retryable: bool = False,
        retry_after: float | None = None,
    ):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.retryable = retryable
        self.retry_after = retry_after


class UnsupportedCapability(SourceError):
    def __init__(self, message: str = "capability not supported"):
        super().__init__("unavailable", message, retryable=False)


class SourceHealth(BaseModel):
    name: str
    ok: bool
    latency_ms: float | None = None
    detail: str | None = None
    error_code: str | None = None  # SourceError code when ok is False


@runtime_checkable
class FinanceAdapter(Protocol):
    name: str
    capabilities: frozenset[Capability]
    last_dropped: int

    async def get_balances(self) -> list[Balance]: ...
    async def get_transactions(self, since: date) -> list[Transaction]: ...
    async def get_holdings(self) -> list[Holding]: ...
    async def health(self) -> SourceHealth: ...


def parse_records[M: BaseModel](
    raw: Iterable[dict], model: type[M], adapter_name: str
) -> tuple[list[M], int]:
    """Validate each record; drop invalid ones. Returns (valid, dropped_count)."""
    valid: list[M] = []
    dropped = 0
    for rec in raw:
        try:
            valid.append(model.model_validate(rec))
        except (ValidationError, TypeError, ValueError) as exc:
            dropped += 1
            log.warning("%s: dropped invalid %s record: %s", adapter_name, model.__name__, exc)
    return valid, dropped
