"""Number verifier for LLM text.

Rule: every number in the LLM text must match an allowed number. Allowed numbers are:
- engine facts (the `facts` dicts and numeric fields the caller passes in),
- the event year and age,
- numbers that already appear in the deterministic source text (the template text).

Any unmatched number rejects the whole text. The caller then serves the template text.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass

_WORDS: dict[str, float] = {
    "zero": 0,
    "nil": 0,
    "nought": 0,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
    "hundred": 100,
    "thousand": 1000,
    "million": 1_000_000,
    "billion": 1_000_000_000,
    "dozen": 12,
    "twice": 2,
    "double": 2,
    "triple": 3,
    "half": 0.5,
    "quarter": 0.25,
}
# "one" is too common as a pronoun ("no one", "the one"). It counts inside a ratio ("one in 10") or before a
# unit word ("one percent", "one year"). "none" counts before a unit word ("none percent").
_RATIO_WORDS = {**_WORDS, "one": 1}

_NUM = r"\d[\d,]*(?:\.\d+)?|\.\d+"
_WORD_ALT = "|".join(sorted(_RATIO_WORDS, key=len, reverse=True))
_TOKEN = rf"(?:{_NUM}|\b(?:{_WORD_ALT})\b)"

_RATIO_RE = re.compile(rf"(?P<a>{_TOKEN})\s+(?:in|out\s+of)\s+(?:every\s+)?(?P<b>{_TOKEN})", re.IGNORECASE)
_NUMBER_RE = re.compile(
    rf"(?P<num>{_NUM})\s*(?P<suffix>k\b|m\b|bn\b|%|\s*per\s*cent\b|\s*percent\b|\s*million\b|\s*billion\b"
    rf"|\s*thousand\b)?",
    re.IGNORECASE,
)
_UNIT_WORD = r"(?:per\s*cent|percent|pounds?|quid|years?|months?|weeks?|days?)"
_ONE_RE = re.compile(rf"\b(?P<word>one|none)\s+(?={_UNIT_WORD}\b)", re.IGNORECASE)
_AFTER_RE = re.compile(r"^\s*(?P<u>per\s*cent|percent|pounds?|quid|gbp|days?|weeks?|months?|years?)\b", re.IGNORECASE)
_WORD_RE = re.compile(rf"\b(?P<word>{'|'.join(sorted(_WORDS, key=len, reverse=True))})\b", re.IGNORECASE)

_SCALE = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "bn": 1e9, "billion": 1e9}

REL_TOLERANCE = 0.005


@dataclass(frozen=True)
class Found:
    """One number found in text. `decimals` is the written precision; `is_ratio` marks 'X in Y'."""

    raw: str
    value: float
    decimals: int
    is_percent: bool = False
    is_ratio: bool = False
    start: int = 0
    end: int = 0
    kind: str | None = None  # written unit: percent, gbp, days, weeks, months, years, or None


def _kind(text: str, start: int, end: int, is_percent: bool) -> str | None:
    if is_percent:
        return "percent"
    before = text[:start].rstrip(" -\u2212")
    if before.endswith("\u00a3") or before[-3:].lower() == "gbp":  # V6 V2-F4: "GBP 138" is money
        return "gbp"
    m = _AFTER_RE.match(text[end:])
    if not m:
        return None
    u = m.group("u").lower().replace(" ", "")
    if u in {"percent"}:
        return "percent"
    if u.startswith(("pound", "quid", "gbp")):
        return "gbp"
    return u if u.endswith("s") else u + "s"


def _token_value(tok: str) -> tuple[float, int]:
    low = tok.lower()
    if low in _RATIO_WORDS:
        return float(_RATIO_WORDS[low]), 0
    clean = tok.replace(",", "")
    decimals = len(clean.split(".")[1]) if "." in clean else 0
    return float(clean), decimals


def extract_numbers(text: str) -> list[Found]:
    """Return every number in `text`. Ratios ('7 in 10') are one item with value a/b."""
    found: list[Found] = []
    spans: list[tuple[int, int]] = []

    for m in _RATIO_RE.finditer(text):
        a, _ = _token_value(m.group("a"))
        b, _ = _token_value(m.group("b"))
        if not (0 < b <= 1000 and a <= b):
            continue  # not a ratio ("born 1990 in 2022"): numbers are checked one by one below
        found.append(Found(m.group(0), a / b, 4, is_ratio=True, start=m.start(), end=m.end(), kind="ratio"))
        spans.append(m.span())

    def taken(pos: int) -> bool:
        return any(s <= pos < e for s, e in spans)

    for m in _NUMBER_RE.finditer(text):
        if taken(m.start()):
            continue
        value, decimals = _token_value(m.group("num"))
        suffix = (m.group("suffix") or "").strip().lower()
        is_percent = suffix in {"%", "per cent", "percent"} or suffix.replace(" ", "") == "percent"
        scale_key = suffix.replace(" ", "")
        if scale_key in _SCALE:
            # "£0.1k" is written to the nearest 100: precision moves with the scale (V6 V2-F4).
            value *= _SCALE[scale_key]
            decimals -= round(math.log10(_SCALE[scale_key]))
        raw = m.group(0).rstrip()
        end = m.start() + len(raw)
        kind = _kind(text, m.start(), end, is_percent)
        found.append(Found(raw, value, decimals, is_percent=kind == "percent", start=m.start(), end=end, kind=kind))
        spans.append(m.span())

    for m in _WORD_RE.finditer(text):
        if taken(m.start()):
            continue
        word = m.group("word").lower()
        kind = _kind(text, m.start(), m.end(), False)
        found.append(Found(m.group(0), float(_WORDS[word]), 0, kind == "percent", start=m.start(), end=m.end(),
                           kind=kind))  # fmt: skip
        spans.append(m.span())

    for m in _ONE_RE.finditer(text):
        if taken(m.start()):
            continue
        value = 1.0 if m.group("word").lower() == "one" else 0.0
        kind = _kind(text, m.start(), m.start() + len(m.group("word")), False)
        found.append(Found(m.group("word"), value, 0, kind == "percent", start=m.start(),
                           end=m.start() + len(m.group("word")), kind=kind))  # fmt: skip
    found.sort(key=lambda f: f.start)
    return found


def _close(value: float, target: float, decimals: int) -> bool:
    v, t = abs(value), abs(target)
    if v == t:
        return True
    if round(t, decimals) == v:
        return True
    return t != 0 and abs(v - t) <= REL_TOLERANCE * t


def number_matches(f: Found, allowed: Iterable[float]) -> bool:
    """True when `f` equals an allowed number after rounding to its written precision (or within 0.5%)."""
    allowed_list = [abs(a) for a in allowed]
    if f.is_ratio:
        # '7 in 10' matches a share of 0.7 (or 0.68 rounded) or a percent of 70.
        share = round(f.value, 1)
        return any(
            (a <= 1 and round(a, 1) == share) or (1 < a <= 100 and round(a / 100, 1) == share) for a in allowed_list
        )
    cands = [(f.value, f.decimals)]
    if f.is_percent:
        # Facts may store a percent as 4.1 or as 0.041.
        cands.append((f.value / 100, f.decimals + 2))
    return any(_close(v, a, d) for v, d in cands for a in allowed_list)


# Which written units may stand for a fact of each unit (chat facts carry units; ADR 0031, V6 T2-F6).
_UNIT_OK: dict[str, frozenset[str | None]] = {
    "gbp": frozenset({"gbp"}),
    "gbp_per_month": frozenset({"gbp"}),
    "gbp_per_year": frozenset({"gbp"}),
    "percent": frozenset({"percent", "ratio"}),
    "months": frozenset({None, "months"}),
    "years": frozenset({None, "years"}),
    "count": frozenset({None, "days", "weeks", "months", "years"}),
    "date_year": frozenset({None}),
}


def fact_matches(f: Found, value: float, unit: str) -> bool:
    """Unit-aware match: '165 days' never verifies '165%', percent facts need percent text, money needs £."""
    if f.kind not in _UNIT_OK.get(unit, frozenset({None})):
        return False
    if f.is_ratio:
        return 0 <= value <= 100 and round(abs(value) / 100, 1) == round(f.value, 1)
    return _close(f.value, value, f.decimals)


@dataclass(frozen=True)
class Verdict:
    ok: bool
    unmatched: tuple[str, ...] = ()


def allowed_numbers(
    facts: dict[str, float] | Iterable[float],
    source_text: str = "",
    year: int | None = None,
    age: int | None = None,
) -> list[float]:
    vals = list(facts.values()) if isinstance(facts, dict) else list(facts)
    vals += [f.value for f in extract_numbers(source_text)]
    if year is not None:
        vals.append(float(year))
    if age is not None:
        vals.append(float(age))
    return vals


def verify(
    text: str,
    facts: dict[str, float] | Iterable[float],
    source_text: str = "",
    year: int | None = None,
    age: int | None = None,
) -> Verdict:
    """Check every number in `text` against facts, the source text, year and age."""
    allowed = allowed_numbers(facts, source_text, year, age)
    bad = tuple(f.raw for f in extract_numbers(text) if not number_matches(f, allowed))
    return Verdict(ok=not bad, unmatched=bad)
