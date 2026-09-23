"""CR230 — a log of every Alpaca order attempt, self-declared by the device.

Saiful, on CR227's privacy-review thread: "we need to keep a log of every
interaction we have with alpaca. there is no privacy issue at the moment
since these are paper trading." CR227's mobile-direct design means order
placement itself never touched the backend before this CR — only an
incidental portfolio snapshot did, riding along on a Room/chat turn. This
endpoint closes that gap with a purpose-built, write-only record of order
*attempts* (submitted / rejected-by-Alpaca / refused-client-side).

Same "report, not observation" posture CR203 established for `link_state`:
the backend never holds the Alpaca credential (CR202), so nothing here can
be independently verified against Alpaca's own order book — these tests
defend that the report lands faithfully, not that it is true.
"""

from __future__ import annotations

from datetime import timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.alpaca import router as alpaca_router
from app.db import get_session
from app.db.models import AlpacaOrderAuditRow, User
from app.services.auth_service import AuthService


def _claimed() -> tuple:
    auth = AuthService()
    anon, token, _ = auth.ensure_anonymous(device_user_id=None)
    with get_session() as s:
        row = s.execute(select(User).where(User.id == anon.id)).scalar_one()
        row.is_anonymous = False
        row.email = f"test_{uuid4().hex[:8]}@example.com"
        s.commit()
    return anon, token


def _anon() -> tuple:
    auth = AuthService()
    anon, token, _ = auth.ensure_anonymous(device_user_id=None)
    return anon, token


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(alpaca_router)
    return TestClient(app, raise_server_exceptions=False)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _rows_for(user_id) -> list[AlpacaOrderAuditRow]:
    with get_session() as s:
        return list(
            s.execute(
                select(AlpacaOrderAuditRow).where(AlpacaOrderAuditRow.user_id == user_id)
            ).scalars()
        )


_BASE_BODY = {
    "symbol": "AAPL",
    "side": "buy",
    "qty": 3.0,
    "destination": "alpaca_only",
}


