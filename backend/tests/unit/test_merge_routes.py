"""BL16 (AT:R38) — /v1/auth/merge/preview + /v1/auth/merge route tests.

Also covers the `adopted_from_user_id` signal that flows back through
AuthVerifyResponse when account-linking Phase 1 silently adopts an
existing email row.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.auth import router as auth_router
from app.db import get_session
from app.db.models import JournalEntryRow, User
from app.services.auth_service import (
    AuthService,
    _log_adoption_event,
    _scaffold_token,
    get_auth_service,
)
from app.services.oidc_verifier import OIDCVerificationError


# ── Test doubles ────────────────────────────────────────────────────────


class _FakeAppleVerifier:
    def verify(self, token: str) -> dict:
        if not token or token.count(".") != 2:
            raise OIDCVerificationError("malformed")
        _h, body, _s = token.split(".")
        body += "=" * (-len(body) % 4)
        return json.loads(base64.urlsafe_b64decode(body).decode())


def _apple_jwt(sub: str, *, email: str | None = None) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"RS256"}').rstrip(b"=").decode()
    payload: dict = {"sub": sub}
    if email is not None:
        payload["email"] = email
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    sig = base64.urlsafe_b64encode(b"sig").rstrip(b"=").decode()
    return f"{header}.{body}.{sig}"


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.include_router(auth_router)
    return a


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _swap_apple_verifier():
    """Swap the singleton AuthService's Apple verifier for the fake one
    so the route tests don't have to mint real RSA-signed Apple JWTs."""
    import app.services.auth_service as svc
    svc._service = None
    s = AuthService(apple_verifier=_FakeAppleVerifier())
    svc._service = s
    yield
    svc._service = None


# ── adopted_from_user_id signal ─────────────────────────────────────────


