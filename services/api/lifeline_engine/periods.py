"""Period matching: find past years whose macro state looks like a given year.

Macro state per year (UK level):
    bank rate, bank rate change on the year before, CPI inflation, house price change,
    unemployment, stock return.
Each feature is standardised (z-score) across the candidate years plus the target year.
A feature with zero spread gets z = 0. Similarity is Euclidean distance on z-scores.
A key missing from the table contributes 0 for every year.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from lifeline_contracts.macro import MacroKey, MacroTable

FloatArray = NDArray[np.float64]

STATE_FEATURES: tuple[str, ...] = (
    "bank_rate",
    "bank_rate_change",
    "cpi_inflation",
    "house_price_change",
    "unemployment",
    "stock_return",
)
STATE_KEYS: tuple[MacroKey, ...] = (
    MacroKey.BANK_RATE,
    MacroKey.CPI_INFLATION,
    MacroKey.HOUSE_PRICE_CHANGE,
    MacroKey.UNEMPLOYMENT,
    MacroKey.STOCK_RETURN,
)


def _v(macro: MacroTable, key: MacroKey, year: int) -> float:
    try:
        return macro.value(key, year)
    except KeyError:
        return 0.0


def macro_state(macro: MacroTable, year: int) -> FloatArray:
    """Raw (not standardised) state vector for `year`, ordered as STATE_FEATURES."""
    bank = _v(macro, MacroKey.BANK_RATE, year)
    prev_years = [y for y in macro.years(MacroKey.BANK_RATE) if y < year]
    change = bank - _v(macro, MacroKey.BANK_RATE, prev_years[-1]) if prev_years else 0.0
    return np.array(
        [
            bank,
            change,
            _v(macro, MacroKey.CPI_INFLATION, year),
            _v(macro, MacroKey.HOUSE_PRICE_CHANGE, year),
            _v(macro, MacroKey.UNEMPLOYMENT, year),
            _v(macro, MacroKey.STOCK_RETURN, year),
        ],
        dtype=np.float64,
    )


def table_years(macro: MacroTable) -> list[int]:
    """Years that have at least one state key in the table."""
    years: set[int] = set()
    for key in STATE_KEYS:
        years.update(macro.years(key))
    return sorted(years)


def standardise(matrix: FloatArray) -> FloatArray:
    """Column z-scores. Columns with zero spread become 0."""
    mean = matrix.mean(axis=0)
    std = matrix.std(axis=0)
    safe = np.where(std > 0, std, 1.0)
    z: FloatArray = np.where(std > 0, (matrix - mean) / safe, 0.0)
    return z


@dataclass(frozen=True)
class PeriodMatch:
    year: int
    distance: float


def similar_years(
    macro: MacroTable,
    year: int,
    k: int,
    candidates: Iterable[int] | None = None,
    exclude: Sequence[int] = (),
) -> list[PeriodMatch]:
    """k past or present years whose macro state is closest to `year`.

    `candidates` defaults to every table year except `year`. Years in `exclude` are dropped.
    Ties break on the earlier year, so the result is deterministic.
    """
    if k <= 0:
        return []
    pool = table_years(macro) if candidates is None else sorted(set(candidates))
    skip = set(exclude) | {year}
    pool = [y for y in pool if y not in skip]
    if not pool:
        return []
    raw = np.vstack([macro_state(macro, y) for y in [year, *pool]])
    z = standardise(raw)
    d = np.sqrt(((z[1:] - z[0]) ** 2).sum(axis=1))
    order = sorted(range(len(pool)), key=lambda i: (float(d[i]), pool[i]))[:k]
    return [PeriodMatch(year=pool[i], distance=float(d[i])) for i in order]
