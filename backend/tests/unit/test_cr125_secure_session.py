"""CR125 — mobile secure session (backend half).

Covers the acceptance criteria from
docs/forward_planning/CR125_mobile_secure_session/CR125_mobile_secure_session.md:

  - an expired or wrong-version token 401s at every guarded route
  - `DELETE /v1/auth/session` then reuse of the old token → 401
  - sign-out bumps `token_version` in the DB (real revocation, not a no-op)
  - a revoked/expired bearer no longer proves device-ownership on
    `/v1/auth/anon` (would otherwise re-mint a fresh valid token, undoing
    the sign-out — see the CR125 comment in `api/auth.py::anon_session`)
  - issue/parse round-trip carries the token_version through
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.auth import router as auth_router
from app.api.mandate import router as mandate_router
from app.db import get_session
from app.db.models import User
from app.services.auth_service import AuthService, _scaffold_token


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.include_router(auth_router)
    a.include_router(mandate_router)
    return a


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def _new_user() -> tuple[UUID, str]:
    auth = AuthService()
    u, t, _ = auth.ensure_anonymous(device_user_id=None)
    return u.id, t


def _current_version(user_id: UUID) -> int:
    with get_session() as s:
        row = s.execute(select(User).where(User.id == user_id)).scalar_one()
        return row.token_version


# ── expiry ──────────────────────────────────────────────────────────────


def test_token_accepted_before_expiry(client: TestClient):
    user_id, _ = _new_user()
    token = _scaffold_token(user_id, token_version=_current_version(user_id), ttl_days=30)
    r = client.get(f"/v1/mandate/{user_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_token_rejected_after_expiry(client: TestClient):
    user_id, _ = _new_user()
    token = _scaffold_token(user_id, token_version=_current_version(user_id), ttl_days=-1)
    r = client.get(f"/v1/mandate/{user_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_whoami_rejects_expired_token(client: TestClient):
    user_id, _ = _new_user()
    token = _scaffold_token(user_id, token_version=_current_version(user_id), ttl_days=-1)
    r = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


# ── token_version revocation ───────────────────────────────────────────


def test_stale_token_version_returns_401(client: TestClient):
    """A token minted before a version bump (e.g. from another sign-in on
    the same account) 401s once the version has moved on."""
    user_id, token = _new_user()
    with get_session() as s:
        row = s.execute(select(User).where(User.id == user_id)).scalar_one()
        row.token_version += 1
    r = client.get(f"/v1/mandate/{user_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_sign_out_bumps_token_version_in_db(client: TestClient):
    user_id, token = _new_user()
    before = _current_version(user_id)
    r = client.delete("/v1/auth/session", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == {"signed_out": True}
    assert _current_version(user_id) == before + 1


def test_sign_out_then_replay_old_bearer_returns_401(client: TestClient):
    user_id, token = _new_user()
    r = client.delete("/v1/auth/session", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    replay = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert replay.status_code == 401


def test_sign_out_then_replay_on_guarded_route_returns_401(client: TestClient):
    """Same as above, exercised against a non-auth guarded route (mandate),
    proving the revocation isn't special-cased to the auth router."""
    user_id, token = _new_user()
    client.delete("/v1/auth/session", headers={"Authorization": f"Bearer {token}"})
    r = client.get(f"/v1/mandate/{user_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_sign_out_does_not_affect_other_users(client: TestClient):
    user_a, token_a = _new_user()
    user_b, token_b = _new_user()
    client.delete("/v1/auth/session", headers={"Authorization": f"Bearer {token_a}"})
    r = client.get(f"/v1/mandate/{user_b}", headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code == 200


def test_fresh_token_after_reauth_works_again(client: TestClient):
    """Sign out, then re-bootstrap (no bearer, as the client does after
    clearing its local copy) — the resulting fresh token is valid."""
    user_id, token = _new_user()
    client.delete("/v1/auth/session", headers={"Authorization": f"Bearer {token}"})
    r = client.post("/v1/auth/anon", json={"device_user_id": None})
    assert r.status_code == 200
    new_token = r.json()["token"]
    check = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {new_token}"})
    assert check.status_code == 200


# ── revoked bearer must not re-prove device ownership on /v1/auth/anon ──


def test_revoked_token_no_longer_proves_ownership_on_anon(client: TestClient):
    """Before CR125's anon_session fix, a signed-out-but-not-yet-expired
    token still satisfied the `device_user_id == authenticated_user_id`
    trust check, so /v1/auth/anon would happily re-mint a brand-new valid
    token for the "revoked" user — silently undoing the sign-out. Now the
    revoked bearer proves nothing, so the call mints a fresh user instead of
    reusing the original."""
    user_id, token = _new_user()
    client.delete("/v1/auth/session", headers={"Authorization": f"Bearer {token}"})
    r = client.post(
        "/v1/auth/anon",
        json={"device_user_id": str(user_id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    returned_id = UUID(r.json()["user"]["id"])
    assert returned_id != user_id, "revoked bearer must not prove ownership"


def test_expired_token_also_does_not_prove_ownership_on_anon(client: TestClient):
    user_id, _ = _new_user()
    expired = _scaffold_token(user_id, token_version=_current_version(user_id), ttl_days=-1)
    r = client.post(
        "/v1/auth/anon",
        json={"device_user_id": str(user_id)},
        headers={"Authorization": f"Bearer {expired}"},
    )
    assert r.status_code == 200
    returned_id = UUID(r.json()["user"]["id"])
    assert returned_id != user_id


# ── issue/parse round trip carries the version ───────────────────────────


def test_issued_token_carries_current_version(client: TestClient):
    user_id, token = _new_user()
    from app.services.auth_service import parse_scaffold_token

    parsed = parse_scaffold_token(token)
    assert parsed is not None
    assert parsed.user_id == user_id
    assert parsed.token_version == _current_version(user_id) == 1
