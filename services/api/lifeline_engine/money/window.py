"""Adaptive analysis window shared by habits and spending insights. Pure: callers pass `today`.

The window is the last `requested` complete calendar months ending at or before `today` (the current month
counts only when `today` is its last day). When the user has less history, the months available are used.
The first month with any data counts only if the data starts in its first FIRST_MONTH_GRACE_DAYS days;
otherwise it is a part month and is left out.
"""

from __future__ import annotations

import calendar
from collections.abc import Iterable
from datetime import date

from lifeline_contracts.finance import Transaction
from lifeline_engine.money import dates

MIN_MONTHS = 2
FIRST_MONTH_GRACE_DAYS = 5


def window_months_list(today: date, window_months: int) -> list[str]:
    """'YYYY-MM' for each month of the window, oldest first."""
    month_end = today.day == calendar.monthrange(today.year, today.month)[1]
    last = dates.month_of(today) if month_end else dates.prev_month(dates.month_of(today))
    return [dates.prev_month(last, k) for k in range(window_months - 1, -1, -1)]


def adaptive_months(txs: Iterable[Transaction], today: date, requested: int) -> list[str]:
    """The requested window, shortened to the complete months of history that exist (may be fewer than MIN_MONTHS)."""
    full = window_months_list(today, requested)
    first = min((t.date for t in txs), default=None)
    if first is None:
        return []
    first_complete = first[:7]
    if int(first[8:10]) > FIRST_MONTH_GRACE_DAYS:
        first_complete = dates.month_of(dates.add_months(dates.month_bounds(first_complete)[0], 1))
    return [m for m in full if m >= first_complete]


def window_note(used: int, requested: int) -> str | None:
    if used >= requested:
        return None
    return f"Based on your last {used} months" if used != 1 else "Based on your last month"