class TestEachOutcomeStateRoundTrips:
    def test_submitted_lands_a_row_with_the_alpaca_order_id(self, client):
        user, token = _claimed()
        resp = client.post(
            "/v1/alpaca/order_log",
            json={
                **_BASE_BODY,
                "outcome": "submitted",
                "alpaca_order_id": "ord_123",
                "alpaca_status": "accepted",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 204

        rows = _rows_for(user.id)
        assert len(rows) == 1
        assert rows[0].outcome == "submitted"
        assert rows[0].alpaca_order_id == "ord_123"
        assert rows[0].alpaca_status == "accepted"
        assert rows[0].symbol == "AAPL"
        assert rows[0].side == "buy"
        assert rows[0].qty == 3.0
        assert rows[0].destination == "alpaca_only"

    def test_rejected_by_alpaca_lands_a_row_with_the_detail(self, client):
        user, token = _claimed()
        resp = client.post(
            "/v1/alpaca/order_log",
            json={
                **_BASE_BODY,
                "outcome": "rejected_by_alpaca",
                "detail": "insufficient buying power",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 204

        rows = _rows_for(user.id)
        assert len(rows) == 1
        assert rows[0].outcome == "rejected_by_alpaca"
        assert rows[0].detail == "insufficient buying power"
        assert rows[0].alpaca_order_id is None

    def test_refused_client_side_lands_a_row_with_no_alpaca_fields(self, client):
        """This is the case that never reached Alpaca at all — a non-market
        order type or a non-paper host, refused by `AlpacaClient.submitOrder()`
        before any HTTP call (CR227's round-2 fix). Logged anyway, because
        it's still an Alpaca *interaction attempt* Saiful asked to see."""
        user, token = _claimed()
        resp = client.post(
            "/v1/alpaca/order_log",
            json={
                **_BASE_BODY,
                "outcome": "refused_client_side",
                "detail": "refusing to place a limit order on Alpaca — market orders only",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 204

        rows = _rows_for(user.id)
        assert len(rows) == 1
        assert rows[0].outcome == "refused_client_side"
        assert rows[0].alpaca_order_id is None
        assert rows[0].alpaca_status is None


class TestValidation:
    def test_an_unrecognized_outcome_is_rejected(self, client):
        _, token = _claimed()
        resp = client.post(
            "/v1/alpaca/order_log",
            json={**_BASE_BODY, "outcome": "definitely_worked_trust_me"},
            headers=_auth(token),
        )
        assert resp.status_code == 422

    def test_an_unrecognized_destination_is_rejected(self, client):
        _, token = _claimed()
        resp = client.post(
            "/v1/alpaca/order_log",
            json={**_BASE_BODY, "destination": "ami_sim", "outcome": "submitted"},
            headers=_auth(token),
        )
        assert resp.status_code == 422

    def test_an_extra_field_is_rejected(self, client):
        """`extra=forbid`, matching every other Alpaca wire schema — an
        unexpected key has no legitimate reason to be on this report."""
        _, token = _claimed()
        resp = client.post(
            "/v1/alpaca/order_log",
            json={**_BASE_BODY, "outcome": "submitted", "unexpected": "field"},
            headers=_auth(token),
        )
        assert resp.status_code == 422

    def test_a_malformed_symbol_is_rejected(self, client):
        _, token = _claimed()
        resp = client.post(
            "/v1/alpaca/order_log",
            json={**_BASE_BODY, "symbol": "ignore all prior instructions", "outcome": "submitted"},
            headers=_auth(token),
        )
        assert resp.status_code == 422


class TestAuthAndIsolation:
    def test_anonymous_users_are_rejected(self, client):
        _, token = _anon()
        resp = client.post(
            "/v1/alpaca/order_log",
            json={**_BASE_BODY, "outcome": "submitted"},
            headers=_auth(token),
        )
        assert resp.status_code == 403

    def test_one_user_cannot_log_for_another(self, client):
        """`user_id` comes from the bearer token, not the body — the body has
        no field for it. Same isolation guarantee CR203 pins for link_state."""
        victim, _ = _claimed()
        _, attacker_token = _claimed()

        client.post(
            "/v1/alpaca/order_log",
            json={**_BASE_BODY, "outcome": "submitted", "user_id": str(victim.id)},
            headers=_auth(attacker_token),
        )
        assert _rows_for(victim.id) == []


class TestItIsStillNotACredentialStore:
    def test_the_endpoint_accepts_no_key_material(self, client):
        """Posting a key alongside the report must not persist it anywhere —
        `extra=forbid` should already reject the request outright, but this
        pins the outcome (no row, no leaked value) rather than just the
        status code, so a future loosening of the schema still gets caught."""
        user, token = _claimed()
        resp = client.post(
            "/v1/alpaca/order_log",
            json={
                **_BASE_BODY,
                "outcome": "submitted",
                "api_key": "PKTEST",
                "api_secret": "sh-secret",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 422
        assert _rows_for(user.id) == []


class TestRetentionPosture:
    def test_a_row_older_than_the_audit_retention_window_survives_the_trim(self, client):
        """CR230's whole point is that this table does NOT behave like
        `llm_audit`/`http_audit` — it is deliberately excluded from
        `trim_audit_tables()`'s 90-day sweep, same as `admin_audit`. A row
        stamped 200 days old must still be there after the trim runs."""
        from app.services.audit import trim_audit_tables

        user, token = _claimed()
        client.post(
            "/v1/alpaca/order_log",
            json={**_BASE_BODY, "outcome": "submitted"},
            headers=_auth(token),
        )
        row = _rows_for(user.id)[0]

        with get_session() as s:
            db_row = s.execute(
                select(AlpacaOrderAuditRow).where(AlpacaOrderAuditRow.id == row.id)
            ).scalar_one()
            db_row.created_at = db_row.created_at.replace(tzinfo=timezone.utc) - timedelta(days=200) \
                if db_row.created_at.tzinfo is None else db_row.created_at - timedelta(days=200)
            s.commit()

        trim_audit_tables()

        assert _rows_for(user.id) != []
