"""DEF181 (security review H4 + N5) — credential leakage into
http_audit, and the audit trail's inability to attribute an action to a
user.

1. `/v1/alpaca/link` and `/v1/alpaca/link_apikey` were missing from
   SCRUB_PATHS — their `api_key`/`api_secret` bodies were persisted
   cleartext for 90 days, bypassing DEF044's encryption-at-rest control.
2. The scrub list is hand-maintained; a NEW route with a secret-shaped
   field but no entry in SCRUB_PATHS would leak exactly the same way.
   `_scrub_secret_fields` is a structural backstop that redacts any JSON
   field whose KEY looks secret-shaped, on every route, list or no list.
3. `_user_id_from_request` claimed to parse the bearer but never did —
   every authenticated action recorded `user_id=NULL`.
4. `?token=` on GET /v1/auth/me is dropped — a bearer in a URL rides
   every proxy/CDN access log with no way to redact it after the fact.
"""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.api.auth import router as auth_router
from app.middleware.http_audit import SCRUB_PATHS, HTTPAuditMiddleware
from app.services.auth_service import AuthService


def _make_app(path: str) -> FastAPI:
    app = FastAPI()

    @app.post(path)
    async def _handler(request: Request) -> JSONResponse:
        return JSONResponse({"ok": True})

    app.add_middleware(HTTPAuditMiddleware)
    return app


def _capture():
    recorded: list[dict] = []

    def _fn(**kwargs: object) -> None:
        recorded.append(dict(kwargs))

    return recorded, _fn


# ── Alpaca link paths are now in SCRUB_PATHS ────────────────────────────


def test_alpaca_link_paths_are_scrubbed():
    assert "/v1/alpaca/link" in SCRUB_PATHS
    assert "/v1/alpaca/link_apikey" in SCRUB_PATHS


def test_alpaca_link_apikey_body_is_redacted():
    app = _make_app("/v1/alpaca/link_apikey")
    recorded, fn = _capture()
    with patch("app.middleware.http_audit.record_http", side_effect=fn):
        client = TestClient(app, raise_server_exceptions=False)
        client.post(
            "/v1/alpaca/link_apikey",
            json={"api_key": "AKIA_SECRET", "api_secret": "shh-dont-tell"},
        )
    assert recorded[0]["request_body"] == b"[REDACTED]"


# ── Structural backstop: secret-shaped fields redacted on ANY route ─────


def test_secret_shaped_field_redacted_on_route_not_in_scrub_list():
    """The whole point: a route that someone FORGOT to add to SCRUB_PATHS
    still doesn't leak a secret-shaped field. Uses a path that is
    deliberately NOT in SCRUB_PATHS."""
    path = "/v1/some/brand/new/route/nobody/added/to/the/list"
    assert path not in SCRUB_PATHS
    app = _make_app(path)
    recorded, fn = _capture()
    with patch("app.middleware.http_audit.record_http", side_effect=fn):
        client = TestClient(app, raise_server_exceptions=False)
        client.post(
            path,
            json={"ticker": "AAPL", "webhook_secret": "wh_abc123", "note": "hi"},
        )
    body = recorded[0]["request_body"]
    assert b"wh_abc123" not in body
    assert b"AAPL" in body  # non-secret fields still recorded (audit stays useful)


def test_non_secret_fields_survive_the_backstop_unredacted():
    path = "/v1/plain/route"
    app = _make_app(path)
    recorded, fn = _capture()
    with patch("app.middleware.http_audit.record_http", side_effect=fn):
        client = TestClient(app, raise_server_exceptions=False)
        client.post(path, json={"ticker": "AAPL", "quantity": 5})
    body = recorded[0]["request_body"]
    assert b"AAPL" in body
    assert b"5" in body


# ── User attribution from the Bearer token ──────────────────────────────


def test_user_id_from_request_parses_bearer_when_no_path_param():
    path = "/v1/no/user/id/in/path"
    app = _make_app(path)
    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)

    recorded, fn = _capture()
    with patch("app.middleware.http_audit.record_http", side_effect=fn):
        client = TestClient(app, raise_server_exceptions=False)
        client.post(path, json={}, headers={"Authorization": f"Bearer {token}"})
    assert recorded[0]["user_id"] == user.id


def test_user_id_from_request_none_without_bearer_or_path_param():
    path = "/v1/anonymous/route"
    app = _make_app(path)
    recorded, fn = _capture()
    with patch("app.middleware.http_audit.record_http", side_effect=fn):
        client = TestClient(app, raise_server_exceptions=False)
        client.post(path, json={})
    assert recorded[0]["user_id"] is None


def test_bearer_wins_over_a_misleading_user_id_path_param():
    """A path param named user_id can name someone OTHER than the caller
    (e.g. /v1/auth/merge/preview/{from_user_id} — the orphan, not the
    caller). The Bearer-derived identity must win."""
    app = FastAPI()

    @app.post("/v1/thing/{user_id}")
    async def _handler(user_id: str, request: Request) -> JSONResponse:
        return JSONResponse({"ok": True})

    app.add_middleware(HTTPAuditMiddleware)

    auth = AuthService()
    caller, token, _ = auth.ensure_anonymous(device_user_id=None)
    someone_else_id = uuid4()

    recorded, fn = _capture()
    with patch("app.middleware.http_audit.record_http", side_effect=fn):
        client = TestClient(app, raise_server_exceptions=False)
        client.post(
            f"/v1/thing/{someone_else_id}",
            json={},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert recorded[0]["user_id"] == caller.id
    assert recorded[0]["user_id"] != someone_else_id


# ── /v1/auth/me: ?token= query variant dropped ──────────────────────────


def test_auth_me_query_token_no_longer_honoured():
    app = FastAPI()
    app.include_router(auth_router)
    client = TestClient(app)
    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)

    # Query-param token must NOT authenticate — 401, not 200.
    r = client.get(f"/v1/auth/me?token={token}")
    assert r.status_code == 401


def test_auth_me_header_bearer_still_works():
    app = FastAPI()
    app.include_router(auth_router)
    client = TestClient(app)
    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)

    r = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["id"] == str(user.id)
