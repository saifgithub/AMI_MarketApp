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


@pytest.mark.parametrize("scrub_path", sorted(SCRUB_PATHS))
def test_scrub_paths_redact_bodies_with_a_trailing_slash(scrub_path: str) -> None:
    """DEF430 r3 MINOR-1 (u66): the trailing-slash normalisation also covers
    SCRUB_PATHS, but nothing pinned it. A POST to `<auth route>/` is recorded
    under the slash path, which is not literally in SCRUB_PATHS."""
    slash_path = scrub_path + "/"
    app = _make_app(slash_path)
    recorded: list[dict] = []

    def _capture(**kwargs: object) -> None:
        recorded.append(dict(kwargs))

    with patch("app.middleware.http_audit.record_http", side_effect=_capture):
        client = TestClient(app, raise_server_exceptions=False)
        client.post(slash_path, json={"identity_token": "secret-jwt", "password": "hunter2"})

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


# ── DEF430 round 2 MAJOR-A ───────────────────────────────────────────────
#
# The request-side fix above only redacts the `account` KEY on the request.
# `preview_trade`'s RESPONSE also echoes part of the same Alpaca paper
# snapshot: `cash_available` (the account's own cash) and `held_quantity`
# (a held position's own size), and the same numbers again inside free-text
# `violations` strings (e.g. "insufficient cash: need $X, have $50000.00";
# a concentration % next to the notional). Per-key redaction can't reach
# text embedded in a string value, so the fix goes dark on the WHOLE
# response body instead — same mechanism `SCRUB_PATHS` already uses for
# auth routes — but only when the matching REQUEST actually carried
# `account` (a preview with no `account` is AMI's own sim and must keep
# its normal, unredacted response).


def test_sim_preview_snapshot_response_is_fully_redacted_buy() -> None:
    """A snapshot-path buy preview: the stored RESPONSE body must contain
    no `50000` (the account's cash), no `cash_available`, and no
    `held_quantity` key."""
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
    # The real, unredacted response DOES carry the account's cash — proves
    # the test would fail without the fix (not a false negative).
    assert "cash_available" in r.text

    with get_session() as s:
        row = s.execute(
            select(HTTPAuditRow)
            .where(HTTPAuditRow.path == "/v1/sim/preview")
            .order_by(HTTPAuditRow.id.desc())
        ).scalars().first()

    assert row.response_body == "[REDACTED]"
    assert "50000" not in row.response_body
    assert "cash_available" not in row.response_body
    assert "held_quantity" not in row.response_body


def test_sim_preview_snapshot_response_is_fully_redacted_sell_of_held_position() -> None:
    """A snapshot-path sell of an already-held ticker: the response echoes
    `held_quantity` for that position — must not survive in the stored row."""
    client = TestClient(_sim_preview_app(), raise_server_exceptions=False)
    user_id, token = _new_user_and_token()

    held_snapshot = {
        "kind": "alpaca_paper",
        "equity": 104321.5,
        "cash": 50000.0,
        "positions": [
            {"ticker": "NVDA", "qty": 12, "market_value": 2100.0},
        ],
    }

    r = client.post(
        "/v1/sim/preview",
        json={
            "user_id": str(user_id),
            "ticker": "NVDA",
            "side": "sell",
            "quantity": 5,
            "order_type": "market",
            "mandate_override": _permissive_mandate(),
            "account": held_snapshot,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    assert "held_quantity" in r.text

    with get_session() as s:
        row = s.execute(
            select(HTTPAuditRow)
            .where(HTTPAuditRow.path == "/v1/sim/preview")
            .order_by(HTTPAuditRow.id.desc())
        ).scalars().first()

    assert row.response_body == "[REDACTED]"
    assert "held_quantity" not in row.response_body
    assert "12" not in row.response_body or "[REDACTED]" == row.response_body


def test_sim_preview_snapshot_response_is_fully_redacted_insufficient_cash() -> None:
    """A snapshot-path buy sized past the account's cash: the refusal
    violation TEXT carries `have $50000.00` — a per-key redaction can't
    reach that, so the whole response must go dark."""
    client = TestClient(_sim_preview_app(), raise_server_exceptions=False)
    user_id, token = _new_user_and_token()

    r = client.post(
        "/v1/sim/preview",
        json={
            "user_id": str(user_id),
            "ticker": "NVDA",
            "side": "buy",
            # Sized to blow well past $50000.0 cash at any plausible mark.
            "quantity": 500000,
            "order_type": "market",
            "mandate_override": _permissive_mandate(),
            "account": _REAL_MANDATE_SNAPSHOT,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    assert "50000" in r.text  # unredacted response really does leak it

    with get_session() as s:
        row = s.execute(
            select(HTTPAuditRow)
            .where(HTTPAuditRow.path == "/v1/sim/preview")
            .order_by(HTTPAuditRow.id.desc())
        ).scalars().first()

    assert row.response_body == "[REDACTED]"
    assert "50000" not in row.response_body


def test_sim_preview_without_account_keeps_normal_response() -> None:
    """A preview with NO `account` key (AMI's own sim portfolio, not a
    linked Alpaca account) must keep its response body exactly as before —
    this fix must not blank every preview response, only the snapshot
    path's."""
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
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text

    with get_session() as s:
        row = s.execute(
            select(HTTPAuditRow)
            .where(HTTPAuditRow.path == "/v1/sim/preview")
            .order_by(HTTPAuditRow.id.desc())
        ).scalars().first()

    assert row.response_body != "[REDACTED]"
    assert "cash_available" in row.response_body


# ── DEF430 round 2 MINOR-A ────────────────────────────────────────────────
#
# `_PATH_SCOPED_PRIVATE_FIELDS.get(path)` / the new response-scrub table
# above are exact dict lookups. A POST to `/v1/sim/preview/` (trailing
# slash) 307-redirects at the route layer, but THIS middleware sees the
# pre-redirect path, so without normalization the exact-match lookup misses
# and stores the full snapshot on both the request and the response.


def test_sim_preview_trailing_slash_request_is_still_redacted() -> None:
    client = TestClient(_sim_preview_app(), raise_server_exceptions=False)
    user_id, token = _new_user_and_token()

    r = client.post(
        "/v1/sim/preview/",
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
        follow_redirects=True,
    )
    assert r.status_code == 200, r.text

    with get_session() as s:
        rows = s.execute(
            select(HTTPAuditRow)
            .where(HTTPAuditRow.path.in_(["/v1/sim/preview", "/v1/sim/preview/"]))
            .order_by(HTTPAuditRow.id.asc())
        ).scalars().all()

    # The 307 redirect itself is recorded too (no body); find the row that
    # actually carried the POST body — the trailing-slash entry.
    slash_rows = [row for row in rows if row.path == "/v1/sim/preview/"]
    assert slash_rows, "expected the pre-redirect POST to be recorded under the trailing-slash path"
    row = slash_rows[0]

    assert row.request_body is not None
    for leaked in ("104321.5", "50000.0", "MSFT", "2100.0"):
        assert leaked not in row.request_body
    assert '"equity"' not in row.request_body
    assert '"cash"' not in row.request_body

    if row.response_body is not None:
        assert row.response_body == "[REDACTED]"
