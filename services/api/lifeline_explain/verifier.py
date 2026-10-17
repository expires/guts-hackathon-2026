"""Number verifier for LLM text.

Rule: every number in the LLM text must match an allowed number. Allowed numbers are:
- engine facts (the `facts` dicts and numeric fields the caller passes in),
- the event year and age,
- numbers that already appear in the deterministic source text (the template text).

Any unmatched number rejects the whole text. The caller then serves the template text.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

_WORDS: dict[str, float] = {
    "zero": 0,
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
# "one" is too common as a pronoun ("no one", "the one"). It counts only inside a ratio ("one in 10").
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
        found.append(Found(m.group(0), a / b, 4, is_ratio=True))
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
            value *= _SCALE[scale_key]
            decimals = 0
        found.append(Found(m.group(0).strip(), value, decimals, is_percent=is_percent))
        spans.append(m.span())

    for m in _WORD_RE.finditer(text):
        if taken(m.start()):
            continue
        word = m.group("word").lower()
        found.append(Found(m.group(0), float(_WORDS[word]), 0))
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
