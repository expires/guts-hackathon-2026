"""Keep bearer tokens out of logs. The room WebSocket carries the token in the query (`?token=`), and
uvicorn logs the full path of every request and WebSocket handshake."""

from __future__ import annotations

import logging
import re

_TOKEN = re.compile(r"(token=)[^&\s\"']+")


class RedactTokens(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            return True
        if "token=" in message:
            record.msg = _TOKEN.sub(r"\1[redacted]", message)
            record.args = ()
        return True


def install() -> None:
    for name in ("uvicorn.access", "uvicorn.error", "uvicorn"):
        logger = logging.getLogger(name)
        if not any(isinstance(f, RedactTokens) for f in logger.filters):
            logger.addFilter(RedactTokens())
