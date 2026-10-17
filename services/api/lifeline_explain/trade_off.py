"""Trade-off facts for Ask Penny (ADR 0042).

The engine (W2) writes each move's trade-off. Penny only rephrases it. This module:
- finds `trade_off` objects inside a next_move or test_move tool result,
- turns every number in their points into a ChatFact with id `tf_<move_id>_<key>`, so the verifier accepts
  those numbers when Penny quotes them,
- adds a move's `trade_off` to a tool result when the engine tool did not put it there.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import ValidationError

from lifeline_contracts.chat import ChatFact
from lifeline_contracts.domain import SourceRef
from lifeline_contracts.next_move import Move, TradeOff
from lifeline_explain.chat_tools import source_key
from lifeline_explain.verifier import extract_numbers, number_matches

log = logging.getLogger(__name__)

TRADE_OFF_TOOLS = frozenset({"next_move", "test_move"})

Unit = Literal["gbp", "gbp_per_month", "gbp_per_year", "percent", "months", "years", "count", "date_year"]

_ID_SAFE = re.compile(r"[^A-Za-z0-9_\-]")
# Written unit in the point text -> fact unit.
_KIND_UNIT: dict[str, Unit] = {
    "gbp": "gbp",
    "percent": "percent",
    "days": "count",
    "weeks": "count",
    "months": "months",
    "years": "years",
}


def fact_id(move_id: str, key: str) -> str:
    return f"tf_{_ID_SAFE.sub('_', move_id)}_{_ID_SAFE.sub('_', key)}"


def _unit_from_key(key: str) -> Unit:
    k = key.lower()
    if "pct" in k or "percent" in k or "rate" in k:
        return "percent"
    if "months" in k:
        return "months"
    if "years" in k:
        return "years"
    if "days" in k or "weeks" in k or "count" in k:
        return "count"
    return "gbp"


def unit_for(key: str, value: float, text: str) -> Unit:
    """Unit of a trade-off fact. The written form of the same number in the point text wins; else the key."""
    by_key = _unit_from_key(key)
    for found in extract_numbers(text):
        if found.is_ratio or not number_matches(found, [value]):
            continue
        if found.kind in _KIND_UNIT:
            return _KIND_UNIT[found.kind]
        if float(value).is_integer() and 1900 <= value <= 2100:
            return "date_year"
        return by_key if by_key in {"months", "years"} else "count"
    return by_key


def trade_off_facts(move_id: str, trade_off: TradeOff, label: str | None = None) -> list[ChatFact]:
    """One ChatFact per number in the trade-off points. Ids are stable for the same move and key."""
    out: list[ChatFact] = []
    seen: set[str] = set()
    for point in trade_off.points:
        sid = source_key(point.source) if point.source is not None else None
        for key, value in point.facts.items():
            fid = fact_id(move_id, key)
            if fid in seen:
                continue
            seen.add(fid)
            name = f"{label}: " if label else ""
            out.append(
                ChatFact(
                    id=fid,
                    value=value,
                    unit=unit_for(key, value, point.text),
                    label=f"What you give up, {name}{key.replace('_', ' ')}"[:120],
                    source_id=sid,
                )
            )
    return out


def trade_off_sources(trade_off: TradeOff) -> list[SourceRef]:
    return [p.source for p in trade_off.points if p.source is not None]


def find_trade_offs(result: Any) -> list[tuple[str, TradeOff]]:
    """(move id, TradeOff) for every `trade_off` object in a tool result.

    The move id comes from the same object's `id` or `move_id`. An invalid trade-off is skipped (logged)."""
    found: list[tuple[str, TradeOff]] = []

    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            raw = value.get("trade_off")
            mid = value.get("id") or value.get("move_id")
            if isinstance(raw, Mapping) and isinstance(mid, str) and mid:
                try:
                    found.append((mid, TradeOff.model_validate(raw)))
                except ValidationError:
                    log.info("penny: skipped an invalid trade_off for move %s", mid[:40])
            for k, v in value.items():
                if k != "trade_off":
                    walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)

    walk(result)
    return found


def attach_trade_offs(result: Any, moves: Mapping[str, Move]) -> Any:
    """Add `trade_off` (contract shape) to each move object in a next_move or test_move result that lacks it.

    next_move: objects with `id` under `top` and `runners_up`. test_move: the top-level object with `move_id`.
    Mutates and returns `result`."""

    def add(obj: Any, mid: Any) -> None:
        if not isinstance(obj, dict) or not isinstance(mid, str) or obj.get("trade_off") is not None:
            return
        mv = moves.get(mid)
        if mv is not None and mv.trade_off is not None:
            obj["trade_off"] = mv.trade_off.model_dump(mode="json")

    if isinstance(result, dict):
        top = result.get("top")
        if isinstance(top, dict):
            add(top, top.get("id"))
        for r in result.get("runners_up") or []:
            if isinstance(r, dict):
                add(r, r.get("id"))
        if "move_id" in result:
            add(result, result.get("move_id"))
    return result
