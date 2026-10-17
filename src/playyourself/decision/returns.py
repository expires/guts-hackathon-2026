"""Monthly return series loading. Data is SYNTHETIC (see data/mock/returns_monthly.csv)."""

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ASSETS = ("global_equity", "uk_equity", "gilts", "cash")

# TODO: reconcile these windows with Ash's engine windows. Inclusive month bounds.
PERIODS: dict[str, tuple[str, str]] = {
    "gfc_2008": ("2007-10", "2012-12"),
    "covid_2020": ("2020-01", "2021-12"),
    "rates_2022": ("2021-12", "2024-06"),
    "full": ("2000-01", "2026-09"),
}

DEFAULT_PATH = Path(__file__).resolve().parents[3] / "data" / "mock" / "returns_monthly.csv"


@dataclass
class ReturnSeries:
    months: list[str]  # YYYY-MM
    data: np.ndarray  # (T, n_assets) monthly simple returns
    assets: tuple[str, ...] = ASSETS

    def __post_init__(self) -> None:
        if self.data.ndim != 2 or self.data.shape != (len(self.months), len(self.assets)):
            raise ValueError("data shape must be (len(months), len(assets))")

    def slice(self, start: str, end: str) -> "ReturnSeries":
        """Inclusive month range. Raises ValueError if bounds are outside the series."""
        if start not in self.months or end not in self.months:
            raise ValueError(f"period {start}..{end} outside available data")
        i0, i1 = self.months.index(start), self.months.index(end)
        if i1 < i0:
            raise ValueError("end before start")
        return ReturnSeries(self.months[i0 : i1 + 1], self.data[i0 : i1 + 1].copy(), self.assets)

    def column(self, asset: str) -> np.ndarray:
        return self.data[:, self.assets.index(asset)]


def load_returns(path: Path | None = None) -> ReturnSeries:
    p = path or DEFAULT_PATH
    with p.open(encoding="utf-8") as f:
        lines = [ln for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
    rows = list(csv.DictReader(lines))
    assets = tuple(c for c in rows[0] if c != "month")
    months = [r["month"] for r in rows]
    data = np.array([[float(r[a]) for a in assets] for r in rows], dtype=float)
    return ReturnSeries(months, data, assets)
