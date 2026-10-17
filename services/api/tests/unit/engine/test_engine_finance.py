"""Hand-calculated cases for lifeline_engine.finance.

Reference values come from the closed-form annuity formula
P * r / (1 - (1 + r) ** -n), with r = annual% / 1200 and n = years * 12,
and match standard UK mortgage calculators.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from lifeline_engine.finance import compound, monthly_payment, real_value, remaining_balance

# ---------- monthly_payment: hand-calculated ----------


def test_spec_case_180k_25y_4_98pct() -> None:
    assert round(monthly_payment(180_000, 4.98, 25), 2) == 1050.17


def test_100k_30y_6pct() -> None:
    assert round(monthly_payment(100_000, 6.0, 30), 2) == 599.55


def test_200k_25y_5pct() -> None:
    assert round(monthly_payment(200_000, 5.0, 25), 2) == 1169.18


def test_zero_rate_is_straight_line() -> None:
    assert monthly_payment(120_000, 0.0, 25) == pytest.approx(400.0)


def test_zero_principal() -> None:
    assert monthly_payment(0, 5.0, 25) == 0.0


@pytest.mark.parametrize(
    ("principal", "rate", "years"),
    [(-1.0, 5.0, 25), (100.0, -0.1, 25), (100.0, 5.0, 0), (100.0, 5.0, -3)],
)
def test_bad_inputs_raise(principal: float, rate: float, years: float) -> None:
    with pytest.raises(ValueError):
        monthly_payment(principal, rate, years)


# ---------- remaining_balance ----------


def test_balance_after_one_year_100k_6pct_30y() -> None:
    assert remaining_balance(100_000, 6.0, 30, 12) == pytest.approx(98_771.99, abs=0.01)


def test_balance_at_start_and_end() -> None:
    assert remaining_balance(180_000, 4.98, 25, 0) == pytest.approx(180_000)
    assert remaining_balance(180_000, 4.98, 25, 300) == pytest.approx(0.0, abs=1e-6)
    assert remaining_balance(180_000, 4.98, 25, 400) == 0.0


def test_balance_zero_rate() -> None:
    assert remaining_balance(120_000, 0.0, 25, 150) == pytest.approx(60_000)


def test_balance_negative_months_raises() -> None:
    with pytest.raises(ValueError):
        remaining_balance(100_000, 5.0, 25, -1)


# ---------- compound and real_value ----------


def test_compound_two_years_5pct() -> None:
    assert compound(1_000, 5.0, 2) == pytest.approx(1_102.50)


def test_compound_negative_rate() -> None:
    assert compound(1_000, -10.0, 1) == pytest.approx(900.0)


def test_real_value_two_years_10pct() -> None:
    assert real_value(1_000, [10.0, 10.0]) == pytest.approx(826.446281, rel=1e-9)


def test_real_value_no_inflation() -> None:
    assert real_value(1_000, []) == 1_000


# ---------- properties ----------

principals = st.floats(min_value=1_000, max_value=2_000_000, allow_nan=False)
rates = st.floats(min_value=0.0, max_value=20.0, allow_nan=False)
terms = st.integers(min_value=1, max_value=40)


@given(principals, rates, rates, terms)
def test_payment_monotone_in_rate(p: float, r1: float, r2: float, y: int) -> None:
    lo, hi = sorted((r1, r2))
    assert monthly_payment(p, lo, y) <= monthly_payment(p, hi, y) + 1e-9


@given(principals, principals, rates, terms)
def test_payment_monotone_in_principal(p1: float, p2: float, r: float, y: int) -> None:
    lo, hi = sorted((p1, p2))
    assert monthly_payment(lo, r, y) <= monthly_payment(hi, r, y) + 1e-9


@given(principals, rates, terms)
def test_payment_covers_principal(p: float, r: float, y: int) -> None:
    assert monthly_payment(p, r, y) * y * 12 >= p - 1e-6


@given(principals, rates, terms, st.integers(min_value=0, max_value=480))
def test_balance_within_bounds_and_decreasing(p: float, r: float, y: int, m: int) -> None:
    b0 = remaining_balance(p, r, y, m)
    b1 = remaining_balance(p, r, y, m + 1)
    assert -1e-6 <= b1 <= b0 + 1e-6 <= p + 1e-6


@given(st.floats(min_value=0, max_value=1e7), rates, st.floats(min_value=0, max_value=50))
def test_compound_roundtrip_with_real_value(v: float, r: float, y: float) -> None:
    grown = compound(v, r, y)
    if y == int(y):
        assert real_value(grown, [r] * int(y)) == pytest.approx(v, rel=1e-9, abs=1e-6)
