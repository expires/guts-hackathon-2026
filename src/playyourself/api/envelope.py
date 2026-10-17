"""One response envelope for every response, including errors."""

import logging
import uuid
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from playyourself.adapters.base import SourceError
from playyourself.domain.models import Snapshot, SourceStatus

log = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict = Field(default_factory=dict)


class Meta(BaseModel):
    request_id: str
    as_of: datetime | None = None
    stale: bool = False
    sources: dict[str, SourceStatus] = Field(default_factory=dict)


class Envelope[T](BaseModel):
    data: T | None = None
    error: ErrorBody | None = None
    meta: Meta


def request_id_of(request: Request) -> str:
    return getattr(request.state, "request_id", None) or str(uuid.uuid4())


def ok[T](data: T, *, request: Request, snapshot: Snapshot | None = None) -> Envelope[T]:
    meta = Meta(request_id=request_id_of(request))
    if snapshot is not None:
        meta.as_of = snapshot.as_of
        meta.stale = snapshot.stale
        meta.sources = dict(snapshot.sources)
    return Envelope[T](data=data, meta=meta)


def error_response(
    request: Request, status: int, code: str, message: str, details: dict | None = None
) -> JSONResponse:
    rid = request_id_of(request)
    body = Envelope[None](
        error=ErrorBody(code=code, message=message, details=details or {}),
        meta=Meta(request_id=rid),
    )
    return JSONResponse(
        body.model_dump(mode="json"), status_code=status, headers={REQUEST_ID_HEADER: rid}
    )


_HTTP_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    422: "invalid_request",
}
_SOURCE_STATUS = {"timeout": 504, "rate_limited": 429, "auth": 502}


def register(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request.state.request_id = str(uuid.uuid4())
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request.state.request_id
        return response

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        code = _HTTP_CODES.get(exc.status_code, "http_error")
        return error_response(request, exc.status_code, code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        errors = [
            {"loc": [str(p) for p in e["loc"]], "msg": e["msg"], "type": e["type"]}
            for e in exc.errors()
        ]
        return error_response(
            request, 422, "validation_error", "Request validation failed", {"errors": errors}
        )

    @app.exception_handler(SourceError)
    async def _source(request: Request, exc: SourceError):
        status = _SOURCE_STATUS.get(exc.code, 502)
        return error_response(
            request,
            status,
            f"source_{exc.code}",
            exc.message or "A data source failed",
            {"retryable": exc.retryable},
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.exception("unhandled error on %s", request.url.path)
        return error_response(request, 500, "internal_error", "Internal server error")
