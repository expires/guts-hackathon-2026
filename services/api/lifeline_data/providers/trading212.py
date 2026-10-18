"""Trading212 adapter (read-only: positions and account summary) mapped to main's contracts.

Verified against docs.trading212.com (Oct 2026): the API serves Invest and Stocks ISA accounts only;
base URLs are https://live.trading212.com/api/v0 and https://demo.trading212.com/api/v0. Auth is HTTP
Basic, `Authorization: Basic base64(API_KEY:API_SECRET)`; both halves are required. Documented rate
limits: GET /equity/positions 1 request / 1 s, GET /equity/account/summary 1 request / 5 s; a 429
carries x-ratelimit-* headers.

Currency: the domain is GBP-only. Position values come from walletImpact.currentValue (ACCOUNT
currency), never currentPrice * quantity (INSTRUMENT currency, wrong for non-GBP instruments).
Positions whose wallet currency is not GBP are dropped and counted in `last_dropped`.

Mapping: positions -> Holding. The summary -> ONE Account(kind="isa", provider="trading212") whose
balance is summary.totalValue (cash + investments), so net worth counts the whole wallet once; the
per-position values live in `holdings` and are NOT added to account balances. T212 does not say
whether the account is Invest or ISA, "isa" is the closest AccountKind.
"""

from __future__ import annotations

import hashlib
import logging
import time
from base64 import b64encode
from collections.abc import Callable
from typing import Any

import httpx
from pydantic import ValidationError

from lifeline_contracts.accounts import Holding
from lifeline_contracts.finance import Account
from lifeline_data.providers._http import ProviderError, request_json

log = logging.getLogger(__name__)

POSITIONS_PATH = "/equity/positions"
SUMMARY_PATH = "/equity/account/summary"
MIN_INTERVAL_SECONDS: dict[str, float] = {POSITIONS_PATH: 1.0, SUMMARY_PATH: 5.0}

# Deliberately simple static mapping keyed on the ticker root (text before the first "_") or ISIN.
# Anything unknown defaults to "equity" with region None.
_ASSET_CLASS: dict[str, str] = {"VAGS": "bond", "VGOV": "bond", "IGLT": "bond", "SGLN": "commodity"}
_REGION: dict[str, str] = {"VUSA": "US", "VWRL": "Global", "VWRP": "Global", "ISF": "UK"}
_REGION_BY_ISIN_PREFIX: dict[str, str] = {"US": "US", "GB": "UK"}

# (base_url, sha256(key:secret), path) -> (clock time, payload). The credential is only stored hashed.
_CACHE: dict[tuple[str, str, str], tuple[float, Any]] = {}


def reset_cache() -> None:
    _CACHE.clear()


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def map_holding(raw: Any) -> Holding | None:
    if not isinstance(raw, dict):
        return None
    inst = raw.get("instrument") if isinstance(raw.get("instrument"), dict) else {}
    wallet = raw.get("walletImpact") if isinstance(raw.get("walletImpact"), dict) else {}
    ticker, isin = inst.get("ticker"), inst.get("isin")
    ident = isin or ticker
    if wallet.get("currency") != "GBP":
        log.warning("trading212: dropped a position: wallet currency is not GBP")
        return None
    value, qty = _num(wallet.get("currentValue")), _num(raw.get("quantity"))
    if not ident or not inst.get("name") or value is None or qty is None:
        return None
    root = ticker.split("_")[0] if isinstance(ticker, str) else ""
    region = _REGION.get(root)
    if region is None and isinstance(isin, str):
        region = _REGION_BY_ISIN_PREFIX.get(isin[:2])
    try:
        return Holding(
            instrument_id=str(ident),
            name=str(inst["name"]),
            quantity=qty,
            value=value,
            asset_class=_ASSET_CLASS.get(root, "equity"),  # type: ignore[arg-type]
            region=region,
        )
    except ValidationError:
        return None


def map_summary(raw: Any) -> Account:
    if not isinstance(raw, dict):
        raise ProviderError("bad_data", "trading212 account summary is not an object", source="trading212")
    total = _num(raw.get("totalValue"))
    if raw.get("currency") != "GBP":
        raise ProviderError("bad_data", "trading212 account currency is not GBP", source="trading212")
    if total is None:
        raise ProviderError("bad_data", "trading212 account summary missing totalValue", source="trading212")
    acct = raw.get("id")
    return Account(
        id=f"t212-{acct}" if acct is not None else "t212",
        name="Trading 212 Stocks & Shares",  # "stocks" keeps it out of cash savings (is_cash_savings)
        kind="isa",
        provider="trading212",
        balance=total,
    )


class Trading212Adapter:
    source = "trading212"

    def __init__(
        self,
        base_url: str,
        client: httpx.AsyncClient,
        api_key: str,
        api_secret: str,
        *,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._client = client
        self._key = api_key
        self._secret = api_secret
        self._clock = clock
        self._wall_clock = wall_clock
        self.last_dropped = 0

    def _auth_value(self) -> str:
        return "Basic " + b64encode(f"{self._key}:{self._secret}".encode()).decode()

    def _cache_id(self, path: str) -> tuple[str, str, str]:
        return (self._base, hashlib.sha256(f"{self._key}:{self._secret}".encode()).hexdigest(), path)

    async def _get(self, path: str) -> Any:
        if not self._key or not self._secret:
            raise ProviderError("auth", "Trading212 needs both an API key and an API secret", source=self.source)
        now = self._clock()
        hit = _CACHE.get(self._cache_id(path))
        if hit is not None and 0 <= now - hit[0] < MIN_INTERVAL_SECONDS[path]:
            return hit[1]
        payload = await request_json(
            self._client,
            "GET",
            self._base + path,
            source=self.source,
            headers={"Authorization": self._auth_value()},
            wall_clock=self._wall_clock,
        )
        _CACHE[self._cache_id(path)] = (self._clock(), payload)
        return payload

    async def holdings(self) -> list[Holding]:
        payload = await self._get(POSITIONS_PATH)
        # VERIFY: the docs do not confirm a top-level array; accept a list or {"items": [...]}.
        if isinstance(payload, dict) and isinstance(payload.get("items"), list):
            payload = payload["items"]
        if not isinstance(payload, list):
            raise ProviderError("bad_data", "trading212 positions is not a list", source=self.source)
        mapped = [map_holding(p) for p in payload]
        self.last_dropped = sum(1 for h in mapped if h is None)
        return [h for h in mapped if h is not None]

    async def account(self) -> Account:
        return map_summary(await self._get(SUMMARY_PATH))

    async def health(self) -> bool:
        """True when the summary call succeeds. Raises ProviderError otherwise."""
        await self._get(SUMMARY_PATH)
        return True
