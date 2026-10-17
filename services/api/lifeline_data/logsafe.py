"""Keep API keys out of logs.

Some sources (Adzuna) take keys as URL query parameters. httpx logs every request URL at INFO.
- `quiet_http_loggers()` sets the `httpx` and `httpcore` loggers to WARNING and adds a filter that
  strips query strings from anything they still log.
- `redact_urls(text)` removes the query string from every URL in a text. Adapter errors pass through it
  before they reach a log line or `SourceStatus.last_error`.
"""

from __future__ import annotations

import logging
import re

_URL_QUERY = re.compile(r"(https?://[^\s?#'\"<>]+)\?[^\s#'\"<>)]*")
_HTTP_LOGGERS = ("httpx", "httpcore")


def redact_urls(text: str) -> str:
    """Replace '?query' after every http(s) URL with '?<redacted>'."""
    return _URL_QUERY.sub(r"\1?<redacted>", text)


class RedactQueryFilter(logging.Filter):
    """Rewrite a record's message with URL query strings removed."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # a bad format string must not break logging
            return True
        clean = redact_urls(message)
        if clean != message:
            record.msg, record.args = clean, None
        return True


_FILTER = RedactQueryFilter()


def quiet_http_loggers() -> None:
    """Idempotent. Call at import of the data layer and again after any logging.basicConfig()."""
    for name in _HTTP_LOGGERS:
        logger = logging.getLogger(name)
        if logger.level == logging.NOTSET or logger.level < logging.WARNING:
            logger.setLevel(logging.WARNING)
        if _FILTER not in logger.filters:
            logger.addFilter(_FILTER)
