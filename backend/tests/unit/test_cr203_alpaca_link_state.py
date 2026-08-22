"""CR203 — the host tracks WHO has a linked Alpaca account, and nothing more.

CR202 moved the credential to the device, which also removed the only way to
answer "who linked?". This restores the answer without restoring the custody:
`users.alpaca_linked_at` is a timestamp, not a secret. The tests below defend
both halves of that sentence — that the fact is recorded, and that the means to
use it is still absent.

The second half is the one worth having. It would be easy to "helpfully" widen
this endpoint into taking the key again (to validate the claim server-side, say)
and land straight back in DEF044.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.alpaca import router as alpaca_router
from app.db import get_session
from app.db.models import User
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


def _stored(user_id) -> datetime | None:
    """The stored stamp, normalised to UTC-aware.

    The unit-test fixture is SQLite, which hands back a naive datetime where
    Postgres returns an aware one. Normalising here keeps the assertions about
    CR203's behaviour rather than about which driver ran them.
    """
    with get_session() as s:
        value = s.execute(
            select(User.alpaca_linked_at).where(User.id == user_id)
        ).scalar_one()
    if value is not None and value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


class TestReportingLinkState:
    def test_a_user_starts_unlinked(self, client):
        user, _ = _claimed()
        assert _stored(user.id) is None

    def test_reporting_linked_stamps_a_time(self, client):
        user, token = _claimed()
        before = datetime.now(timezone.utc)

        resp = client.post(
            "/v1/alpaca/link_state", json={"linked": True}, headers=_auth(token)
        )
        assert resp.status_code == 200
        assert resp.json()["linked"] is True

        stored = _stored(user.id)
        assert stored is not None
        assert stored >= before - timedelta(seconds=5)

    def test_reporting_unlinked_clears_it(self, client):
        user, token = _claimed()
        client.post("/v1/alpaca/link_state", json={"linked": True}, headers=_auth(token))
        assert _stored(user.id) is not None

        resp = client.post(
            "/v1/alpaca/link_state", json={"linked": False}, headers=_auth(token)
        )
        assert resp.status_code == 200
        assert resp.json()["linked"] is False
        assert resp.json()["linked_at"] is None
        assert _stored(user.id) is None

    def test_repeat_reports_refresh_the_timestamp(self, client):
        """The value of a self-declared flag is its age, so a repeat report has
        to move the clock — a no-op would leave every reader unable to tell a
        live link from one last confirmed a year ago."""
        user, token = _claimed()
        client.post("/v1/alpaca/link_state", json={"linked": True}, headers=_auth(token))
        first = _stored(user.id)

        with get_session() as s:
            row = s.execute(select(User).where(User.id == user.id)).scalar_one()
            row.alpaca_linked_at = first - timedelta(days=30)
            s.commit()

        client.post("/v1/alpaca/link_state", json={"linked": True}, headers=_auth(token))
        assert _stored(user.id) > first - timedelta(days=30)

    def test_anonymous_users_are_rejected(self, client):
        _, token = _anon()
        resp = client.post(
            "/v1/alpaca/link_state", json={"linked": True}, headers=_auth(token)
        )
        assert resp.status_code == 403

    def test_one_user_cannot_report_for_another(self, client):
        """`user_id` is taken from the bearer and the body has nowhere to name
        one — isolation is structural. Asserted rather than assumed, because
        'the body has no field for it' is exactly the kind of claim that stops
        being true when someone adds a field."""
        victim, _ = _claimed()
        _, attacker_token = _claimed()

        client.post(
            "/v1/alpaca/link_state",
            json={"linked": True, "user_id": str(victim.id)},
            headers=_auth(attacker_token),
        )
        assert _stored(victim.id) is None


class TestItIsStillNotACredentialStore:
    def test_the_endpoint_accepts_no_key_material(self, client):
        """A key posted alongside the flag must not be stored anywhere on User.

        This is the regression that would quietly undo CR202: widening this
        route to 'also take the key so we can verify the claim' puts the secret
        back on the host, and DEF044/DEF181/DEF182/DEF185 come with it.
        """
        user, token = _claimed()
        client.post(
            "/v1/alpaca/link_state",
            json={"linked": True, "api_key": "PKTEST", "api_secret": "sh-secret"},
            headers=_auth(token),
        )

        with get_session() as s:
            row = s.execute(select(User).where(User.id == user.id)).scalar_one()

        for attr in ("alpaca_access_token", "alpaca_refresh_token", "alpaca_auth_mode"):
            assert not hasattr(row, attr)

        values = [
            v for k, v in vars(row).items()
            if isinstance(v, str) and not k.startswith("_")
        ]
        assert not any("sh-secret" in v or "PKTEST" in v for v in values), (
            "key material posted to link_state was persisted on the User row"
        )

    def test_the_stored_value_carries_no_secret(self, client):
        user, token = _claimed()
        client.post("/v1/alpaca/link_state", json={"linked": True}, headers=_auth(token))
        assert isinstance(_stored(user.id), datetime)
