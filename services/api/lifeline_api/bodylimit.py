"""Reject request bodies above the limit (64 KB by default) with 413 in the shared error format."""

from __future__ import annotations

import contextlib

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from lifeline_api.errors import error_response


class _TooLarge(Exception):
    pass


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int, path_limits: dict[str, int] | None = None) -> None:
        """`path_limits` gives exact paths their own limit (e.g. statement uploads)."""
        self.app = app
        self.default_max = max_bytes
        self.path_limits = dict(path_limits or {})

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        max_bytes = self.path_limits.get(scope.get("path", ""), self.default_max)
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    too_big = int(value) > max_bytes
                except ValueError:
                    too_big = True
                if too_big:
                    await self._reject(scope, receive, send, max_bytes)
                    return

        seen = 0
        overflow = False

        async def counted_receive() -> Message:
            nonlocal seen, overflow
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > max_bytes:
                    overflow = True
                    raise _TooLarge
            return message

        async def guarded_send(message: Message) -> None:
            # After an overflow, drop whatever the app sends (FastAPI turns the read error into a 400).
            if not overflow:
                await send(message)

        with contextlib.suppress(_TooLarge):
            await self.app(scope, counted_receive, guarded_send)
        if overflow:
            await self._reject(scope, receive, send, max_bytes)

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send, max_bytes: int) -> None:
        resp = error_response(413, "payload_too_large", f"Request body is larger than {max_bytes} bytes")
        await resp(scope, receive, send)
