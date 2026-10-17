"""Occupation profiles from `config/occupations.toml`. No occupation branches in code."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Any


@dataclass(frozen=True)
class Occupation:
    name: str
    bonus_share: float
    bonus_stock_beta: float
    bonus_cap: float
    redundancy_mult: float
    redundancy_stock: float
    public_sector: bool

    def bonus_rate(self, stock_return_pct: float) -> float:
        """Bonus as a share of base pay for a year with this stock market return."""
        if self.bonus_cap <= 0:
            return 0.0
        return max(0.0, min(self.bonus_cap, self.bonus_share + self.bonus_stock_beta * stock_return_pct))


@lru_cache(maxsize=1)
def _config() -> dict[str, Any]:
    raw = resources.files("lifeline_sim.config").joinpath("occupations.toml").read_text(encoding="utf-8")
    return tomllib.loads(raw)


def _make(name: str, row: dict[str, Any], base: dict[str, Any]) -> Occupation:
    merged = {**base, **row}
    return Occupation(
        name=name,
        bonus_share=float(merged["bonus_share"]),
        bonus_stock_beta=float(merged["bonus_stock_beta"]),
        bonus_cap=float(merged["bonus_cap"]),
        redundancy_mult=float(merged["redundancy_mult"]),
        redundancy_stock=float(merged["redundancy_stock"]),
        public_sector=bool(merged["public_sector"]),
    )


@lru_cache(maxsize=256)
def occupation(title: str) -> Occupation:
    cfg = _config()
    base = cfg["default"]
    profiles = {k: v for k, v in cfg.items() if k not in ("default", "public_pay_cap")}
    key = title.strip().lower()
    if key in profiles:
        return _make(key, profiles[key], base)
    for name, row in profiles.items():
        if key in [str(a) for a in row.get("aliases", [])]:
            return _make(name, row, base)
    for name, row in sorted(profiles.items(), key=lambda kv: -len(kv[0])):
        if name in key:
            return _make(name, row, base)
    return _make("default", {}, base)


def public_pay_cap(year: int) -> float | None:
    """Public sector pay growth cap in percent for the year, or None."""
    caps: dict[str, Any] = _config().get("public_pay_cap", {})
    v = caps.get(str(year))
    return None if v is None else float(v)
