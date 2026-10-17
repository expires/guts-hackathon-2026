"""Monzo adapter (read-only: balances, pots, transactions).

Endpoints, auth and request parameters are verified against docs.monzo.com (Oct 2026). Items
that the docs do not confirm are marked VERIFY. No rate limits are assumed.

History: after the first 5 minutes following authentication Monzo only shares the last 90 days
of transactions, so `full_sync()` imports everything right after connecting and stores it locally
(see monzo_history.py). Later syncs only fetch the recent window and merge it into that store.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta
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
from playyourself.adapters.monzo_history import MonzoHistory
from playyourself.domain.models import Balance, Holding, Transaction
from playyourself.settings import Settings

# Verified against docs.monzo.com (Oct 2026): paths below, Bearer auth, and the query params
# account_id, since (RFC 3339 timestamp or transaction id), limit, current_account_id.
ACCOUNTS_PATH = "/accounts"
BALANCE_PATH = "/balance"
POTS_PATH = "/pots"
TRANSACTIONS_PATH = "/transactions"
WHOAMI_PATH = "/ping/whoami"
ACCOUNT_TYPE = "uk_retail"  # account_type=uk_retail filter verified; the `type` field is VERIFY
# VERIFY: transfer detection via scheme "uk_retail_pot", account `closed`/`type` and pot
# `deleted` fields, and transaction field names beyond id/amount/created are not confirmed.
TRANSFER_SCHEMES = frozenset({"uk_retail_pot"})
# Docs: `limit` defaults to 30 and has a maximum of 100.
PAGE_LIMIT = 100
# Our own safety guard against a runaway pagination loop, not an API limit.
MAX_PAGES = 500
# Docs: after the first 5 minutes only the last 90 days are available. 89 leaves a day of margin.
RECENT_SYNC_DAYS = 89
TRANSFER_CATEGORIES = frozenset({"transfers", "savings"})


def _map_transaction(raw: Any) -> dict:
    """Monzo transaction JSON -> Transaction fields. Missing fields stay missing so validation
    drops the record."""
    if not isinstance(raw, dict):
        return {}
    merchant = raw.get("merchant")
    name = merchant.get("name") if isinstance(merchant, dict) else None
    category = raw.get("category")
    is_transfer = raw.get("scheme") in TRANSFER_SCHEMES or (
        not name and category in TRANSFER_CATEGORIES
    )
    out = {
        "id": raw.get("id"),
        "ts": raw.get("created"),
        "amount_pence": raw.get("amount"),
        "merchant": name or raw.get("description"),
        "category": category,
        "is_transfer": bool(is_transfer),
    }
    return {k: v for k, v in out.items() if v is not None}


def _map_balance(raw: Any, account_id: str) -> dict:
    return {
        "account_id": account_id,
        "kind": "current",
        "value_pence": raw.get("balance") if isinstance(raw, dict) else None,
    }


def _map_pot(raw: Any) -> dict:
    if not isinstance(raw, dict):
        return {}
    return {"account_id": raw.get("id"), "kind": "pot", "value_pence": raw.get("balance")}


def _list_of(payload: Any, key: str, source: str) -> list:
    items = payload.get(key) if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise SourceError("bad_data", f"{source} response missing '{key}' list")
    return items


class MonzoAdapter:
    name = "monzo"
    mode = "live"
    cache_key = "monzo-live"
    capabilities = frozenset({Capability.BALANCES, Capability.TRANSACTIONS})

    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient | None = None,
        token: str | None = None,
        refresher: Callable[[], Awaitable[str | None]] | None = None,
        history: MonzoHistory | None = None,
    ):
        self._settings = settings
        self._client = client
        self._token = token if token is not None else settings.monzo_access_token
        self._refresher = refresher  # returns a new access token, or None
        self._history = history  # None = no local persistence
        self.last_dropped = 0

    async def _send(self, path: str, params: dict[str, Any]) -> Any:
        if not self._token:
            raise SourceError(
                "auth", "no access token set (MONZO_ACCESS_TOKEN or connect in the UI)"
            )
        headers = {"Authorization": f"Bearer {self._token}"}
        url = self._settings.monzo_base_url.rstrip("/") + path
        if self._client is not None:
            return await request_json(
                self._client, "GET", url, source=self.name, headers=headers, params=params
            )
        async with httpx.AsyncClient(timeout=self._settings.source_timeout_seconds) as c:
            return await request_json(
                c, "GET", url, source=self.name, headers=headers, params=params
            )

    async def _get(self, path: str, **params: Any) -> Any:
        try:
            return await self._send(path, params)
        except SourceError as exc:
            if exc.code != "auth" or self._refresher is None:
                raise
        new_token = await self._refresher()  # one refresh, then one retry
        if not new_token:
            raise SourceError("auth", "monzo token rejected and could not be refreshed")
        self._token = new_token
        return await self._send(path, params)

    async def _account_id(self) -> str:
        accounts = _list_of(await self._get(ACCOUNTS_PATH), "accounts", self.name)
        for acc in accounts:
            if (
                isinstance(acc, dict)
                and acc.get("type") == ACCOUNT_TYPE
                and not acc.get("closed", False)
                and acc.get("id")
            ):
                return str(acc["id"])
        raise SourceError("bad_data", "no open uk_retail account found")

    async def get_balances(self) -> list[Balance]:
        acc = await self._account_id()
        bal = await self._get(BALANCE_PATH, account_id=acc)
        pots = _list_of(await self._get(POTS_PATH, current_account_id=acc), "pots", self.name)
        raw = [_map_balance(bal, acc)] + [
            _map_pot(p) for p in pots if isinstance(p, dict) and not p.get("deleted", False)
        ]
        valid, self.last_dropped = parse_records(raw, Balance, self.name)
        return valid

    async def _fetch_transactions(self, acc: str, since: datetime | None) -> list[dict]:
        """Page through /transactions. First page uses the `since` timestamp (none = everything),
        later pages use since=<id of the last transaction>. Stops on a short page."""
        by_id: dict[str, dict] = {}
        anonymous: list[dict] = []
        cursor = since.strftime("%Y-%m-%dT%H:%M:%SZ") if since else None
        for _ in range(MAX_PAGES):
            params: dict[str, Any] = {"account_id": acc, "limit": PAGE_LIMIT}
            if cursor:
                params["since"] = cursor
            # VERIFY: expand[] is mentioned in the docs but absent from the argument table.
            params["expand[]"] = "merchant"
            items = _list_of(
                await self._get(TRANSACTIONS_PATH, **params), "transactions", self.name
            )
            for t in items:
                mapped = _map_transaction(t)
                if mapped.get("id"):
                    by_id[mapped["id"]] = mapped  # dedupe, later wins
                else:
                    anonymous.append(mapped)
            last = items[-1].get("id") if items and isinstance(items[-1], dict) else None
            if len(items) < PAGE_LIMIT or not isinstance(last, str) or last == cursor:
                break
            cursor = last
        return [*by_id.values(), *anonymous]

    def _store(self, acc: str, raw: list[dict], *, full: bool) -> int:
        valid, dropped = parse_records(raw, Transaction, self.name)
        if self._history is not None:
            self._history.merge(acc, [t.model_dump(mode="json") for t in valid], full=full)
        return dropped

    async def full_sync(self) -> bool:
        """Import ALL history and store it. Call right after authentication (5-minute window).
        Never raises: the failure is recorded for the status endpoint and False is returned."""
        if self._history is None:
            return False
        try:
            async with asyncio.timeout(self._settings.monzo_initial_sync_timeout_seconds):
                acc = await self._account_id()
                raw = await self._fetch_transactions(acc, None)
            self._store(acc, raw, full=True)
        except (SourceError, TimeoutError) as exc:
            self._history.set_error(exc.code if isinstance(exc, SourceError) else "timeout")
            return False
        self._history.set_error(None)
        return True

    async def get_transactions(self, since: date) -> list[Transaction]:
        acc = await self._account_id()
        since_dt = datetime(since.year, since.month, since.day, tzinfo=UTC)
        today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        floor = today - timedelta(days=RECENT_SYNC_DAYS)
        # With a stored full history only the recent window is needed. Without one, never ask
        # for older data: Monzo refuses it after the first 5 minutes.
        start = (
            floor if self._history is not None and self._history.is_full() else max(since_dt, floor)
        )
        raw = await self._fetch_transactions(acc, start)
        if self._history is None:
            valid, self.last_dropped = parse_records(raw, Transaction, self.name)
            return [t for t in valid if t.ts >= since_dt]
        self.last_dropped = self._store(acc, raw, full=False)
        stored, _ = parse_records(self._history.transactions(), Transaction, self.name)
        return [t for t in stored if t.ts >= since_dt]

    async def get_holdings(self) -> list[Holding]:
        raise UnsupportedCapability("monzo does not support holdings")

    async def health(self) -> SourceHealth:
        start = time.perf_counter()
        try:
            await self._get(WHOAMI_PATH)
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
