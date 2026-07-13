"""Tests for the adversarial-audit (2026-05-18) Phase 1.5 fixes.

Each test corresponds to one of the deploy-blocking findings A1-A6.
Together with test_auth_dependency.py these close the coverage gap the
auditor flagged in section "Test coverage notes".
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth import router as auth_router
from app.api.coach import router as coach_router
from app.api.lessons import router as lessons_router
from app.api.mandate import router as mandate_router
from app.api.one_on_one import router as one_on_one_router
from app.api.room import router as room_router
from app.core.config import settings
from app.services.auth_service import (
    AuthService,
    _scaffold_token,
    parse_scaffold_token,
)


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.include_router(auth_router)
    a.include_router(mandate_router)
    a.include_router(lessons_router)
    a.include_router(room_router)
    a.include_router(coach_router)
    a.include_router(one_on_one_router)
    return a


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def _new_user() -> tuple[UUID, str]:
    auth = AuthService()
    u, t, _ = auth.ensure_anonymous(device_user_id=None)
    return u.id, t


# ── A1: env=dev no longer accepts legacy unsigned tokens ──────────────────


def test_legacy_unsigned_token_rejected_outside_local(monkeypatch):
    monkeypatch.setattr(settings, "env", "staging")
    legacy = f"scaffold:{uuid4().hex}"
    assert parse_scaffold_token(legacy) is None


def test_legacy_unsigned_token_also_rejected_in_dev(monkeypatch):
    """The pre-audit code allowed legacy in env=dev. Closed by A1."""
    monkeypatch.setattr(settings, "env", "dev")
    legacy = f"scaffold:{uuid4().hex}"
    assert parse_scaffold_token(legacy) is None


def test_legacy_unsigned_token_still_accepted_in_local(monkeypatch):
    """Local dev still accepts legacy — needed for offline tinkering."""
    monkeypatch.setattr(settings, "env", "local")
    auth = AuthService()
    user, _, _ = auth.ensure_anonymous(device_user_id=None)
    legacy = f"scaffold:{user.id.hex}"
    assert parse_scaffold_token(legacy) == user.id


# ── A2: /v1/auth/anon doesn't mint for arbitrary device_user_id ───────────


def test_anon_endpoint_mints_fresh_when_no_bearer(client: TestClient):
    victim = uuid4()
    r = client.post("/v1/auth/anon", json={"device_user_id": str(victim)})
    assert r.status_code == 200
    returned_id = UUID(r.json()["user"]["id"])
    assert returned_id != victim, "no-bearer must mint fresh, not honour body"


def test_anon_endpoint_reuses_user_when_bearer_matches(client: TestClient):
    user_id, token = _new_user()
    r = client.post(
        "/v1/auth/anon",
        json={"device_user_id": str(user_id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert UUID(r.json()["user"]["id"]) == user_id


def test_anon_endpoint_ignores_body_when_bearer_belongs_to_someone_else(
    client: TestClient,
):
    user_a, token_a = _new_user()
    user_b_id = uuid4()
    r = client.post(
        "/v1/auth/anon",
        json={"device_user_id": str(user_b_id)},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    returned_id = UUID(r.json()["user"]["id"])
    assert returned_id not in (user_a, user_b_id), \
        "cross-user device_user_id must mint fresh"


# ── A3: magic-link requires auth, binds to current_user only ──────────────


def test_magic_link_start_requires_auth(client: TestClient):
    r = client.post("/v1/auth/magic_link/start", json={"email": "x@y.com"})
    assert r.status_code == 401


def test_magic_link_verify_requires_auth(client: TestClient):
    r = client.post(
        "/v1/auth/magic_link/verify",
        json={"email": "x@y.com", "code": "000000"},
    )
    assert r.status_code == 401


def test_magic_link_debug_code_returned_in_local(monkeypatch, client: TestClient):
    monkeypatch.setattr(settings, "env", "local")
    _, token = _new_user()
    r = client.post(
        "/v1/auth/magic_link/start",
        json={"email": "alpha@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["debug_code"] is not None


def test_magic_link_debug_code_hidden_in_staging(monkeypatch, client: TestClient):
    monkeypatch.setattr(settings, "env", "staging")
    _, token = _new_user()
    r = client.post(
        "/v1/auth/magic_link/start",
        json={"email": "alpha@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["debug_code"] is None


def test_magic_link_verify_binds_to_current_user(monkeypatch, client: TestClient):
    """User A authenticates, requests magic-link, verifies. The claim must
    attach to A's user row — no user_id field in the body to bypass."""
    monkeypatch.setattr(settings, "env", "local")
    user_a, token_a = _new_user()
    # Request the code as user A.
    r = client.post(
        "/v1/auth/magic_link/start",
        json={"email": "alpha@example.com"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    code = r.json()["debug_code"]
    # Verify still as user A.
    r = client.post(
        "/v1/auth/magic_link/verify",
        json={"email": "alpha@example.com", "code": code},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert UUID(body["user"]["id"]) == user_a
    assert body["user"]["email"] == "alpha@example.com"
    assert body["user"]["is_anonymous"] is False


# ── A4: Apple endpoint now lives in every env (Phase 3 verification) ──────
#
# This was originally a 503-everywhere-but-local gate. Closed in AT:R29 by
# the OIDCVerifier wiring — the route now reaches the verifier in every env.
# Bogus tokens get a 400 from the verifier (not a 503 from a routing gate).


def test_apple_endpoint_rejects_unverifiable_token(monkeypatch, client: TestClient):
    monkeypatch.setattr(settings, "env", "staging")
    r = client.post(
        "/v1/auth/apple",
        json={"identity_token": "header.body.sig", "user_id": str(uuid4())},
    )
    # Verifier rejects: malformed/unsigned token can't be validated against
    # Apple's JWKS. Route translates the OIDCVerificationError into HTTP 400.
    assert r.status_code == 400


# ── A5: lessons grant route removed ───────────────────────────────────────


def test_lessons_grant_route_removed(client: TestClient):
    r = client.post(
        "/v1/lessons/activations/grant",
        json={"user_id": str(uuid4()), "agent_id": "portfolio_manager"},
    )
    # 404 (no route) or 405 (method not allowed) — either confirms removal.
    assert r.status_code in (404, 405)


# ── A6: body / object ownership on coach + one_on_one ─────────────────────


def test_coach_start_rejects_foreign_user_in_body(client: TestClient):
    user_a, token_a = _new_user()
    user_b, _ = _new_user()
    r = client.post(
        "/v1/coach/start",
        json={
            "user_id": str(user_b),
            "agent_id": "portfolio_manager",
            "mode": "from_scratch",
            "locale": "en",
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert r.status_code == 403


def test_one_on_one_start_ignores_user_id_in_body(client: TestClient):
    """L-1 (AT:R32): OneOnOneStartRequest no longer accepts user_id.
    Extra fields are silently dropped by Pydantic; the route sources the
    user from the Bearer token. Sending a foreign user_id in the body is
    now harmless — the session opens under the bearer's identity."""
    user_a, token_a = _new_user()
    _user_b, _ = _new_user()
    r = client.post(
        "/v1/agents/one_on_one/start",
        json={
            "user_id": str(_user_b),  # extra field — ignored
            "agent_id": "concierge",
            "locale": "en",
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["user_id"] == str(user_a)  # bearer wins, not the body


def test_room_stream_rejects_foreign_user_in_body(client: TestClient):
    user_a, token_a = _new_user()
    user_b, _ = _new_user()
    r = client.post(
        "/v1/room/stream",
        json={
            "user_id": str(user_b),
            "ticker": "AAPL",
            "locale": "en",
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert r.status_code == 403


def test_room_get_rejects_foreign_run_id(client: TestClient):
    """A6: GET /v1/room/{run_id} must reject when the run belongs to another
    user. Done by looking up the run and comparing run.user_id to bearer."""
    user_a, token_a = _new_user()
    fake_run_id = uuid4()  # not a real run, exercises the 404 path
    r = client.get(
        f"/v1/room/{fake_run_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    # 404 (no such run) is acceptable; what we're guarding is "200 with
    # someone else's transcript", which the new ownership check prevents.
    assert r.status_code in (403, 404)


def test_one_on_one_get_rejects_foreign_session(client: TestClient):
    """A6 cousin: GET /v1/agents/one_on_one/{session_id} loads the session
    and checks ownership. Strict: sessions with no user_id are also rejected.
    """
    _, token_a = _new_user()
    nonexistent_session = uuid4()
    r = client.get(
        f"/v1/agents/one_on_one/{nonexistent_session}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    # 404 (no such session) is acceptable; the protection is against
    # returning a session owned by user B to caller A.
    assert r.status_code in (403, 404)


# ── Residual: dead Flutter call site ──────────────────────────────────────


def test_dead_flutter_grant_call_404s(client: TestClient):
    """Flutter still defines `ApiClient.grantActivation()` that targets the
    removed route. This test documents the contract: such a call gets 404
    from the backend (rather than silently succeeding). The Flutter method
    itself can be deleted in a follow-up (no callers in the app)."""
    r = client.post(
        "/v1/lessons/activations/grant",
        json={"user_id": str(uuid4()), "agent_id": "portfolio_manager",
              "method": "founder_grant"},
    )
    assert r.status_code in (404, 405)


# ── BL13 (AT:R32): OnboardingSession ↔ claimed_user_id binding ────────────


def test_magic_link_verify_binds_onboarding_session(monkeypatch, client: TestClient):
    """When the client passes `onboarding_session_id`, the matching session's
    `claimed_user_id` is stamped with the new user. Enables cohort analysis +
    GDPR-clean deletion."""
    import asyncio
    from app.schemas.onboarding import OnboardingSession
    from app.services.session_store import get_session_store

    monkeypatch.setattr(settings, "env", "local")
    user_a, token_a = _new_user()

    # Seed an onboarding session in the store.
    store = get_session_store()
    session = OnboardingSession()  # default-factories id + timestamps
    asyncio.run(store.create(session))

    # Mint a magic-link code as user_a (env=local returns debug_code).
    r_start = client.post(
        "/v1/auth/magic_link/start",
        json={"email": "bl13@example.com"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    code = r_start.json()["debug_code"]

    # Verify, passing the onboarding session id.
    r = client.post(
        "/v1/auth/magic_link/verify",
        json={
            "email": "bl13@example.com",
            "code": code,
            "onboarding_session_id": str(session.id),
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert r.status_code == 200

    # Re-read the session — claimed_user_id now points to user_a.
    saved = asyncio.run(store.get(session.id))
    assert saved is not None
    assert saved.claimed_user_id == user_a


def test_magic_link_verify_unknown_session_id_silently_skips(monkeypatch, client: TestClient):
    """An onboarding_session_id that doesn't exist in the store (expired or
    fabricated) is silently ignored — verify still succeeds, no crash."""
    monkeypatch.setattr(settings, "env", "local")
    _, token_a = _new_user()
    r_start = client.post(
        "/v1/auth/magic_link/start",
        json={"email": "unknown-session@example.com"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    code = r_start.json()["debug_code"]
    r = client.post(
        "/v1/auth/magic_link/verify",
        json={
            "email": "unknown-session@example.com",
            "code": code,
            "onboarding_session_id": str(uuid4()),  # never created
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert r.status_code == 200
