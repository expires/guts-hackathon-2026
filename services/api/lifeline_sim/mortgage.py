"""Mortgage maths. Uses `lifeline_engine.finance` (W2) when present, else a local annuity formula."""

from __future__ import annotations

from collections.abc import Callable


def _monthly_payment(principal: float, annual_rate_pct: float, years: int) -> float:
    n = max(1, round(years * 12))
    r = annual_rate_pct / 100 / 12
    if principal <= 0:
        return 0.0
    if r == 0:
        return principal / n
    return principal * r / (1 - (1 + r) ** -n)


def _remaining_balance(principal: float, annual_rate_pct: float, years: int, months_paid: int) -> float:
    n = max(1, round(years * 12))
    k = min(max(months_paid, 0), n)
    r = annual_rate_pct / 100 / 12
    if principal <= 0:
        return 0.0
    if r == 0:
        return principal * (1 - k / n)
    pay = _monthly_payment(principal, annual_rate_pct, years)
    return max(0.0, principal * (1 + r) ** k - pay * ((1 + r) ** k - 1) / r)


def _resolve() -> tuple[Callable[[float, float, int], float], Callable[[float, float, int, int], float]]:
    try:
        from lifeline_engine import finance  # W2. Pure, so the sim may use it.
    except ImportError:
        return _monthly_payment, _remaining_balance
    mp = getattr(finance, "monthly_payment", None)
    rb = getattr(finance, "remaining_balance", None)
    if callable(mp) and callable(rb):
        return mp, rb
    return _monthly_payment, _remaining_balance


monthly_payment, remaining_balance = _resolve()
