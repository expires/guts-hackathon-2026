from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from playyourself.adapters.base import SourceError
from playyourself.api import envelope
from playyourself.api.envelope import Envelope, ok


class Item(BaseModel):
    n: int


def make_client() -> TestClient:
    app = FastAPI()
    envelope.register(app)

    @app.get("/ok", response_model=Envelope[Item])
    def _ok(request: envelope.Request):
        return ok(Item(n=1), request=request)

    @app.get("/http")
    def _http():
        raise HTTPException(404, "nope")

    @app.get("/val")
    def _val(n: int):
        return n

    @app.get("/source")
    def _source():
        raise SourceError("timeout", "slow", retryable=True)

    @app.get("/boom")
    def _boom():
        raise RuntimeError("secret internal detail")

    return TestClient(app, raise_server_exceptions=False)


def check_shape(r, status, code):
    assert r.status_code == status
    body = r.json()
    assert set(body) == {"data", "error", "meta"}
    assert body["data"] is None
    assert body["error"]["code"] == code
    assert body["meta"]["request_id"] == r.headers["X-Request-ID"]
    return body


def test_success_shape():
    r = make_client().get("/ok")
    body = r.json()
    assert r.status_code == 200
    assert body["data"] == {"n": 1} and body["error"] is None
    assert body["meta"]["request_id"] == r.headers["X-Request-ID"]
    assert body["meta"]["stale"] is False


def test_404():
    body = check_shape(make_client().get("/missing"), 404, "not_found")
    assert body["error"]["message"]


def test_http_exception():
    check_shape(make_client().get("/http"), 404, "not_found")


def test_validation_error():
    body = check_shape(make_client().get("/val?n=abc"), 422, "validation_error")
    assert body["error"]["details"]["errors"][0]["loc"] == ["query", "n"]


def test_source_error():
    body = check_shape(make_client().get("/source"), 504, "source_timeout")
    assert body["error"]["details"] == {"retryable": True}


def test_unhandled_exception_does_not_leak():
    r = make_client().get("/boom")
    body = check_shape(r, 500, "internal_error")
    assert "secret" not in r.text
    assert body["error"]["message"] == "Internal server error"


def test_request_ids_unique():
    c = make_client()
    assert c.get("/ok").headers["X-Request-ID"] != c.get("/ok").headers["X-Request-ID"]
