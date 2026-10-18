"""Portfolio description and illustrative history for Penny. Pure: no I/O, no clock, no RNG.

Describes the mix the user already holds (shares of the investments, by asset class and region, how concentrated)
and replays that mix, and a few reference mixes, through named past periods of a monthly returns series.
It never says what to buy, sell or hold. History is illustrative and not a forecast.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from lifeline_contracts.accounts import Holding

HISTORY_LABEL = "Illustrative past returns, not a forecast"
MAX_HOLDINGS = 25
# Series columns (the fixture's assets).
ASSETS: tuple[str, ...] = ("global_equity", "uk_equity", "gilts", "cash")

ASSET_LABELS: dict[str, str] = {
    "equity": "shares", "bond": "bonds", "cash": "cash", "property": "property", "commodity": "commodities",
    "other": "other",
}  # fmt: skip


@dataclass(frozen=True)
class HoldingShare:
    name: str
    value: float
    share_pct: float


@dataclass(frozen=True)
class Description:
    total: float
    count: int
    holdings: tuple[HoldingShare, ...]  # largest first, at most MAX_HOLDINGS
    by_class: tuple[tuple[str, float], ...]  # (asset class, % of investments), largest first
    by_region: tuple[tuple[str, float], ...]
    top1_pct: float
    top3_pct: float | None  # None below 3 holdings
    note: str


def describe(holdings: Sequence[Holding]) -> Description | None:
    """Mix and concentration of the positions. None when nothing is held."""
    held = sorted((h for h in holdings if h.value > 0), key=lambda h: (-h.value, h.instrument_id))
    total = sum(h.value for h in held)
    if total <= 0:
        return None

    def pct(v: float) -> float:
        return round(v / total * 100, 1)

    classes: dict[str, float] = {}
    regions: dict[str, float] = {}
    for h in held:
        classes[h.asset_class] = classes.get(h.asset_class, 0.0) + h.value
        region = (h.region or "Unknown").strip() or "Unknown"
        regions[region] = regions.get(region, 0.0) + h.value
    top1 = pct(held[0].value)
    top3 = pct(sum(h.value for h in held[:3])) if len(held) >= 3 else None
    note = f"Your biggest holding is {top1:g}% of your investments"
    if top3 is not None:
        note += f". Your top 3 holdings make up {top3:g}%"
    elif len(held) == 1:
        note = "You hold one investment, so all of it rides on that one"
    return Description(
        total=round(total, 2),
        count=len(held),
        holdings=tuple(HoldingShare(h.name[:60], round(h.value, 2), pct(h.value)) for h in held[:MAX_HOLDINGS]),
        by_class=tuple((c, pct(v)) for c, v in sorted(classes.items(), key=lambda kv: (-kv[1], kv[0]))),
        by_region=tuple((r, pct(v)) for r, v in sorted(regions.items(), key=lambda kv: (-kv[1], kv[0]))),
        top1_pct=top1,
        top3_pct=top3,
        note=note,
    )


# ---------- history ----------

PERIODS: dict[str, tuple[str, str]] = {  # inclusive month bounds
    "gfc_2008": ("2007-10", "2012-12"),
    "covid_2020": ("2020-01", "2021-12"),
    "rates_2022": ("2021-12", "2024-06"),
}
PERIOD_LABELS: dict[str, str] = {
    "gfc_2008": "the 2008 financial crisis",
    "covid_2020": "the 2020 Covid crash",
    "rates_2022": "the 2022 rate rises",
}
PERIOD_YEARS: dict[str, int] = {"gfc_2008": 2008, "covid_2020": 2020, "rates_2022": 2022}
REFERENCE_MIXES: dict[str, tuple[str, dict[str, float]]] = {
    "all_shares": ("All shares", {"equity": 1.0}),
    "shares_80_bonds_20": ("80/20 shares and bonds", {"equity": 0.8, "bond": 0.2}),
    "shares_60_bonds_40": ("60/40 shares and bonds", {"equity": 0.6, "bond": 0.4}),
}
_ASSET_MAP = {"equity": "global_equity", "bond": "gilts", "cash": "cash"}
_UK = frozenset({"UK", "GB", "UNITED KINGDOM"})


@dataclass(frozen=True)
class ReturnSeries:
    months: tuple[str, ...]  # "YYYY-MM"
    assets: tuple[str, ...]
    returns: tuple[tuple[float, ...], ...]  # [month][asset], monthly returns as fractions
    label: str = HISTORY_LABEL


@dataclass(frozen=True)
class MixResult:
    key: str
    label: str
    biggest_drop_pct: float
    recovery_months: int | None  # months from the lowest point back to the old high; None if not within the period
    end_change_pct: float  # change over the whole period


@dataclass(frozen=True)
class PeriodResult:
    key: str
    label: str
    year: int
    start: str
    end: str
    mixes: tuple[MixResult, ...]  # yours first, then the reference mixes


def weights_from_holdings(holdings: Sequence[Holding]) -> dict[str, float] | None:
    """Current mix on the series' assets, summing to 1. UK equity maps to uk_equity, other shares and anything not
    shares, bonds or cash to global_equity. None when nothing is held."""
    total = sum(h.value for h in holdings if h.value > 0)
    if total <= 0:
        return None
    out: dict[str, float] = {}
    for h in holdings:
        if h.value <= 0:
            continue
        if h.asset_class == "equity" and (h.region or "").upper() in _UK:
            asset = "uk_equity"
        else:
            asset = _ASSET_MAP.get(h.asset_class, "global_equity")
        out[asset] = out.get(asset, 0.0) + h.value / total
    return out


def _reference_weights(spec: dict[str, float]) -> dict[str, float]:
    return {_ASSET_MAP[k]: v for k, v in spec.items()}


def _index(rs: ReturnSeries, i0: int, i1: int, weights: dict[str, float]) -> list[float]:
    """Monthly rebalanced index from 100 over months i0..i1 inclusive."""
    cols = {a: rs.assets.index(a) for a in weights if a in rs.assets}
    out = [100.0]
    for t in range(i0, i1 + 1):
        r = sum(w * rs.returns[t][cols[a]] for a, w in weights.items() if a in cols)
        out.append(out[-1] * (1.0 + r))
    return out


def drop_and_recovery(index: Sequence[float]) -> tuple[float, int | None]:
    """(biggest fall from a high as a % , months from the lowest point back to that high or None)."""
    peak = index[0]
    peak_at_trough = peak
    worst = 0.0
    trough = 0
    for i, x in enumerate(index):
        if x > peak:
            peak = x
        dd = 1.0 - x / peak
        if dd > worst:
            worst, trough, peak_at_trough = dd, i, peak
    if worst <= 0:
        return 0.0, 0
    for j in range(trough, len(index)):
        if index[j] >= peak_at_trough:
            return round(worst * 100, 1), j - trough
    return round(worst * 100, 1), None


def mix_history(holdings: Sequence[Holding], rs: ReturnSeries) -> tuple[PeriodResult, ...]:
    """Your current mix against the reference mixes in each named period. Empty when nothing is held."""
    mine = weights_from_holdings(holdings)
    if mine is None:
        return ()
    mixes: list[tuple[str, str, dict[str, float]]] = [("yours", "Your mix today", mine)]
    mixes += [(k, label, _reference_weights(spec)) for k, (label, spec) in REFERENCE_MIXES.items()]
    out: list[PeriodResult] = []
    for key, (start, end) in PERIODS.items():
        if start not in rs.months or end not in rs.months:
            continue
        i0, i1 = rs.months.index(start), rs.months.index(end)
        if i1 < i0:
            continue
        results = []
        for mk, label, w in mixes:
            idx = _index(rs, i0, i1, w)
            drop, rec = drop_and_recovery(idx)
            results.append(MixResult(mk, label, drop, rec, round((idx[-1] / idx[0] - 1) * 100, 1)))
        out.append(PeriodResult(key, PERIOD_LABELS[key], PERIOD_YEARS[key], start, end, tuple(results)))
    return tuple(out)
