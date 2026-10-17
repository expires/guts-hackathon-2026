"""Calls into the pure modules (sim, engine). Maps their errors to the shared error format.

Sim and engine functions are synchronous and CPU bound, so they run in a worker thread.
"""

from __future__ import annotations

from collections.abc import Callable

from anyio import to_thread

from lifeline_api.errors import ApiError
from lifeline_sim.errors import SimError

# SimError.code -> HTTP status. Unknown codes are state conflicts (409).
SIM_STATUS: dict[str, int] = {
    "pending_events": 409,
    "dead": 409,
    "payment_required": 402,
    "not_found": 404,
    "invalid_choice": 422,
    "invalid_action": 422,
    "invalid_input": 422,
}


def sim_error_to_api(exc: SimError) -> ApiError:
    return ApiError(SIM_STATUS.get(exc.code, 409), exc.code, exc.message, source="sim")


# MacroTable.get raises KeyError with these prefixes when real data has a gap (ADR 0027, live mode).
_MACRO_GAP_PREFIXES = ("no data for ", "no UK value for ")


def macro_gap_to_api(exc: KeyError) -> ApiError | None:
    """409 data_unavailable for a MacroTable gap, naming the series. None for any other KeyError (a real bug)."""
    msg = str(exc.args[0]) if exc.args else ""
    if not msg.startswith(_MACRO_GAP_PREFIXES):
        return None
    return ApiError(409, "data_unavailable", f"Real data is missing for this: {msg}.", source="data")


async def call_pure[**P, T](fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    def run() -> T:
        try:
            return fn(*args, **kwargs)
        except SimError as exc:
            raise sim_error_to_api(exc) from exc
        except KeyError as exc:
            gap = macro_gap_to_api(exc)
            if gap is None:
                raise
            raise gap from exc

    return await to_thread.run_sync(run)
