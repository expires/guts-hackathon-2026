"""User-chosen names that other people see (players, circle members, circle names). V6 S5-F2.

Same rules as lifeline_explain.chat.sanitize_untrusted: NFKC, drop control and format characters (zero-width,
bidi overrides, tag characters). Then angle brackets go, whitespace collapses, the result is trimmed and cut.
An empty result is no name at all."""

from __future__ import annotations

import re

from lifeline_explain.chat import sanitize_untrusted

_WS = re.compile(r"\s+")
_MARKUP = str.maketrans("", "", "<>‹›")


def clean_name(raw: str | None, limit: int) -> str | None:
    if raw is None:
        return None
    text = sanitize_untrusted(raw, limit=4 * limit).translate(_MARKUP)
    text = _WS.sub(" ", text).strip()[:limit].strip()
    return text or None