def test_apple_response_carries_adopted_from_user_id_on_adoption(client: TestClient):
    """Sign in once with email X → user A. Sign in from a new device with
    Apple shipping the same email → adopts A, response signals the new
    device's pre-claim anon as `adopted_from_user_id`."""
    auth = get_auth_service()
    # First sign-in establishes the email row.
    user_a_au, _, _ = auth.ensure_anonymous(device_user_id=None)
    code = auth.start_magic_link(
        email="adopt-me@example.com", user_id=user_a_au.id,
    )
    auth.verify_magic_link(
        email="adopt-me@example.com", code=code, user_id=user_a_au.id,
    )

    # Second device — fresh anon, then Apple ships same email.
    user_b_au, token_b, _ = auth.ensure_anonymous(device_user_id=None)
    r = client.post("/v1/auth/apple", json={
        "identity_token": _apple_jwt("apple-sub-adopt", email="adopt-me@example.com"),
        "user_id": str(user_b_au.id),
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["id"] == str(user_a_au.id)
    assert body["adopted_from_user_id"] == str(user_b_au.id)


def test_apple_response_adopted_from_is_null_on_fresh_claim(client: TestClient):
    """No matching email/sub → fresh anon promoted in place. `adopted_from`
    must be null (the same row got claimed, not adopted)."""
    auth = get_auth_service()
    user_au, token, _ = auth.ensure_anonymous(device_user_id=None)
    r = client.post("/v1/auth/apple", json={
        "identity_token": _apple_jwt("brand-new-sub", email="fresh@example.com"),
        "user_id": str(user_au.id),
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["id"] == str(user_au.id)  # promoted in place
    assert body["adopted_from_user_id"] is None


def test_magic_link_response_carries_adopted_from_on_email_match(client: TestClient):
    auth = get_auth_service()
    # Establish email row.
    user_a_au, _, _ = auth.ensure_anonymous(device_user_id=None)
    code1 = auth.start_magic_link(
        email="shared-ml@example.com", user_id=user_a_au.id,
    )
    auth.verify_magic_link(
        email="shared-ml@example.com", code=code1, user_id=user_a_au.id,
    )
    # New device with a different anon.
    user_b_au, token_b, _ = auth.ensure_anonymous(device_user_id=None)
    code2 = auth.start_magic_link(
        email="shared-ml@example.com", user_id=user_b_au.id,
    )
    r = client.post(
        "/v1/auth/magic_link/verify",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"email": "shared-ml@example.com", "code": code2},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["id"] == str(user_a_au.id)
    assert body["adopted_from_user_id"] == str(user_b_au.id)


# ── /v1/auth/merge/preview ──────────────────────────────────────────────


def test_preview_happy_path_after_adoption(client: TestClient):
    """Adoption fires → SubscriptionEventRow recorded → preview returns
    counts of mergeable rows."""
    auth = get_auth_service()
    # Adopter user with email + a journal entry.
    adopter_au, adopter_token, _ = auth.ensure_anonymous(device_user_id=None)
    with get_session() as s:
        adopter_row = s.execute(
            select(User).where(User.id == adopter_au.id)
        ).scalar_one()
        adopter_row.email = "adopter-preview@example.com"
        adopter_row.is_anonymous = False
        adopter_row.claimed_at = datetime.now(timezone.utc)
    # Orphan with some content.
    orphan_au, _, _ = auth.ensure_anonymous(device_user_id=None)
    with get_session() as s:
        for i in range(4):
            s.add(JournalEntryRow(
                user_id=orphan_au.id, entry_type="trade",
                title=f"orphan entry {i}",
            ))
        _log_adoption_event(
            s, from_user_id=orphan_au.id, to_user_id=adopter_au.id,
        )

    r = client.get(
        f"/v1/auth/merge/preview/{orphan_au.id}",
        headers={"Authorization": f"Bearer {adopter_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["from_user_id"] == str(orphan_au.id)
    assert body["to_user_id"] == str(adopter_au.id)
    assert body["journal_entries"] == 4
    assert body["mandate_conflict"] is False


def test_preview_403_when_no_adoption_event_for_caller(client: TestClient):
    auth = get_auth_service()
    caller_au, caller_token, _ = auth.ensure_anonymous(device_user_id=None)
    other_user_id = uuid4()
    # No SubscriptionEventRow linking other_user_id → caller — caller is
    # not the adopter; deny.
    r = client.get(
        f"/v1/auth/merge/preview/{other_user_id}",
        headers={"Authorization": f"Bearer {caller_token}"},
    )
    assert r.status_code == 403


def test_preview_404_when_orphan_already_merged(client: TestClient):
    """Caller IS the adopter (event row exists), but the orphan user_id
    no longer resolves to a User row — it was deleted by a prior merge."""
    auth = get_auth_service()
    adopter_au, adopter_token, _ = auth.ensure_anonymous(device_user_id=None)
    ghost_orphan_id = uuid4()  # never existed
    with get_session() as s:
        _log_adoption_event(
            s, from_user_id=ghost_orphan_id, to_user_id=adopter_au.id,
        )
    r = client.get(
        f"/v1/auth/merge/preview/{ghost_orphan_id}",
        headers={"Authorization": f"Bearer {adopter_token}"},
    )
    assert r.status_code == 404


def test_preview_401_without_bearer(client: TestClient):
    r = client.get(f"/v1/auth/merge/preview/{uuid4()}")
    assert r.status_code == 401


# ── /v1/auth/merge (POST) ───────────────────────────────────────────────


def test_execute_happy_path_returns_counts_and_deletes_orphan(client: TestClient):
    auth = get_auth_service()
    adopter_au, adopter_token, _ = auth.ensure_anonymous(device_user_id=None)
    orphan_au, _, _ = auth.ensure_anonymous(device_user_id=None)
    with get_session() as s:
        for i in range(2):
            s.add(JournalEntryRow(
                user_id=orphan_au.id, entry_type="trade",
                title=f"orphan {i}",
            ))
        _log_adoption_event(
            s, from_user_id=orphan_au.id, to_user_id=adopter_au.id,
        )

    r = client.post(
        "/v1/auth/merge",
        headers={"Authorization": f"Bearer {adopter_token}"},
        json={"from_user_id": str(orphan_au.id)},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["counts"]["journal_entries"] == 2
    assert body["mandate_kept"] == "neither"

    # Orphan row + its journal entries are gone / re-keyed.
    with get_session() as s:
        assert s.execute(
            select(User).where(User.id == orphan_au.id)
        ).scalar_one_or_none() is None
        entries = s.execute(
            select(JournalEntryRow).where(JournalEntryRow.user_id == adopter_au.id)
        ).scalars().all()
        assert len(entries) == 2


def test_execute_403_when_caller_not_the_adopter(client: TestClient):
    auth = get_auth_service()
    real_adopter_au, _, _ = auth.ensure_anonymous(device_user_id=None)
    orphan_au, _, _ = auth.ensure_anonymous(device_user_id=None)
    intruder_au, intruder_token, _ = auth.ensure_anonymous(device_user_id=None)
    with get_session() as s:
        _log_adoption_event(
            s, from_user_id=orphan_au.id, to_user_id=real_adopter_au.id,
        )
    r = client.post(
        "/v1/auth/merge",
        headers={"Authorization": f"Bearer {intruder_token}"},
        json={"from_user_id": str(orphan_au.id)},
    )
    assert r.status_code == 403


def test_execute_404_when_orphan_already_merged(client: TestClient):
    auth = get_auth_service()
    adopter_au, adopter_token, _ = auth.ensure_anonymous(device_user_id=None)
    ghost_orphan_id = uuid4()
    with get_session() as s:
        _log_adoption_event(
            s, from_user_id=ghost_orphan_id, to_user_id=adopter_au.id,
        )
    r = client.post(
        "/v1/auth/merge",
        headers={"Authorization": f"Bearer {adopter_token}"},
        json={"from_user_id": str(ghost_orphan_id)},
    )
    assert r.status_code == 404
