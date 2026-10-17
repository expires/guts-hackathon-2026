"""Number formatting for user-facing sentences.

Rule (ADR 0016, ADR 0018): every number in a sentence must appear in its `facts`. The helpers
return the rounded value that the text shows, so callers store exactly that value in `facts`.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def money_value(x: float, pence: bool = False) -> float:
    """The value that `gbp` shows."""
    return round(abs(x), 2) if pence else float(round(abs(x)))


def gbp(x: float, pence: bool = False) -> str:
    """'£1,234' or, with pence, '£12.99'. Always the absolute value; the sentence says the direction."""
    v = money_value(x, pence)
    return f"£{v:,.2f}" if pence else f"£{v:,.0f}"


def pct_value(x: float, dp: int = 2) -> float:
    return round(x, dp)


def pct(x: float, dp: int = 2) -> str:
    return f"{pct_value(x, dp):.{dp}f}%"


def numbers_in(text: str) -> list[float]:
    """Every number in `text`, commas removed."""
    out: list[float] = []
    for m in NUMBER_RE.findall(text):
        cleaned = m.replace(",", "")
        if cleaned:
            out.append(float(cleaned))
    return out


def unsupported_numbers(text: str, facts: Mapping[str, float], tol: float = 0.005) -> list[float]:
    """Numbers in `text` that are not a value in `facts` (within `tol`). Empty means the text is clean."""
    values = [abs(v) for v in facts.values()]
    return [n for n in numbers_in(text) if not any(abs(n - v) <= tol for v in values)]


NUMBER_WORDS = frozenset(
    {
        "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
        "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty", "thirty", "forty",
        "fifty", "sixty", "seventy", "eighty", "ninety", "hundred", "thousand", "million", "billion", "trillion",
        "percent", "per", "cent", "pound", "pounds", "pence", "quid", "k", "m", "bn",
    }
)
_NAME_STRIP = re.compile(r"[0-9%£$€.,+\-/:]+")


def clean_name(name: str, fallback: str = "this payee") -> str:
    """Display name for an UNTRUSTED payee name (merchant, bill or subscription name) before it goes into any
    engine text (ADR 0034, V6 T2-F1). Removes digits, %, currency signs and number words, collapses whitespace.
    A name that is empty after cleaning becomes `fallback`."""
    words = [w for w in _NAME_STRIP.sub(" ", name).split() if w.lower() not in NUMBER_WORDS]
    out = " ".join(words)[:60].strip()
    return out or fallback


def digit_facts(name: str, prefix: str = "name") -> dict[str, float]:
    """Facts for numbers inside a proper name (e.g. 'Microsoft 365'), so the name can appear in text."""
    return {f"{prefix}_{i}": n for i, n in enumerate(numbers_in(name))}
