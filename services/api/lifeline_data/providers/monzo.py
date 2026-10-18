"""Monzo adapter (read-only: accounts, balance, pots, transactions) mapped to main's contracts.

Endpoints, auth and request parameters are verified against docs.monzo.com (Oct 2026). Items the
docs do not confirm are marked VERIFY. No rate limits are assumed.

History: Monzo shares full history only in the first 5 minutes after authentication, then only the
last 90 days. `full_sync()` imports everything right after connecting and stores it per subject
(see store.py). Later syncs fetch the 89-day recent window and merge it in.

Mapping to lifeline_contracts.finance:
- uk_retail account -> Account(kind="current", balance=/balance.balance, which excludes pots).
- each non-deleted pot -> Account(kind="savings", id=pot id). Pots are not in the current balance, so
  there is no double count.
- uk_rewards (and any other type) is skipped: no sensible AccountKind, and it holds no spendable
  balance for the Money tab.
- transaction: amount = minor units / 100 (negative = out), date = UTC date of `created`,
  merchant = expanded merchant name, provider_category = Monzo's own category (the engine's
  categorise() maps it). Pot moves (scheme "uk_retail_pot", VERIFY) get a description the categoriser
  recognises: "Transfer to savings pot" (-> savings) / "Transfer from savings pot" (-> transfers),
  so they never count as spending. Declined transactions (decline_reason set) are dropped.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from pydantic import ValidationError

from lifeline_contracts.finance import Account, Transaction
from lifeline_data.providers._http import ProviderError, request_json
from lifeline_data.providers.store import ProviderStore

log = logging.getLogger(__name__)

ACCOUNTS_PATH = "/accounts"
BALANCE_PATH = "/balance"
POTS_PATH = "/pots"
TRANSACTIONS_PATH = "/transactions"
WHOAMI_PATH = "/ping/whoami"
ACCOUNT_TYPE = "uk_retail"  # account_type filter verified; the `type` field on the account is VERIFY
# VERIFY: pot-move detection via scheme "uk_retail_pot", and account `closed` / pot `deleted` flags.
POT_SCHEMES = frozenset({"uk_retail_pot"})
# Docs: `limit` defaults to 30 with a maximum of 100.
PAGE_LIMIT = 100
# Our own guard against a runaway pagination loop, not an API limit.
MAX_PAGES = 500
# Docs: after the first 5 minutes only the last 90 days are available. 89 leaves a day of margin.
RECENT_SYNC_DAYS = 89

Refresher = Callable[[], Awaitable[str | None]]


def map_transaction(raw: Any, account_id: str) -> Transaction | None:
    """Monzo transaction JSON -> Transaction, or None when it is malformed or declined."""
    if not isinstance(raw, dict) or raw.get("decline_reason"):
        return None
    amount, created = raw.get("amount"), raw.get("created")
    if not raw.get("id") or isinstance(amount, bool) or not isinstance(amount, int) or not isinstance(created, str):
        return None
    merchant = raw.get("merchant")
    name = merchant.get("name") if isinstance(merchant, dict) else None  # VERIFY: expand[]=merchant
    description = str(raw.get("description") or name or "Monzo transaction")
    if raw.get("scheme") in POT_SCHEMES:
        description = "Transfer to savings pot" if amount < 0 else "Transfer from savings pot"
        name = None
    category = raw.get("category")
    try:
        return Transaction(
            id=str(raw["id"]),
            account_id=account_id,
            date=created[:10],
            amount=amount / 100,
            description=description[:200],
            merchant=name[:80] if isinstance(name, str) and name else None,
            provider_category=category[:60] if isinstance(category, str) and category else None,
        )
    except ValidationError:
        return None


def _list_of(payload: Any, key: str) -> list[Any]:
    items = payload.get(key) if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise ProviderError("bad_data", f"monzo response missing '{key}' list", source="monzo")
    return items


class MonzoAdapter:
    source = "monzo"

    def __init__(
        self,
        base_url: str,
        client: httpx.AsyncClient,
        access_token: str,
        *,
        refresher: Refresher | None = None,
        store: ProviderStore | None = None,
        subject: str | None = None,
        initial_sync_timeout: float = 60.0,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._base = base_url.rstrip("/")
        self._client = client
        self._token = access_token
        self._refresher = refresher
        self._store = store
        self._subject = subject
        self._timeout = initial_sync_timeout
        self._clock = clock
        self.last_dropped = 0

    async def _send(self, path: str, params: dict[str, Any] | None) -> Any:
        return await request_json(
            self._client,
            "GET",
            self._base + path,
            source=self.source,
            headers={"Authorization": f"Bearer {self._token}"},
            params=params,
        )

    async def _get(self, path: str, **params: Any) -> Any:
        try:
            return await self._send(path, params or None)
        except ProviderError as exc:
            if exc.code != "auth" or self._refresher is None:
                raise
        new_token = await self._refresher()  # one refresh, then one retry
        if not new_token:
            raise ProviderError("auth", "monzo token rejected and could not be refreshed", source=self.source)
        self._token = new_token
        return await self._send(path, params or None)

    async def whoami(self) -> None:
        await self._get(WHOAMI_PATH)

    async def current_account_id(self) -> str:
        for acc in _list_of(await self._get(ACCOUNTS_PATH), "accounts"):
            if isinstance(acc, dict) and acc.get("type") == ACCOUNT_TYPE and not acc.get("closed") and acc.get("id"):
                return str(acc["id"])
        raise ProviderError("bad_data", "no open uk_retail account found", source=self.source)

    async def accounts(self, account_id: str | None = None) -> list[Account]:
        acc = account_id or await self.current_account_id()
        bal = await self._get(BALANCE_PATH, account_id=acc)
        pence = bal.get("balance") if isinstance(bal, dict) else None
        if isinstance(pence, bool) or not isinstance(pence, int):
            raise ProviderError("bad_data", "monzo balance missing", source=self.source)
        out = [Account(id=acc, name="Monzo", kind="current", provider="monzo", balance=pence / 100)]
        for pot in _list_of(await self._get(POTS_PATH, current_account_id=acc), "pots"):
            if not isinstance(pot, dict) or pot.get("deleted") or not pot.get("id"):
                continue
            value = pot.get("balance")
            if isinstance(value, bool) or not isinstance(value, int):
                continue
            out.append(
                Account(
                    id=str(pot["id"]),
                    name=str(pot.get("name") or "Pot")[:60],
                    kind="savings",
                    provider="monzo",
                    balance=value / 100,
                )
            )
        return out

    async def _fetch_transactions(self, acc: str, since: datetime | None) -> list[Transaction]:
        """Page /transactions. The first page uses the `since` timestamp (None = everything), later pages
        use since=<id of the last transaction>. Stops on a short page."""
        by_id: dict[str, Transaction] = {}
        dropped = 0
        cursor = since.strftime("%Y-%m-%dT%H:%M:%SZ") if since else None
        for _ in range(MAX_PAGES):
            params: dict[str, Any] = {"account_id": acc, "limit": PAGE_LIMIT, "expand[]": "merchant"}
            if cursor:
                params["since"] = cursor
            items = _list_of(await self._get(TRANSACTIONS_PATH, **params), "transactions")
            for raw in items:
                tx = map_transaction(raw, acc)
                if tx is None:
                    dropped += 1
                else:
                    by_id[tx.id] = tx
            last = items[-1].get("id") if items and isinstance(items[-1], dict) else None
            if len(items) < PAGE_LIMIT or not isinstance(last, str) or last == cursor:
                break
            cursor = last
        self.last_dropped = dropped
        return list(by_id.values())

    def _merge(self, acc: str, txs: list[Transaction], *, full: bool) -> None:
        if self._store is not None and self._subject is not None:
            self._store.merge_history(self._subject, acc, [t.model_dump(mode="json") for t in txs], full=full)

    async def full_sync(self) -> bool:
        """Import ALL history and store it. Call right after authentication (5-minute window).
        Never raises: the failure code is recorded for the connections status and False is returned."""
        if self._store is None or self._subject is None:
            return False
        try:
            async with asyncio.timeout(self._timeout):
                acc = await self.current_account_id()
                txs = await self._fetch_transactions(acc, None)
            self._merge(acc, txs, full=True)
        except ProviderError as exc:
            self._store.set_error(self._subject, "monzo", exc.code)
            return False
        except TimeoutError:
            self._store.set_error(self._subject, "monzo", "timeout")
            return False
        except Exception as exc:  # never raise from a sync
            log.warning("monzo full sync failed (%s)", type(exc).__name__)
            self._store.set_error(self._subject, "monzo", "bad_data")
            return False
        self._store.set_error(self._subject, "monzo", None)
        return True

    async def sync_recent(self, acc: str | None = None) -> list[Transaction]:
        """Fetch the 89-day recent window, merge it into the stored history and return all stored
        transactions (or just the window when there is no store). Raises ProviderError."""
        acc = acc or await self.current_account_id()
        today = self._clock().replace(hour=0, minute=0, second=0, microsecond=0)
        recent = await self._fetch_transactions(acc, today - timedelta(days=RECENT_SYNC_DAYS))
        if self._store is None or self._subject is None:
            return recent
        self._merge(acc, recent, full=False)
        stored = []
        for raw in self._store.history_transactions(self._subject):
            try:
                stored.append(Transaction.model_validate(raw))
            except ValidationError:
                continue
        return stored
