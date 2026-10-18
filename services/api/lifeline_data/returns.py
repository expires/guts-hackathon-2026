"""Monthly return series loader. The bundled data is SYNTHETIC (see the fixture header line).

I/O lives here so lifeline_engine stays pure: it takes a ReturnSeries argument. No real monthly total-return
series for shares and bonds exists in the data hub (the market adapter has FTSE All-Share year-on-year changes and
a gilt yield level only), so Penny's mix history uses this illustrative series and labels it that way.
"""

from __future__ import annotations

import csv
from pathlib import Path

from lifeline_engine.portfolio import ReturnSeries

DEFAULT_PATH = Path(__file__).resolve().parent / "fixtures" / "returns_monthly_synthetic.csv"


def load_returns(path: Path | None = None) -> ReturnSeries:
    p = path or DEFAULT_PATH
    with p.open(encoding="utf-8", newline="") as f:
        lines = [ln for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
    rows = list(csv.DictReader(lines))
    if not rows:
        raise ValueError(f"no return rows in {p}")
    assets = tuple(c for c in rows[0] if c != "month")
    return ReturnSeries(
        months=tuple(r["month"] for r in rows),
        assets=assets,
        returns=tuple(tuple(float(r[a]) for a in assets) for r in rows),
    )
