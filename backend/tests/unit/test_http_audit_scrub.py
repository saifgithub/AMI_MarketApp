"""Tests for http_audit middleware body scrubbing (adversarial audit B4).

Auth routes that issue or accept credentials should have request + response
bodies replaced with [REDACTED] in the http_audit table. Non-auth routes
should still record normal bodies.

DEF430 MAJOR-1 adds a second class of test below: the DEF419 mandate-preview
snapshot (`account` on `/v1/sim/preview`) is personal financial data, not a
secret, so it doesn't go through SCRUB_PATHS wholesale like the auth routes
above — it goes through the path-scoped `_PATH_SCOPED_PRIVATE_FIELDS` redaction
instead, keyed on the exact key name the client uses on the exact route that
carries it.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.db.models import HTTPAuditRow
from app.db.session import get_session
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


# ── DEF430 MAJOR-1 ───────────────────────────────────────────────────────
#
# Privacy v2.1 says the Alpaca account summary "is used for that request"
# and is "not store[d] ... as its own record". The DEF419 preview snapshot
# rides `/v1/sim/preview` under the key `account` — a key `_PRIVATE_FIELD_RE`
# (which only matches literally "alpaca") never touched, so it was persisted
# to `http_audit.request_body` verbatim for 90 days, making that sentence
# false. Fix is path-scoped: `account` is redacted on `/v1/sim/preview`
# specifically, not globally (an unrelated route's own `account` key must
# survive untouched).

_REAL_MANDATE_SNAPSHOT = {
    # The exact wire shape `AlpacaSnapshot.toMandateSnapshotJson()` sends —
    # `kind`, `equity`, `cash`, `positions[{ticker, qty, market_value}]` —
    # per `backend/app/schemas/alpaca.py`'s `AccountSnapshotIn`. `MSFT` here
    # is deliberately NOT the previewed trade's own ticker (`NVDA` below), so
    # a leak-check on this symbol can't pass by accident just because the
    # (unredacted) top-level `ticker` field also names it.
    "kind": "alpaca_paper",
    "equity": 104321.5,
    "cash": 50000.0,
    "positions": [
        {"ticker": "MSFT", "qty": 12, "market_value": 2100.0},
    ],
}


def _permissive_mandate() -> dict:
    return {
        "compliance": {"long_only": True},
        "single_name_cap_pct": 150.0,
        "max_open_positions": 50,
        "max_trades_per_day": 50,
        "max_trades_per_week": 50,
        "post_loss_cooldown_hours": 0,
        "max_open_risk_pct": 100.0,
        "max_drawdown_pct": 100,
    }


def _sim_preview_app() -> FastAPI:
    from app.api.sim import router as sim_router

    app = FastAPI()
    app.include_router(sim_router)
    app.add_middleware(HTTPAuditMiddleware)
    return app


def _new_user_and_token():
    from app.services.auth_service import AuthService

    auth = AuthService()
    u, t, _ = auth.ensure_anonymous(device_user_id=None)
    return u.id, t


def test_sim_preview_account_snapshot_is_redacted_in_http_audit() -> None:
    """Post the REAL `toMandateSnapshotJson` wire shape through the REAL
    `/v1/sim/preview` route (with the real middleware attached), then read
    back the real stored `HTTPAuditRow` — it must hold no `equity`, `cash`,
    or `positions`."""
    client = TestClient(_sim_preview_app(), raise_server_exceptions=False)
    user_id, token = _new_user_and_token()

    r = client.post(
        "/v1/sim/preview",
        json={
            "user_id": str(user_id),
            "ticker": "NVDA",
            "side": "buy",
            "quantity": 1,
            "order_type": "market",
            "mandate_override": _permissive_mandate(),
            "account": _REAL_MANDATE_SNAPSHOT,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text

    with get_session() as s:
        row = s.execute(
            select(HTTPAuditRow).where(HTTPAuditRow.path == "/v1/sim/preview")
        ).scalar_one()

    assert row.request_body is not None
    assert row.request_body.count('"account": "[REDACTED]"') == 1 or (
        '"account":"[REDACTED]"' in row.request_body
    )
    for leaked in ("104321.5", "50000.0", "MSFT", "2100.0"):
        assert leaked not in row.request_body, (
            f"{leaked!r} from the Alpaca account snapshot leaked into "
            f"http_audit.request_body: {row.request_body}"
        )
    assert '"equity"' not in row.request_body
    assert '"cash"' not in row.request_body
    # Quoted with the leading `"positions"` key form (not a bare substring
    # check) — `mandate_override.max_open_positions` legitimately contains
    # the substring "positions" and must NOT make this assertion pass for
    # the wrong reason.
    assert '"positions"' not in row.request_body
    # The unrelated fields on the same request are untouched — this is a
    # redaction of one key, not a wholesale SCRUB_PATHS-style blanking.
    assert "market" in row.request_body
    assert str(user_id) in row.request_body


def test_room_body_alpaca_key_is_still_redacted_alongside_the_new_fix() -> None:
    """The pre-existing CR202 redaction (the `alpaca` key, used by Room
    convene / 1-on-1) must keep working after adding the path-scoped
    `account` redaction — this is an addition, not a replacement."""
    app = _make_app("/v1/room/stream")
    recorded: list[dict] = []

    def _capture(**kwargs: object) -> None:
        recorded.append(dict(kwargs))

    with patch("app.middleware.http_audit.record_http", side_effect=_capture):
        client = TestClient(app, raise_server_exceptions=False)
        client.post(
            "/v1/room/stream",
            json={"user_id": "u1", "ticker": "AAPL", "alpaca": _REAL_MANDATE_SNAPSHOT},
        )

    assert len(recorded) == 1
    body = recorded[0]["request_body"]
    assert b'"alpaca": "[REDACTED]"' in body or b'"alpaca":"[REDACTED]"' in body
    assert b"104321.5" not in body


def test_an_unrelated_routes_account_key_is_not_swept() -> None:
    """The redaction is scoped to `/v1/sim/preview` — a different route that
    happens to also use the generic key name `account` for something else
    entirely must be untouched. Proves this is a path-scoped fix, not a
    second global `_PRIVATE_FIELD_RE`-style entry for `account`."""
    app = _make_app("/v1/billing/something")
    recorded: list[dict] = []

    def _capture(**kwargs: object) -> None:
        recorded.append(dict(kwargs))

    with patch("app.middleware.http_audit.record_http", side_effect=_capture):
        client = TestClient(app, raise_server_exceptions=False)
        client.post(
            "/v1/billing/something",
            json={"account": "checking-1234", "amount": 9.99},
        )

    assert len(recorded) == 1
    body = recorded[0]["request_body"]
    assert b"[REDACTED]" not in body
    assert b"checking-1234" in body
