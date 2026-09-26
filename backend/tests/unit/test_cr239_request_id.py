"""CR239 Leg A — every response, and every error body, carries a request id.

`HTTPAuditMiddleware` mints one UUID per request (the SAME value that becomes
`http_audit.id`, not a second number) and echoes it on `X-Request-Id`; the
global exception handlers in `app.main` put the same value in the JSON body's
`request_id` field so a client that only inspects the parsed body still gets
it. This file pins both halves plus the one-value guarantee across success,
`HTTPException`, and an unhandled exception.
"""

from __future__ import annotations

from unittest.mock import patch
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from app.main import (
    _http_exception_with_request_id,
    _unhandled_exception_with_request_id,
)
from app.middleware.http_audit import HTTPAuditMiddleware


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(HTTPException, _http_exception_with_request_id)
    app.add_exception_handler(Exception, _unhandled_exception_with_request_id)

    @app.get("/ok")
    async def _ok() -> JSONResponse:
        return JSONResponse({"ok": True})

    @app.get("/rejected")
    async def _rejected() -> JSONResponse:
        raise HTTPException(status_code=409, detail="that request wasn't accepted")

    @app.get("/boom")
    async def _boom() -> JSONResponse:
        raise RuntimeError("unhandled")

    app.add_middleware(HTTPAuditMiddleware)
    return app


def _client() -> TestClient:
    # raise_server_exceptions=False: TestClient's default re-raises a 500
    # instead of letting the app's own exception handler answer it — this
    # suite is pinning that handler's behaviour, so it must run.
    return TestClient(_make_app(), raise_server_exceptions=False)


def test_a_healthy_response_carries_the_header() -> None:
    with patch("app.middleware.http_audit.record_http"):
        r = _client().get("/ok")
    assert r.status_code == 200
    request_id = r.headers.get("x-request-id")
    assert request_id is not None
    UUID(request_id)  # well-formed


def test_a_rejected_request_carries_the_same_id_in_header_and_body() -> None:
    with patch("app.middleware.http_audit.record_http"):
        r = _client().get("/rejected")
    assert r.status_code == 409
    header_id = r.headers.get("x-request-id")
    body = r.json()
    assert header_id is not None
    assert body["request_id"] == header_id
    assert body["detail"] == "that request wasn't accepted"


def test_an_unhandled_exception_still_carries_a_request_id() -> None:
    with patch("app.middleware.http_audit.record_http"):
        r = _client().get("/boom")
    assert r.status_code == 500
    header_id = r.headers.get("x-request-id")
    body = r.json()
    assert header_id is not None
    assert body["request_id"] == header_id


def test_the_persisted_http_audit_row_id_is_the_same_value_the_client_saw() -> None:
    """Not a second number: `http_audit.id` IS the trace id echoed on the
    response, so a support session can look up the exact row by the id the
    user reads off their screen."""
    recorded: list[dict] = []

    def _capture(**kwargs: object) -> None:
        recorded.append(dict(kwargs))

    with patch("app.middleware.http_audit.record_http", side_effect=_capture):
        r = _client().get("/rejected")

    assert len(recorded) == 1
    header_id = r.headers.get("x-request-id")
    assert str(recorded[0]["request_id"]) == header_id


def test_two_requests_get_two_different_ids() -> None:
    with patch("app.middleware.http_audit.record_http"):
        client = _client()
        r1 = client.get("/ok")
        r2 = client.get("/ok")
    assert r1.headers["x-request-id"] != r2.headers["x-request-id"]
