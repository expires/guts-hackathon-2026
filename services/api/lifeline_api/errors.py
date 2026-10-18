"""One error format everywhere: {"error": {"code", "message", "source"}}."""

from __future__ import annotations

import logging
import math
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from lifeline_contracts.api_models import Error, ErrorBody
from lifeline_data.providers._http import ProviderError

log = logging.getLogger(__name__)

_STATUS_CODES: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    402: "payment_required",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "validation_error",
    429: "rate_limited",
    500: "internal",
    501: "not_implemented",
    503: "unavailable",
}


# ProviderError.code -> (HTTP status, API error code). A provider rejecting OUR stored credentials is
# `provider_auth` (400), never `unauthorized` (401), which means "the app's own bearer token is bad".
PROVIDER_STATUS: dict[str, tuple[int, str]] = {
    "auth": (400, "provider_auth"),
    "rate_limited": (429, "rate_limited"),
    "timeout": (504, "timeout"),
    "unavailable": (502, "unavailable"),
    "bad_data": (502, "bad_data"),
    "not_configured": (503, "not_configured"),
    "offline": (503, "offline"),
    "bad_state": (400, "bad_state"),
    "not_connected": (409, "not_connected"),
}


class ApiError(Exception):
    """Raise from routes. Rendered with the shared error format."""

    def __init__(self, status: int, code: str, message: str, source: str = "api",
                 headers: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.source = source
        self.headers = headers


PROVIDER_NAMES = {"monzo": "Monzo", "trading212": "Trading212"}


def provider_message(code: str, source: str) -> str:
    """Plain English text for a ProviderError code. Never includes anything from the provider's reply."""
    name = PROVIDER_NAMES.get(source, "Your provider")
    return {
        "auth": f"{name} did not accept those details. If you just connected Monzo, open the Monzo app and approve "
        "access, then try again."
        if source == "monzo"
        else f"{name} did not accept those details. Check them and try again.",
        "rate_limited": f"{name} is busy. Try again in a minute.",
        "timeout": f"{name} took too long to answer. Try again.",
        "unavailable": f"{name} is not answering right now. Try again soon.",
        "bad_data": f"{name} sent something we could not read.",
        "not_configured": f"{name} sign-in is not set up on this server.",
        "offline": "Live connections are switched off on this server.",
        "bad_state": "That sign-in link has expired. Start again.",
        "not_connected": f"{name} is not connected.",
    }.get(code, f"{name} could not be reached.")


def provider_error_to_api(exc: ProviderError) -> ApiError:
    """Map a data-layer ProviderError to the shared error format with fixed plain-English copy."""
    status, code = PROVIDER_STATUS.get(exc.code, (502, "unavailable"))
    headers = None
    if status == 429:
        headers = {"Retry-After": str(max(1, math.ceil(exc.retry_after or 30)))}
    return ApiError(status, code, provider_message(exc.code, exc.source), exc.source, headers)


def error_body(code: str, message: str, source: str = "api") -> dict[str, Any]:
    return Error(error=ErrorBody(code=code, message=message, source=source)).model_dump()


def error_response(status: int, code: str, message: str, source: str = "api",
                   headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(status_code=status, content=error_body(code, message, source), headers=headers)


def not_found(what: str = "Not found") -> ApiError:
    return ApiError(404, "not_found", what)


def unauthorized(message: str = "Missing or invalid bearer token") -> ApiError:
    return ApiError(401, "unauthorized", message, headers={"WWW-Authenticate": "Bearer"})


def not_implemented(feature: str) -> ApiError:
    return ApiError(501, "not_implemented", f"{feature} is not available yet")


def _validation_message(exc: RequestValidationError) -> str:
    parts: list[str] = []
    for err in exc.errors()[:5]:
        loc = ".".join(str(p) for p in err.get("loc", ()) if p != "body")
        msg = str(err.get("msg", "invalid"))
        parts.append(f"{loc}: {msg}" if loc else msg)
    return "; ".join(parts) or "Invalid request"


async def _api_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApiError)
    return error_response(exc.status, exc.code, exc.message, exc.source, exc.headers)


async def _provider_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ProviderError)
    api = provider_error_to_api(exc)
    return error_response(api.status, api.code, api.message, api.source, api.headers)


async def _http_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = _STATUS_CODES.get(exc.status_code, "error")
    message = exc.detail if isinstance(exc.detail, str) else code.replace("_", " ")
    headers = dict(exc.headers) if exc.headers else None
    return error_response(exc.status_code, code, message, "api", headers)


async def _validation_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    return error_response(422, "validation_error", _validation_message(exc))


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error_handler)
    app.add_exception_handler(ProviderError, _provider_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)


class CatchAllMiddleware:
    """Outermost app middleware. Turns any unhandled exception into a 500 with code `internal`.

    No stack trace leaves the server. The trace goes to the log only.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            log.exception("unhandled error on %s %s", scope.get("method"), scope.get("path"))
            if started:
                raise
            resp = error_response(500, "internal", "Internal error")
            await resp(scope, receive, send)
