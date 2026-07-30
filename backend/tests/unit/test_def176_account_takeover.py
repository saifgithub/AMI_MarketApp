"""DEF176 (security review C1) — account takeover via body-supplied
`user_id` on /v1/auth/apple and /v1/auth/google.

Before the fix: an attacker authenticating with their OWN valid identity
token could pass `user_id=<victim>` in the body. Since the attacker's
`sub`/email matched no row, resolution fell through to loading the
victim's row by `user_id` and permanently attaching the attacker's
apple_id/google_id to it — durable account takeover.

The fix removes `user_id` from both request schemas and binds the claim
to the caller's Bearer (`Depends(get_current_user)`), exactly like the
magic-link routes. These tests prove a foreign/victim user_id in the
body can no longer bind the attacker's identity to the victim's row.
"""

from __future__ import annotations

import base64
import json
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth import router as auth_router
from app.db import get_session
from app.db.models import User
from app.services.auth_service import AuthService, get_auth_service
from app.services.oidc_verifier import OIDCVerificationError
from sqlalchemy import select


class _FakeAppleVerifier:
    def verify(self, token: str) -> dict:
        if not token or token.count(".") != 2:
            raise OIDCVerificationError("malformed")
        _h, body, _s = token.split(".")
        body += "=" * (-len(body) % 4)
        return json.loads(base64.urlsafe_b64decode(body).decode())


class _FakeGoogleVerifier:
    def verify(self, token: str) -> dict:
        if not token or token.count(".") != 2:
            raise OIDCVerificationError("malformed")
        _h, body, _s = token.split(".")
        body += "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(body).decode())
        payload.setdefault("email_verified", True)
        return payload


def _jwt(sub: str, *, email: str | None = None) -> str:
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
def _swap_verifiers():
    """Swap the singleton AuthService's verifiers for fakes so the route
    tests don't have to mint real RSA-signed identity tokens."""
    import app.services.auth_service as svc
    svc._service = None
    s = AuthService(
        apple_verifier=_FakeAppleVerifier(),
        google_verifier=_FakeGoogleVerifier(),
    )
    svc._service = s
    yield
    svc._service = None


def test_apple_body_user_id_cannot_take_over_victim_row(client: TestClient):
    """The attacker authenticates with their OWN valid identity token but
    supplies a VICTIM's user_id in the body. Pre-fix: the victim's row got
    loaded and permanently claimed. Post-fix: the body user_id is ignored
    (pydantic drops the unknown field); the claim binds to the attacker's
    own Bearer-authenticated (fresh anon) row."""
    auth = get_auth_service()
    victim, _victim_token, _ = auth.ensure_anonymous(device_user_id=None)
    attacker, attacker_token, _ = auth.ensure_anonymous(device_user_id=None)

    r = client.post(
        "/v1/auth/apple",
        json={
            "identity_token": _jwt("attacker-apple-sub"),
            "user_id": str(victim.id),
        },
        headers={"Authorization": f"Bearer {attacker_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # Must NOT be the victim's row.
    assert body["user"]["id"] != str(victim.id)
    assert body["user"]["id"] == str(attacker.id)

    with get_session() as s:
        victim_row = s.execute(select(User).where(User.id == victim.id)).scalar_one()
        assert victim_row.apple_id is None, "victim row must not be mutated"


def test_google_body_user_id_cannot_take_over_victim_row(client: TestClient):
    auth = get_auth_service()
    victim, _victim_token, _ = auth.ensure_anonymous(device_user_id=None)
    attacker, attacker_token, _ = auth.ensure_anonymous(device_user_id=None)

    r = client.post(
        "/v1/auth/google",
        json={
            "identity_token": _jwt("attacker-google-sub"),
            "user_id": str(victim.id),
        },
        headers={"Authorization": f"Bearer {attacker_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["id"] != str(victim.id)
    assert body["user"]["id"] == str(attacker.id)

    with get_session() as s:
        victim_row = s.execute(select(User).where(User.id == victim.id)).scalar_one()
        assert victim_row.google_id is None, "victim row must not be mutated"


def test_apple_requires_bearer(client: TestClient):
    r = client.post(
        "/v1/auth/apple",
        json={"identity_token": _jwt("no-bearer-sub")},
    )
    assert r.status_code == 401


def test_google_requires_bearer(client: TestClient):
    r = client.post(
        "/v1/auth/google",
        json={"identity_token": _jwt("no-bearer-sub")},
    )
    assert r.status_code == 401


def test_apple_uuid_enumeration_via_league_standings_no_longer_matters(client: TestClient):
    """Even a perfectly enumerable victim UUID (e.g. from league standings)
    is useless for this exploit now — the body field is inert."""
    victim_id = uuid4()  # not even a real user; the point is the body is ignored
    auth = get_auth_service()
    attacker, attacker_token, _ = auth.ensure_anonymous(device_user_id=None)
    r = client.post(
        "/v1/auth/apple",
        json={
            "identity_token": _jwt("attacker-sub-2"),
            "user_id": str(victim_id),
        },
        headers={"Authorization": f"Bearer {attacker_token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["user"]["id"] == str(attacker.id)
