"""Trading212 adapter (read-only: positions and ISA cash).

Verified against docs.trading212.com (Oct 2026): the API works only for Invest and Stocks ISA
accounts; base URLs are https://live.trading212.com/api/v0 and https://demo.trading212.com/api/v0.
Auth is HTTP Basic, `Authorization: Basic base64(API_KEY:API_SECRET)`; both halves are required.

Currency: the domain is GBP-only for now. Position values come from walletImpact.currentValue
(ACCOUNT currency), never currentPrice * quantity (INSTRUMENT currency, wrong for non-GBP
instruments). Records whose wallet/account currency is not GBP are dropped with a warning.
"""

import hashlib
import logging
import time
from base64 import b64encode
from collections.abc import Callable
from datetime import date
from typing import Any

import httpx

from playyourself.adapters._http import request_json
from playyourself.adapters.base import (
    Capability,
    SourceError,
    SourceHealth,
    UnsupportedCapability,
    parse_records,
)
from playyourself.domain.models import Balance, Holding, Transaction
from playyourself.settings import Settings

log = logging.getLogger(__name__)

# Verified against docs.trading212.com (Oct 2026)
POSITIONS_PATH = "/equity/positions"
SUMMARY_PATH = "/equity/account/summary"
# Verified against docs.trading212.com (Oct 2026): 1 request / 1 s (positions), 1 / 5 s (summary).
MIN_INTERVAL_SECONDS: dict[str, float] = {POSITIONS_PATH: 1.0, SUMMARY_PATH: 5.0}
# Epoch-looking x-ratelimit-reset values are above this (seconds since 1970 ~ 1.7e9).
_EPOCH_THRESHOLD = 1_000_000_000

# Deliberately simple static mapping keyed on the ticker root (text before the first "_") or ISIN.
# Anything unknown defaults to "equity" with region None.
_ASSET_CLASS: dict[str, str] = {"VAGS": "bond", "VGOV": "bond", "IGLT": "bond", "SGLN": "commodity"}
_REGION: dict[str, str] = {"VUSA": "US", "VWRL": "Global", "VWRP": "Global", "ISF": "UK"}
_REGION_BY_ISIN_PREFIX: dict[str, str] = {"US": "US", "GB": "UK"}

# Module-level response cache: (base_url, sha256(key:secret), path) -> (monotonic time, payload).
# The credential is only ever stored hashed.
_CACHE: dict[tuple[str, str, str], tuple[float, Any]] = {}


def _reset_cache() -> None:
    _CACHE.clear()


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _pence(value: Any) -> int | None:
    n = _num(value)
    return None if n is None else round(n * 100)


def _map_holding(raw: Any) -> dict:
    if not isinstance(raw, dict):
        return {}
    inst = raw.get("instrument")
    inst = inst if isinstance(inst, dict) else {}
    wallet = raw.get("walletImpact")
    wallet = wallet if isinstance(wallet, dict) else {}
    ticker, isin = inst.get("ticker"), inst.get("isin")
    ident = isin or ticker
    value = _pence(wallet.get("currentValue"))
    if wallet.get("currency") != "GBP":
        log.warning("trading212: dropped position %s: wallet currency is not GBP", ident)
        value = None
    root = ticker.split("_")[0] if isinstance(ticker, str) else ""
    region = _REGION.get(root)
    if region is None and isinstance(isin, str):
        region = _REGION_BY_ISIN_PREFIX.get(isin[:2])
    return {
        "instrument_id": ident,
        "name": inst.get("name"),
        "quantity": raw.get("quantity"),
        "value_pence": value,
        "asset_class": _ASSET_CLASS.get(root, "equity"),
        "region": region,
    }


def _map_summary_cash(raw: Any) -> dict:
    """Free cash = availableToTrade + inPies. reservedForOrders is NOT free cash (excluded)."""
    if not isinstance(raw, dict):
        return {}
    cash = raw.get("cash")
    cash = cash if isinstance(cash, dict) else {}
    avail, pies = _num(cash.get("availableToTrade")), _num(cash.get("inPies"))
    value = None if avail is None or pies is None else round((avail + pies) * 100)
    if raw.get("currency") != "GBP":
        log.warning("trading212: dropped cash balance: account currency is not GBP")
        value = None
    acct = raw.get("id")
    return {
        "account_id": str(acct) if acct is not None else None,
        "kind": "isa_cash",
        "value_pence": value,
    }


