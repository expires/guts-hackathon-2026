"""Connected-account service: Monzo + Trading212 credentials, sync and live FinanceSnapshot.

Used by DataHub (`finance_snapshot`) and, later, the API routes. Everything is per SUBJECT (the JWT
`sub`): subject A's credentials are never used for subject B. Tokens never leave the server.

Live snapshot rules (see ADR 0010 for the fallback order):
- no provider connected -> None (the hub serves the labelled fixture persona);
- connected: live data for the connected parts only, the rest is EMPTY (sample data is never mixed
  into live data). Monzo gives accounts + transactions, Trading212 gives an ISA account + holdings;
- any connected provider failing -> the last good live snapshot saved on disk, status "cached";
  none saved -> None (fixture, status "mock").
- Trading212 env fallback (T212_API_KEY/T212_API_SECRET) applies only when APP_ENV is "dev".
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from pydantic import ValidationError

from lifeline_contracts.accounts import (
    ConnectionsResponse,
    HistoryStatus,
    Holding,
    Provider,
    ProviderConnection,
)
from lifeline_contracts.finance import Account, FinanceSnapshot, Transaction
from lifeline_data.providers import monzo_oauth
from lifeline_data.providers._http import ProviderError
from lifeline_data.providers.monzo import MonzoAdapter
from lifeline_data.providers.store import PROVIDERS, ProviderStore, mask
from lifeline_data.providers.trading212 import Trading212Adapter
from lifeline_data.settings import DataSettings

log = logging.getLogger(__name__)

SNAPSHOT_MEMO_SECONDS = 60.0  # protects the providers' rate limits when the app polls
LIVE_FETCH_TIMEOUT_SECONDS = 25.0
LIVE_ERROR_KEY = {"monzo": "monzo:live", "trading212": "trading212"}


class ProviderService:
    def __init__(
        self,
        settings: DataSettings,
        http: Callable[[], httpx.AsyncClient],
        *,
        live_enabled: Callable[[], bool] = lambda: True,
        clock: Callable[[], float] = time.time,
        store: ProviderStore | None = None,
        oauth_states: monzo_oauth.OAuthStateStore | None = None,
    ) -> None:
        self.settings = settings
        self._http = http
        self._live_enabled = live_enabled
        self._clock = clock
        self.store = store or ProviderStore(Path(settings.credentials_dir))
        self.oauth_states = oauth_states or monzo_oauth.OAuthStateStore(
            clock=clock, path=Path(settings.credentials_dir) / "oauth_states.json"
        )
        self._memo: dict[str, tuple[float, FinanceSnapshot]] = {}

    # ---- credentials -----------------------------------------------------------------------
    def _t212_creds(self, subject: str) -> dict[str, Any] | None:
        stored = self.store.get(subject, "trading212")
        if stored:
            return stored
        if self.settings.app_env == "dev" and self.settings.t212_api_key and self.settings.t212_api_secret:
            return {"api_key": self.settings.t212_api_key, "api_secret": self.settings.t212_api_secret}
        return None

    def _creds(self, subject: str, provider: str) -> dict[str, Any] | None:
        return self._t212_creds(subject) if provider == "trading212" else self.store.get(subject, provider)

    def _now(self) -> datetime:
        return datetime.fromtimestamp(self._clock(), UTC)

    def _require_live(self) -> httpx.AsyncClient:
        if not self._live_enabled():
            raise ProviderError("offline", "live provider calls are disabled in offline mode")
        return self._http()

    # ---- connections -----------------------------------------------------------------------
    def connection(self, subject: str, provider: Provider) -> ProviderConnection:
        creds = self._creds(subject, provider)
        primary = "api_key" if provider == "trading212" else "access_token"
        history = None
        if provider == "monzo":
            history = HistoryStatus(**self.store.history_status(subject)) if creds else None
        return ProviderConnection(
            provider=provider,
            connected=creds is not None,
            data_status="live" if creds is not None else "mock",
            hint=mask(str(creds[primary])) if creds else None,
            oauth_available=provider == "monzo" and monzo_oauth.is_configured(self.settings),
            history=history,
            last_error=self.store.last_error(subject, LIVE_ERROR_KEY[provider]) if creds else None,
        )

    def connections(self, subject: str) -> ConnectionsResponse:
        return ConnectionsResponse(providers=[self.connection(subject, p) for p in PROVIDERS])  # type: ignore[arg-type]

    # ---- Trading212 ------------------------------------------------------------------------
    async def connect_trading212(self, subject: str, key: str, secret: str) -> ProviderConnection:
        """Validate via the account summary BEFORE storing. Raises ProviderError; nothing stored on failure."""
        key, secret = key.strip(), secret.strip()
        client = self._require_live()
        adapter = Trading212Adapter(
            self.settings.t212_base_url, client, key, secret, clock=self._clock, wall_clock=self._clock
        )
        await adapter.account()  # raises auth / rate_limited / unavailable / bad_data
        self.store.set(subject, "trading212", {"api_key": key, "api_secret": secret})
        self.store.set_error(subject, LIVE_ERROR_KEY["trading212"], None)
        self._memo.pop(subject, None)
        return self.connection(subject, "trading212")

    # ---- Monzo -----------------------------------------------------------------------------
    def _monzo(self, subject: str, token: str) -> MonzoAdapter:
        async def refresher() -> str | None:
            creds = self.store.get(subject, "monzo")
            old = creds.get("refresh_token") if creds else None
            if not old or not monzo_oauth.is_configured(self.settings):
                return None
            try:
                new = await monzo_oauth.refresh(self.settings, str(old), self._http())
            except ProviderError:
                return None
            self.store.set(subject, "monzo", new)  # the refresh token is always replaced
            return str(new["access_token"])

        return MonzoAdapter(
            self.settings.monzo_base_url,
            self._http(),
            token,
            refresher=refresher,
            store=self.store,
            subject=subject,
            initial_sync_timeout=self.settings.monzo_initial_sync_timeout_seconds,
            clock=self._now,
        )

    async def connect_monzo_token(self, subject: str, token: str) -> ProviderConnection:
        """Dev convenience: validate a pasted playground token via whoami, store it, run the full sync."""
        token = token.strip()
        client = self._require_live()
        adapter = MonzoAdapter(self.settings.monzo_base_url, client, token)
        await adapter.whoami()
        self.store.set(subject, "monzo", {"access_token": token})
        await self._start_monzo_sync(subject)
        return self.connection(subject, "monzo")

    async def _start_monzo_sync(self, subject: str) -> bool:
        creds = self.store.get(subject, "monzo")
        if not creds:
            return False
        self._memo.pop(subject, None)
        return await self._monzo(subject, str(creds["access_token"])).full_sync()

    def monzo_start(self, subject: str) -> str:
        """Authorize URL for the user to open. Raises ProviderError("not_configured") without client id/secret."""
        if not monzo_oauth.is_configured(self.settings):
            raise ProviderError("not_configured", "Monzo OAuth is not configured", source="monzo")
        return monzo_oauth.authorize_url(self.settings, self.oauth_states.issue(subject))

    async def monzo_callback(self, state: str | None, code: str) -> str:
        """Exchange the code, store the tokens, run the full sync. Returns the subject that started the flow."""
        pending = self.oauth_states.consume(state)
        if pending is None:
            raise ProviderError("bad_state", "invalid or expired sign-in state", source="monzo")
        creds = await monzo_oauth.exchange_code(self.settings, code, self._require_live())
        self.store.set(pending.subject, "monzo", creds)
        await self._start_monzo_sync(pending.subject)
        return pending.subject

    async def monzo_sync(self, subject: str) -> HistoryStatus:
        """Retry the history import (for example after approving access in the Monzo app)."""
        creds = self.store.get(subject, "monzo")
        if not creds:
            raise ProviderError("not_connected", "Monzo is not connected", source="monzo")
        self._require_live()
        if self.store.history_is_full(subject):
            adapter = self._monzo(subject, str(creds["access_token"]))
            try:
                await adapter.sync_recent()
                self.store.set_error(subject, "monzo", None)
            except ProviderError as exc:
                self.store.set_error(subject, "monzo", exc.code)
            self._memo.pop(subject, None)
        else:
            await self._start_monzo_sync(subject)
        return HistoryStatus(**self.store.history_status(subject))

    def disconnect(self, subject: str, provider: Provider) -> None:
        self.store.forget(subject, provider)
        self.store.set_error(subject, LIVE_ERROR_KEY[provider], None)
        self._memo.pop(subject, None)

    # ---- live snapshot ---------------------------------------------------------------------
    async def _monzo_part(self, subject: str, creds: dict[str, Any]) -> tuple[list[Account], list[Transaction]]:
        adapter = self._monzo(subject, str(creds["access_token"]))
        acc = await adapter.current_account_id()
        accounts = await adapter.accounts(acc)
        return accounts, await adapter.sync_recent(acc)

    async def _t212_part(self, creds: dict[str, Any]) -> tuple[Account, list[Holding]]:
        adapter = Trading212Adapter(
            self.settings.t212_base_url,
            self._http(),
            str(creds["api_key"]),
            str(creds["api_secret"]),
            clock=self._clock,
            wall_clock=self._clock,
        )
        return await adapter.account(), await adapter.holdings()

    def _cached_snapshot(self, subject: str) -> FinanceSnapshot | None:
        raw = self.store.load_snapshot(subject)
        if raw is None:
            return None
        try:
            return FinanceSnapshot.model_validate(raw).model_copy(update={"status": "cached"})
        except ValidationError:
            return None

    async def live_snapshot(self, subject: str) -> FinanceSnapshot | None:
        """Live (or last-good cached) snapshot for a subject with connected providers, else None. Never raises."""
        monzo_creds = self._creds(subject, "monzo")
        t212_creds = self._creds(subject, "trading212")
        if monzo_creds is None and t212_creds is None:
            return None
        if not self._live_enabled():
            return self._cached_snapshot(subject)
        memo = self._memo.get(subject)
        if memo is not None and 0 <= self._clock() - memo[0] < SNAPSHOT_MEMO_SECONDS:
            return memo[1]

        names: list[str] = []
        jobs: list[Any] = []
        if monzo_creds is not None:
            names.append("monzo")
            jobs.append(self._monzo_part(subject, monzo_creds))
        if t212_creds is not None:
            names.append("trading212")
            jobs.append(self._t212_part(t212_creds))
        try:
            async with asyncio.timeout(LIVE_FETCH_TIMEOUT_SECONDS):
                results = await asyncio.gather(*jobs, return_exceptions=True)
        except Exception as exc:  # timeout or anything unexpected
            log.warning("live finance fetch failed (%s)", type(exc).__name__)
            return self._cached_snapshot(subject)

        failed = False
        accounts: list[Account] = []
        transactions: list[Transaction] = []
        holdings: list[Holding] = []
        for name, result in zip(names, results, strict=True):
            if isinstance(result, BaseException):
                failed = True
                code = result.code if isinstance(result, ProviderError) else "bad_data"
                self.store.set_error(subject, LIVE_ERROR_KEY[name], code)
                log.warning("live %s fetch failed (%s)", name, code)
                continue
            self.store.set_error(subject, LIVE_ERROR_KEY[name], None)
            if name == "monzo":
                accounts += result[0]
                transactions += result[1]
            else:
                accounts.append(result[0])
                holdings += result[1]
        if failed:
            return self._cached_snapshot(subject)
        snapshot = FinanceSnapshot(
            status="live",
            source="+".join(names),
            as_of=self._now().date().isoformat(),
            accounts=accounts,
            transactions=sorted(transactions, key=lambda t: (t.date, t.id)),
            holdings=holdings,
        )
        try:
            self.store.save_snapshot(subject, snapshot.model_dump(mode="json"))
        except OSError as exc:
            log.warning("could not save finance snapshot (%s)", type(exc).__name__)
        self._memo[subject] = (self._clock(), snapshot)
        return snapshot
