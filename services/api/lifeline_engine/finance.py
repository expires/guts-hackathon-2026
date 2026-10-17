"""Pure money maths. No I/O, no clock, no RNG.

Conventions:
- Rates are percent per year (4.98 means 4.98%).
- Mortgages are UK repayment annuities with monthly compounding: r = annual% / 1200.
- Results are unrounded floats. Round only for display.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

__all__ = ["compound", "monthly_payment", "real_value", "remaining_balance", "term_months"]


def term_months(years: float) -> int:
    """Number of monthly payments for a term in years. Rounds to the nearest month."""
    n = round(years * 12)
    if n <= 0:
        raise ValueError("term must be at least one month")
    return n


def _check(principal: float, annual_rate_pct: float) -> None:
    if principal < 0:
        raise ValueError("principal must be >= 0")
    if annual_rate_pct < 0:
        raise ValueError("annual_rate_pct must be >= 0")


def monthly_payment(principal: float, annual_rate_pct: float, years: float) -> float:
    """Level monthly payment that clears `principal` over `years`.

    Example: monthly_payment(180_000, 4.98, 25) -> 1050.17 (rounded).
    A 0% rate gives principal / months.
    """
    _check(principal, annual_rate_pct)
    n = term_months(years)
    if principal == 0:
        return 0.0
    r = annual_rate_pct / 1200.0
    if r == 0:
        return principal / n
    # expm1/log1p keep precision when r is tiny.
    return principal * r / -math.expm1(-n * math.log1p(r))


def remaining_balance(principal: float, annual_rate_pct: float, years: float, months_paid: int) -> float:
    """Outstanding balance after `months_paid` level payments (exact, unrounded payment).

    Returns `principal` at 0 months and 0.0 at or after the end of the term.
    """
    _check(principal, annual_rate_pct)
    if months_paid < 0:
        raise ValueError("months_paid must be >= 0")
    n = term_months(years)
    if months_paid >= n or principal == 0:
        return 0.0
    if months_paid == 0:
        return principal
    r = annual_rate_pct / 1200.0
    if r == 0:
        return principal * (n - months_paid) / n
    pay = monthly_payment(principal, annual_rate_pct, years)
    lg = months_paid * math.log1p(r)
    return max(0.0, principal * math.exp(lg) - pay * math.expm1(lg) / r)


def compound(value: float, annual_rate_pct: float, years: float) -> float:
    """Grow `value` at `annual_rate_pct` per year, compounded annually. Rate may be negative (>-100)."""
    if annual_rate_pct <= -100:
        raise ValueError("annual_rate_pct must be > -100")
    return value * math.pow(1.0 + annual_rate_pct / 100.0, years)


def real_value(nominal: float, inflation_pcts: Iterable[float]) -> float:
    """Deflate `nominal` by a sequence of annual inflation rates (percent), one per year."""
    factor = 1.0
    for pct in inflation_pcts:
        if pct <= -100:
            raise ValueError("inflation must be > -100")
        factor *= 1.0 + pct / 100.0
    return nominal / factor
