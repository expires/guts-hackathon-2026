"""Fast read-only view over a `MacroTable`.

`MacroTable.get` scans every value on each call. A life replay makes thousands of lookups,
so this view indexes the table once. Lookup rules match `MacroTable.get` exactly:
nearest year when the year is missing, UK value with note "UK average used" when the
region is missing.
"""

from __future__ import annotations

from lifeline_contracts.domain import SourceRef
from lifeline_contracts.macro import MacroKey, MacroTable, MacroValue
from lifeline_sim.params import SAVINGS_FLOOR, SAVINGS_SPREAD, TRACKER_MARGIN, VARIABLE_MARGIN

UK = "uk"
PRICE_BASE_YEAR = 2024
PRICE_LEVEL = "price_level"
# Series that have regional data. Only these get "UK average used" when a region is missing.
REGIONAL_KEYS = frozenset(
    {
        MacroKey.HOUSE_PRICE,
        MacroKey.HOUSE_PRICE_CHANGE,
        MacroKey.MEDIAN_PAY,
        MacroKey.UNEMPLOYMENT,
        MacroKey.OWNER_OCCUPIED_SHARE,
        MacroKey.RENT_CHANGE,
        MacroKey.BURGLARY_RATE,
        MacroKey.FLOOD_RISK,
    }
)
PAY_GROWTH = "pay_growth"
TRACKER_NOW = "tracker_now"  # 2-year tracker rate: BoE IUMBV48 when present, else Bank Rate + TRACKER_MARGIN
BEST_SAVINGS_RATE = "best_savings_rate"  # top easy-access rate the sim pays: Bank Rate + SAVINGS_SPREAD, floored
SVR_RATE = (
    "svr_rate"  # variable mortgage rate: Bank Rate + VARIABLE_MARGIN  # percent y/y growth of regional median pay
)


class MacroView:
    def __init__(self, table: MacroTable) -> None:
        self.table = table
        self._by: dict[tuple[MacroKey, int, str], MacroValue] = {}
        years: dict[MacroKey, set[int]] = {}
        for v in table.values.values():
            self._by[(v.key, v.year, v.region or UK)] = v
            years.setdefault(v.key, set()).add(v.year)
        self._years: dict[MacroKey, list[int]] = {k: sorted(ys) for k, ys in years.items()}
        self._get_cache: dict[tuple[MacroKey, int, str | None], MacroValue | None] = {}
        self._env_cache: dict[tuple[int, str], dict[str, float]] = {}
        self._price_cache: dict[int, float] = {}

    def has(self, key: MacroKey) -> bool:
        return key in self._years

    def get(self, key: MacroKey, year: int, region: str | None = None) -> MacroValue | None:
        """Same rules as `MacroTable.get`, but returns None when the key has no data."""
        ck = (key, year, region)
        if ck in self._get_cache:
            return self._get_cache[ck]
        result = self._lookup(key, year, region)
        self._get_cache[ck] = result
        return result

    def _lookup(self, key: MacroKey, year: int, region: str | None) -> MacroValue | None:
        years = self._years.get(key)
        if not years:
            return None
        note: str | None = None
        if year not in years:
            year = min(years, key=lambda y: (abs(y - year), y))
            note = "nearest year used"
        if region is not None:
            hit = self._by.get((key, year, region))
            if hit is not None:
                return hit if note is None else hit.model_copy(update={"note": note})
        uk = self._by.get((key, year, UK))
        if uk is None:
            return None
        if region is not None and key in REGIONAL_KEYS:
            note = "UK average used" if note is None else f"UK average used; {note}"
        return uk if note is None else uk.model_copy(update={"note": note})

    def value(self, key: MacroKey, year: int, region: str | None = None, default: float = 0.0) -> float:
        v = self.get(key, year, region)
        return default if v is None else v.value

    def price_level(self, year: int) -> float:
        """Consumer price level relative to 2024 (2024 = 1.0), chained from UK CPI inflation."""
        if year in self._price_cache:
            return self._price_cache[year]
        level = 1.0
        if year > PRICE_BASE_YEAR:
            for y in range(PRICE_BASE_YEAR + 1, year + 1):
                level *= 1 + self.value(MacroKey.CPI_INFLATION, y, None, 2.0) / 100
        elif year < PRICE_BASE_YEAR:
            for y in range(year + 1, PRICE_BASE_YEAR + 1):
                level /= 1 + self.value(MacroKey.CPI_INFLATION, y, None, 2.0) / 100
        self._price_cache[year] = level
        return level

    def env(self, year: int, region: str) -> dict[str, float]:
        """Formula variables: each key, `prev_<key>`, `price_level` and `pay_growth`."""
        ck = (year, region)
        cached = self._env_cache.get(ck)
        if cached is not None:
            return cached
        out: dict[str, float] = {}
        for key in MacroKey:
            out[key.value] = self.value(key, year, region)
            out[f"prev_{key.value}"] = self.value(key, year - 1, region)
        out[PRICE_LEVEL] = self.price_level(year)
        out[PAY_GROWTH] = self.growth(MacroKey.MEDIAN_PAY, year, region) * 100
        bank = out[MacroKey.BANK_RATE.value]
        # Revert-to and tracker rates: BoE quoted series when the table has them (ADR 0020),
        # else Bank Rate plus a fixed margin.
        svr = self.get(MacroKey.MORTGAGE_SVR, year, None)
        out[SVR_RATE] = svr.value if svr is not None else bank + VARIABLE_MARGIN
        tracker = self.get(MacroKey.MORTGAGE_TRACKER, year, None)
        out[TRACKER_NOW] = tracker.value if tracker is not None else bank + TRACKER_MARGIN
        out[BEST_SAVINGS_RATE] = max(SAVINGS_FLOOR, out[MacroKey.BANK_RATE.value] + SAVINGS_SPREAD)
        self._env_cache[ck] = out
        return out

    def growth(self, key: MacroKey, year: int, region: str | None = None) -> float:
        """Year-on-year growth of a level series (0.03 = 3%).

        After the last year in the table, repeats the last known growth instead of 0.
        """
        years = self._years.get(key)
        if not years or len(years) < 2:
            return 0.0
        y = max(years[1], min(year, years[-1]))
        prev = self.value(key, y - 1, region)
        return self.value(key, y, region) / prev - 1 if prev > 0 else 0.0

    def source_ref(self, key: MacroKey, year: int, region: str | None) -> SourceRef | None:
        v = self.get(key, year, region)
        if v is None:
            return None
        return SourceRef(source=v.source, series_id=v.series_id, status=v.status, note=v.note)


def macro_names() -> dict[str, MacroKey]:
    """Formula variable name -> macro key it reads. `price_level` reads CPI inflation."""
    out: dict[str, MacroKey] = {}
    for key in MacroKey:
        out[key.value] = key
        out[f"prev_{key.value}"] = key
    out[PRICE_LEVEL] = MacroKey.CPI_INFLATION
    out[PAY_GROWTH] = MacroKey.MEDIAN_PAY
    out[SVR_RATE] = MacroKey.BANK_RATE
    out[BEST_SAVINGS_RATE] = MacroKey.BANK_RATE
    out[TRACKER_NOW] = MacroKey.BANK_RATE
    return out


# Derived names whose own series, when the table has it, is cited instead of (and as well as) Bank Rate.
SOFT_SOURCES: dict[str, MacroKey] = {SVR_RATE: MacroKey.MORTGAGE_SVR, TRACKER_NOW: MacroKey.MORTGAGE_TRACKER}