class _HeaderCapture:
    """Thin client shim so we can read rate-limit headers on a 429 (request_json hides them)."""

    def __init__(self, client: httpx.AsyncClient):
        self._client = client
        self.headers: httpx.Headers | None = None

    async def request(self, method: str, url: str, **kw: Any) -> httpx.Response:
        resp = await self._client.request(method, url, **kw)
        self.headers = resp.headers
        return resp


def _retry_after_from_reset(headers: httpx.Headers | None, now: float) -> float | None:
    # VERIFY: x-ratelimit-reset may be a seconds delta or an epoch timestamp; handle both.
    raw = headers.get("x-ratelimit-reset") if headers is not None else None
    try:
        value = float(raw) if raw is not None else None
    except ValueError:
        return None
    if value is None or value < 0:
        return None
    return max(0.0, value - now) if value >= _EPOCH_THRESHOLD else value


class Trading212Adapter:
    name = "trading212"
    mode = "live"
    cache_key = "trading212-live"
    capabilities = frozenset({Capability.HOLDINGS, Capability.BALANCES})

    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient | None = None,
        api_key: str | None = None,
        api_secret: str | None = None,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
    ):
        self._settings = settings
        self._client = client
        self._key = api_key if api_key is not None else settings.t212_api_key
        self._secret = api_secret if api_secret is not None else settings.t212_api_secret
        self._clock = clock
        self._wall_clock = wall_clock
        self._local: dict[str, tuple[float, Any]] = {}
        self.last_dropped = 0

    def _auth_value(self) -> str:
        raw = f"{self._key}:{self._secret}".encode()
        return "Basic " + b64encode(raw).decode()

    def _cache_id(self, path: str) -> tuple[str, str, str]:
        digest = hashlib.sha256(f"{self._key}:{self._secret}".encode()).hexdigest()
        return (self._settings.t212_base_url.rstrip("/"), digest, path)

    def _cached(self, path: str) -> Any | None:
        ttl = MIN_INTERVAL_SECONDS[path]
        now = self._clock()
        for entry in (self._local.get(path), _CACHE.get(self._cache_id(path))):
            if entry is not None and 0 <= now - entry[0] < ttl:
                return entry[1]
        return None

    async def _get(self, path: str) -> Any:
        if not self._key or not self._secret:
            raise SourceError("auth", "Trading212 needs both an API key and an API secret")
        hit = self._cached(path)
        if hit is not None:
            return hit
        headers = {"Authorization": self._auth_value()}
        url = self._settings.t212_base_url.rstrip("/") + path
        try:
            if self._client is not None:
                cap = _HeaderCapture(self._client)
                payload = await request_json(cap, "GET", url, source=self.name, headers=headers)  # type: ignore[arg-type]
            else:
                async with httpx.AsyncClient(timeout=self._settings.source_timeout_seconds) as c:
                    cap = _HeaderCapture(c)
                    payload = await request_json(
                        cap,  # type: ignore[arg-type]
                        "GET",
                        url,
                        source=self.name,
                        headers=headers,
                    )
        except SourceError as exc:
            if exc.code == "rate_limited" and exc.retry_after is None:
                exc.retry_after = _retry_after_from_reset(cap.headers, self._wall_clock())
            raise
        stamp = (self._clock(), payload)
        self._local[path] = stamp
        _CACHE[self._cache_id(path)] = stamp
        return payload

    async def get_holdings(self) -> list[Holding]:
        payload = await self._get(POSITIONS_PATH)
        # VERIFY: docs do not confirm a top-level array; accept a list or {"items": [...]}.
        if isinstance(payload, dict) and isinstance(payload.get("items"), list):
            payload = payload["items"]
        if not isinstance(payload, list):
            raise SourceError("bad_data", "trading212 positions is not a list")
        valid, self.last_dropped = parse_records(
            [_map_holding(p) for p in payload], Holding, self.name
        )
        return valid

    async def get_balances(self) -> list[Balance]:
        payload = await self._get(SUMMARY_PATH)
        if not isinstance(payload, dict):
            raise SourceError("bad_data", "trading212 account summary is not an object")
        valid, self.last_dropped = parse_records([_map_summary_cash(payload)], Balance, self.name)
        return valid

    async def get_transactions(self, since: date) -> list[Transaction]:
        raise UnsupportedCapability("trading212 does not support transactions")

    async def health(self) -> SourceHealth:
        start = time.perf_counter()
        try:
            await self._get(SUMMARY_PATH)
        except SourceError as exc:
            return SourceHealth(
                name=self.name,
                ok=False,
                detail=f"{exc.code}: {exc.message}",
                error_code=exc.code,
            )
        return SourceHealth(
            name=self.name, ok=True, latency_ms=(time.perf_counter() - start) * 1000
        )
