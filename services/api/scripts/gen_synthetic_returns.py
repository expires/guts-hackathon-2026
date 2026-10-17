"""Generate lifeline_data/fixtures/returns_monthly_synthetic.csv: SYNTHETIC stylised monthly returns.

Deterministic (seeded). Not real index data. Run: uv run python scripts/gen_synthetic_returns.py (from services/api)
"""

from pathlib import Path

import numpy as np

SEED = 20260930
ASSETS = ("global_equity", "uk_equity", "gilts", "cash")
HEADER = "# SYNTHETIC DATA — illustrative only, not real index returns"
OUT = Path(__file__).resolve().parents[1] / "lifeline_data" / "fixtures" / "returns_monthly_synthetic.csv"

# annual (drift, vol) per asset
PARAMS = {
    "global_equity": (0.07, 0.15),
    "uk_equity": (0.065, 0.15),
    "gilts": (0.03, 0.06),
    "cash": (0.02, 0.002),
}
# Long-run annualised (geometric) return each asset is pinned to over the whole series.
# Without this, one seed's noise plus net-negative shock windows can leave equities
# below zero over 26 years, which makes every backtest look implausible.
TARGET_ANNUAL = {"global_equity": 0.065, "uk_equity": 0.05, "gilts": 0.025, "cash": 0.018}
# (start, end inclusive, {asset: cumulative simple return over window})
SHOCKS = [
    ("2007-10", "2009-02", {"global_equity": -0.45, "uk_equity": -0.42, "gilts": 0.08}),
    ("2009-03", "2009-12", {"global_equity": 0.40, "uk_equity": 0.35, "gilts": -0.02}),
    ("2020-02", "2020-03", {"global_equity": -0.30, "uk_equity": -0.33, "gilts": 0.02}),
    ("2020-04", "2020-11", {"global_equity": 0.45, "uk_equity": 0.40, "gilts": 0.0}),
    ("2022-01", "2022-10", {"global_equity": -0.20, "uk_equity": -0.12, "gilts": -0.25}),
]


def month_labels(start=(2000, 1), end=(2026, 9)) -> list[str]:
    y, m = start
    out = []
    while (y, m) <= end:
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def generate() -> tuple[list[str], np.ndarray]:
    rng = np.random.default_rng(SEED)
    months = month_labels()
    t = len(months)
    data = np.zeros((t, len(ASSETS)))
    for j, a in enumerate(ASSETS):
        mu, sig = PARAMS[a]
        data[:, j] = mu / 12 + sig / np.sqrt(12) * rng.standard_normal(t)
    data[:, 3] = np.clip(data[:, 3], 0.0, None)
    # Shocks: keep the noise shape but shift log-returns so the window hits its target exactly.
    for start, end, targets in SHOCKS:
        i0, i1 = months.index(start), months.index(end)
        for a, tgt in targets.items():
            j = ASSETS.index(a)
            logs = np.log1p(np.clip(data[i0 : i1 + 1, j], -0.5, None))
            shift = (np.log1p(tgt) - logs.sum()) / len(logs)
            data[i0 : i1 + 1, j] = np.expm1(logs + shift)
    # Pin long-run returns by shifting only the non-shock months, so shock windows stay exact.
    calm = np.ones(t, dtype=bool)
    for start, end, _ in SHOCKS:
        calm[months.index(start) : months.index(end) + 1] = False
    for j, a in enumerate(ASSETS):
        logs = np.log1p(data[:, j])
        shift = (t / 12 * np.log1p(TARGET_ANNUAL[a]) - logs.sum()) / calm.sum()
        logs[calm] += shift
        data[:, j] = np.expm1(logs)
    return months, data


def main() -> None:
    months, data = generate()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        f.write(HEADER + "\n")
        f.write("month," + ",".join(ASSETS) + "\n")
        for m, row in zip(months, data, strict=True):
            f.write(m + "," + ",".join(f"{x:.6f}" for x in row) + "\n")
    print(f"wrote {OUT} ({len(months)} rows)")


if __name__ == "__main__":
    main()
