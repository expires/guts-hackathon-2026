"""Per-user account record (ADR 0029). One document per subject, kind "account"."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Literal, cast

from lifeline_api import money, onboarding
from lifeline_api.auth import DOC_REVOKED_BEFORE, revoke_all
from lifeline_api.state import AppState
from lifeline_api.store import StoreUnavailable
from lifeline_contracts.account import Me

log = logging.getLogger(__name__)

DOC_ACCOUNT = "account"


def provider_of(sub: str) -> Literal["apple", "demo"]:
    return "apple" if sub.startswith("apple_") else "demo"


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


async def ensure(state: AppState, sub: str, display_name: str | None = None) -> dict[str, Any]:
    """The account document, created on first use."""
    doc = await state.store.get_doc(sub, DOC_ACCOUNT)
    if doc is None:
        doc = {"created_at": _now(), "provider": provider_of(sub), "display_name": display_name,
               }
        await state.store.put_doc(sub, DOC_ACCOUNT, doc)
    elif display_name and not doc.get("display_name"):
        doc["display_name"] = display_name
        await state.store.put_doc(sub, DOC_ACCOUNT, doc)
    return cast(dict[str, Any], doc)


async def ensure_quietly(state: AppState, sub: str, display_name: str | None = None) -> None:
    """Sign-in must work while Postgres is down. The account is then created on first use."""
    try:
        await ensure(state, sub, display_name)
    except StoreUnavailable:
        log.warning("account not recorded at sign-in: store unavailable")


BANK_NAMES = {"monzo": "Monzo"}


async def bank_name(state: AppState, sub: str) -> str | None:
    """Name of the user's connected bank, read from the hub's provider connections (Yaffy's integration).
    None when nothing is connected, or before that integration is merged. Never fails the request."""
    connections = getattr(state.hub, "connections", None)
    if connections is None:
        return None
    try:
        resp: Any = await connections(sub)
    except Exception as exc:
        log.warning("bank connections unavailable: %s", type(exc).__name__)
        return None
    for conn in getattr(resp, "providers", []) or []:
        name = BANK_NAMES.get(str(getattr(conn, "provider", "")))
        if name and getattr(conn, "connected", False):
            return name
    return None


async def me(state: AppState, sub: str) -> Me:
    doc = await ensure(state, sub)
    # Only the user's own data counts (demo-mode sample data does not). Both fields come from the one
    # stored snapshot, so they always agree.
    own = await money.stored_snapshot(state, sub)
    return Me(
        id=sub,
        display_name=doc.get("display_name"),
        auth_provider=doc.get("provider", provider_of(sub)),
        created_at=doc["created_at"],
        bank_name=await bank_name(state, sub),
        has_finance_data=own is not None,
        finance_inputs=onboarding.inputs_of(own),
    )


async def _leave_rooms(state: AppState, sub: str) -> None:
    from lifeline_api.routes.rooms import leave_all_rooms  # routes import this module

    try:
        await leave_all_rooms(state, sub)
    except Exception as exc:
        log.warning("rooms not cleared on reset: %s", type(exc).__name__)
    from lifeline_api.routes.circles import leave_all

    await leave_all(state, sub)


async def erase(state: AppState, sub: str, *, keep_account: bool) -> int:
    """Delete every record of the user: money data, lives, plan, goals, budgets, guesses, threads, health.

    The money data goes first: if the hub cannot delete it, nothing else is touched and the caller gets 503.
    Account deletion (keep_account=False) also rejects every token issued before now.
    """
    try:
        await money.delete_snapshot(state, sub)
    except StoreUnavailable:
        raise
    except Exception as exc:
        log.warning("user snapshot delete failed: %s", type(exc).__name__)
        raise StoreUnavailable() from exc
    await _leave_rooms(state, sub)
    if keep_account:
        deleted = await state.store.delete_owner(sub, keep=(DOC_ACCOUNT, DOC_REVOKED_BEFORE))
        await ensure(state, sub)
        return deleted
    await revoke_all(state, sub)  # first, so no old token can recreate the account meanwhile
    return await state.store.delete_owner(sub, keep=(DOC_REVOKED_BEFORE,))
