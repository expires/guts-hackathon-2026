"""Monthly return series loader. The bundled data is SYNTHETIC (see the fixture header line).

I/O lives here so lifeline_engine and lifeline_eval stay pure: they take a ReturnSeries argument.
The market adapter (lifeline_data/adapters/market.py) only has FTSE All-Share year-on-year changes and a
gilt yield level, not monthly total returns for UK equity, global equity and gilts, so it cannot replace this.
"""

from __future__ import annotations

import csv
from pathlib import Path

from lifeline_contracts.investing import RETURNS_LABEL, ReturnSeries

DEFAULT_PATH = Path(__file__).resolve().parent / "fixtures" / "returns_monthly_synthetic.csv"


def load_returns(path: Path | None = None) -> ReturnSeries:
    p = path or DEFAULT_PATH
    with p.open(encoding="utf-8", newline="") as f:
        lines = [ln for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
    rows = list(csv.DictReader(lines))
    if not rows:
        raise ValueError(f"no return rows in {p}")
    assets = [c for c in rows[0] if c != "month"]
    return ReturnSeries(
        months=[r["month"] for r in rows],
        assets=assets,
        returns=[[float(r[a]) for a in assets] for r in rows],
        label=RETURNS_LABEL,
        data_status="mock",
    )
