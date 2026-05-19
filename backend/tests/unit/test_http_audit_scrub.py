"""Tests for http_audit middleware body scrubbing (adversarial audit B4).

Auth routes that issue or accept credentials should have request + response
bodies replaced with [REDACTED] in the http_audit table. Non-auth routes
should still record normal bodies.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.middleware.http_audit import SCRUB_PATHS, HTTPAuditMiddleware


def _make_app(path: str) -> FastAPI:
    app = FastAPI()

    @app.post(path)
    async def _handler(request: Request) -> JSONResponse:
        return JSONResponse({"ok": True, "secret": "token-abc"})

    app.add_middleware(HTTPAuditMiddleware)
    return app


@pytest.mark.parametrize("scrub_path", sorted(SCRUB_PATHS))
def test_scrub_paths_redact_bodies(scrub_path: str) -> None:
    app = _make_app(scrub_path)
    recorded: list[dict] = []

    def _capture(**kwargs: object) -> None:
        recorded.append(dict(kwargs))

    with patch("app.middleware.http_audit.record_http", side_effect=_capture):
        client = TestClient(app, raise_server_exceptions=False)
        client.post(scrub_path, json={"identity_token": "secret-jwt", "password": "hunter2"})

    assert len(recorded) == 1
    assert recorded[0]["request_body"] == b"[REDACTED]"
    assert recorded[0]["response_body"] == b"[REDACTED]"


def test_non_scrub_path_records_body() -> None:
    app = _make_app("/v1/some/other/route")
    recorded: list[dict] = []

    def _capture(**kwargs: object) -> None:
        recorded.append(dict(kwargs))

    with patch("app.middleware.http_audit.record_http", side_effect=_capture):
        client = TestClient(app, raise_server_exceptions=False)
        client.post("/v1/some/other/route", json={"ticker": "AAPL"})

    assert len(recorded) == 1
    assert recorded[0]["request_body"] != b"[REDACTED]"
    assert b"AAPL" in recorded[0]["request_body"]
    assert recorded[0]["response_body"] != b"[REDACTED]"


def test_skip_path_not_recorded() -> None:
    app = _make_app("/v1/health")

    @app.get("/v1/health")
    async def _health() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    recorded: list[dict] = []

    def _capture(**kwargs: object) -> None:
        recorded.append(dict(kwargs))

    with patch("app.middleware.http_audit.record_http", side_effect=_capture):
        client = TestClient(app, raise_server_exceptions=False)
        client.get("/v1/health")

    assert len(recorded) == 0
