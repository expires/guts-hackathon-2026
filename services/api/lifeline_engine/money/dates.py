"""Calendar helpers for the money insights. Pure: no clock. Callers pass `today`."""

from __future__ import annotations

import calendar
from datetime import date, timedelta

__all__ = ["add_days", "add_months", "iso", "month_bounds", "month_of", "parse", "prev_month", "date"]


def parse(text: str) -> date:
    return date.fromisoformat(text)


def iso(d: date) -> str:
    return d.isoformat()


def add_days(d: date, n: int) -> date:
    return d + timedelta(days=n)


def add_months(d: date, n: int) -> date:
    """Same day `n` months later. A day past the month end moves to the last day of that month."""
    m = d.month - 1 + n
    year, month = d.year + m // 12, m % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def month_of(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def month_bounds(month: str) -> tuple[date, date]:
    """First and last day of a 'YYYY-MM' month."""
    year, mon = int(month[:4]), int(month[5:7])
    return date(year, mon, 1), date(year, mon, calendar.monthrange(year, mon)[1])


def prev_month(month: str, n: int = 1) -> str:
    return month_of(add_months(month_bounds(month)[0], -n))
