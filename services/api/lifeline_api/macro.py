"""The MacroTable for API routes.

- `table(state)`: one build at a time per process; every caller during a build shares it (V1 cold start).
- `table_fast(state)`: never waits long for a cold build (V1 O1). If the build is not done within a short
  budget, it returns the last good table (process memory, else the copy kept in Postgres), with every value
  relabelled "cached". It returns (table, fresh) so callers can finish their work again when the build lands.
- Every finished build is kept as the last good table, in memory and in Postgres (macro_tables + a pointer).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from lifeline_api.state import AppState
from lifeline_api.store import macro_hash
from lifeline_contracts.macro import MacroTable

log = logging.getLogger(__name__)

FAST_BUDGET_SECONDS = 0.5
POINTER_OWNER, POINTER_KIND = "system", "macro_latest"


def _build(state: AppState) -> asyncio.Task[Any]:
    task: asyncio.Task[Any] | None = state.memo.get(("macro-build",))
    if task is None or task.done():
        task = asyncio.ensure_future(state.hub.macro_table())
        state.memo[("macro-build",)] = task
        task.add_done_callback(lambda t: _keep(state, t))
    return task


def _keep(state: AppState, task: asyncio.Task[Any]) -> None:
    if task.cancelled() or task.exception() is not None:
        return
    result: MacroTable = task.result()
    if not result.values:
        return  # an empty table (offline live mode) is not worth keeping
    state.memo[("macro-last",)] = result
    with contextlib.suppress(RuntimeError):  # no running loop: nothing to persist from
        persist = asyncio.get_running_loop().create_task(_persist(state, result))
        state.games.add(persist)
        persist.add_done_callback(state.games.discard)


async def _persist(state: AppState, result: MacroTable) -> None:
    try:
        digest = macro_hash(result)
        await state.store.put_macro(digest, result)
        await state.store.put_doc(POINTER_OWNER, POINTER_KIND, {"hash": digest})
    except Exception as exc:
        log.info("last good macro table not saved: %s", type(exc).__name__)


async def table(state: AppState) -> MacroTable:
    result: MacroTable = await asyncio.shield(_build(state))
    return result


def _as_cached(t: MacroTable) -> MacroTable:
    values = {k: v.model_copy(update={"status": "cached"}) if v.status == "live" else v for k, v in t.values.items()}
    return t.model_copy(update={"values": values})


async def _last_good(state: AppState) -> MacroTable | None:
    hit: MacroTable | None = state.memo.get(("macro-last",))
    if hit is not None:
        return hit
    try:
        ptr = await state.store.get_doc(POINTER_OWNER, POINTER_KIND)
        if ptr is None:
            return None
        stored = await state.store.get_macro(str(ptr["hash"]))
    except Exception:
        return None
    if stored is not None:
        state.memo[("macro-last",)] = stored
    return stored


async def table_fast(state: AppState, budget: float | None = None) -> tuple[MacroTable, bool]:
    """(table, fresh). Waits at most `budget` seconds for a build, then uses the last good table, labelled
    cached. With no last good table at all (very first start), it waits for the build."""
    task = _build(state)
    try:
        result: MacroTable = await asyncio.wait_for(asyncio.shield(task),
                                                    timeout=FAST_BUDGET_SECONDS if budget is None else budget)
        return result, True
    except TimeoutError:
        last = await _last_good(state)
        if last is None:
            return await table(state), True
        return _as_cached(last), False
