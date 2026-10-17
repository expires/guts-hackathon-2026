"""Safe MacroTable lookups for the engine. Pure."""

from __future__ import annotations

from lifeline_contracts.domain import SourceRef
from lifeline_contracts.macro import MacroKey, MacroTable

DEFAULT_YEAR = 2025


def value_or(macro: MacroTable, key: MacroKey, year: int, region: str | None, default: float) -> float:
    """Table value, or `default` when the table has no data for `key`."""
    try:
        return macro.value(key, year, region)
    except KeyError:
        return default


def latest_year(macro: MacroTable) -> int:
    """Latest year with a Bank Rate or median pay value. DEFAULT_YEAR for an empty table."""
    for key in (MacroKey.BANK_RATE, MacroKey.MEDIAN_PAY):
        years = macro.years(key)
        if years:
            return years[-1]
    years_any = sorted({v.year for v in macro.values.values()})
    return years_any[-1] if years_any else DEFAULT_YEAR


def source_ref(macro: MacroTable, key: MacroKey, year: int, region: str | None = None) -> SourceRef | None:
    """SourceRef for one lookup, or None when the table has no data for `key`."""
    try:
        v = macro.get(key, year, region)
    except KeyError:
        return None
    return SourceRef(source=v.source, series_id=v.series_id, status=v.status, note=v.note)
