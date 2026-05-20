"""Tests for the /v1/admin/* back-office API (AT:R27).

Covers:
  - get_admin dependency: 503 when unconfigured, 403 on bad secret, 200 on match
  - GET  /users search by email + device_user_id
  - GET  /users/{id} detail + events
  - PATCH /users/{id}/plan — happy path + unknown plan rejection
  - POST  /users/{id}/trial — grant
  - PATCH /users/{id}/trial — extend + revoke
  - POST  /users/{id}/credits — add + deduct + zero-delta rejection
  - POST  /users/{id}/suspend — happy path + double-suspend conflict
  - POST  /users/{id}/reinstate — happy path + not-suspended conflict
  - GET   /users/{id}/events — pagination
  - Suspension enforcement in get_current_user (403 on suspended user)
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin import router as admin_router
from app.api.dependencies import get_current_user
from app.core.config import settings
from app.services.auth_service import AuthService

_SECRET = "test-admin-secret-abc123"
_ADMIN_HDR = {"Authorization": f"Bearer {_SECRET}"}


@pytest.fixture(autouse=True)
def _set_admin_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_secret", _SECRET)


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(admin_router)
    return TestClient(app, raise_server_exceptions=False)


def _make_user(email: str | None = None) -> tuple:
    """Create a test user and return (user_id, token, device_user_id)."""
    from app.db import get_session
    from app.db.models import User
    from sqlalchemy import select

    auth = AuthService()
    device_id = uuid4()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)
    with get_session() as s:
        row = s.execute(select(User).where(User.id == user.id)).scalar_one()
        row.device_user_id = device_id
        if email:
            row.email = email
            row.is_anonymous = False
    return user.id, token, device_id


# ── Auth dependency ───────────────────────────────────────────────────────────

def test_admin_unconfigured_returns_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_secret", "")
    r = client.get("/v1/admin/users?email=x@y.com", headers=_ADMIN_HDR)
    assert r.status_code == 503


def test_admin_bad_secret_returns_403(client: TestClient) -> None:
    r = client.get("/v1/admin/users?email=x@y.com", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 403


def test_admin_no_header_returns_403(client: TestClient) -> None:
    r = client.get("/v1/admin/users?email=x@y.com")
    assert r.status_code == 403


# ── Search ────────────────────────────────────────────────────────────────────

def test_search_requires_param(client: TestClient) -> None:
    r = client.get("/v1/admin/users", headers=_ADMIN_HDR)
    assert r.status_code == 400


def test_search_by_email_not_found(client: TestClient) -> None:
    r = client.get("/v1/admin/users?email=nobody@example.com", headers=_ADMIN_HDR)
    assert r.status_code == 200
    assert r.json() == []


def test_search_by_email_found(client: TestClient) -> None:
    _make_user(email="found@example.com")
    r = client.get("/v1/admin/users?email=found@example.com", headers=_ADMIN_HDR)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["email"] == "found@example.com"


def test_search_by_device_user_id(client: TestClient) -> None:
    user_id, _, device_id = _make_user()
    r = client.get(f"/v1/admin/users?device_user_id={device_id}", headers=_ADMIN_HDR)
    assert r.status_code == 200
    assert any(u["id"] == str(user_id) for u in r.json())


# ── User detail ───────────────────────────────────────────────────────────────

def test_get_user_not_found(client: TestClient) -> None:
    r = client.get(f"/v1/admin/users/{uuid4()}", headers=_ADMIN_HDR)
    assert r.status_code == 404


def test_get_user_detail(client: TestClient) -> None:
    user_id, _, _ = _make_user()
    r = client.get(f"/v1/admin/users/{user_id}", headers=_ADMIN_HDR)
    assert r.status_code == 200
    d = r.json()
    assert d["id"] == str(user_id)
    assert d["plan"] == "floor_pass"
    assert d["recent_events"] == []


# ── Plan change ───────────────────────────────────────────────────────────────

def test_change_plan_valid(client: TestClient) -> None:
    user_id, _, _ = _make_user()
    r = client.patch(
        f"/v1/admin/users/{user_id}/plan",
        json={"plan": "trader", "note": "comp for beta test"},
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 200
    d = r.json()
    assert d["plan"] == "trader"
    assert len(d["recent_events"]) == 1
    ev = d["recent_events"][0]
    assert ev["event_type"] == "plan_changed"
    assert ev["from_value"] == "floor_pass"
    assert ev["to_value"] == "trader"
    assert ev["note"] == "comp for beta test"


def test_change_plan_invalid(client: TestClient) -> None:
    user_id, _, _ = _make_user()
    r = client.patch(
        f"/v1/admin/users/{user_id}/plan",
        json={"plan": "unicorn_tier"},
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 400


# ── Trial ─────────────────────────────────────────────────────────────────────

def test_grant_trial(client: TestClient) -> None:
    user_id, _, _ = _make_user()
    r = client.post(
        f"/v1/admin/users/{user_id}/trial",
        json={"days": 14},
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 200
    d = r.json()
    assert d["plan"] == "trial_trader"
    assert d["trial_started_at"] is not None
    assert d["trial_expires_at"] is not None
    ev = d["recent_events"][0]
    assert ev["event_type"] == "trial_granted"
    assert ev["to_value"] == "trial_trader:14d"


def test_extend_trial(client: TestClient) -> None:
    user_id, _, _ = _make_user()
    client.post(f"/v1/admin/users/{user_id}/trial", json={"days": 7}, headers=_ADMIN_HDR)
    r = client.patch(
        f"/v1/admin/users/{user_id}/trial",
        json={"action": "extend", "days": 7},
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 200
    ev = r.json()["recent_events"][0]
    assert ev["event_type"] == "trial_extended"


def test_extend_trial_requires_days(client: TestClient) -> None:
    user_id, _, _ = _make_user()
    r = client.patch(
        f"/v1/admin/users/{user_id}/trial",
        json={"action": "extend"},
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 400


def test_revoke_trial(client: TestClient) -> None:
    user_id, _, _ = _make_user()
    client.post(f"/v1/admin/users/{user_id}/trial", json={"days": 30}, headers=_ADMIN_HDR)
    r = client.patch(
        f"/v1/admin/users/{user_id}/trial",
        json={"action": "revoke"},
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 200
    d = r.json()
    assert d["plan"] == "floor_pass"
    assert d["trial_expires_at"] is None
    ev = d["recent_events"][0]
    assert ev["event_type"] == "trial_revoked"


# ── Credits ───────────────────────────────────────────────────────────────────

def test_add_credits(client: TestClient) -> None:
    user_id, _, _ = _make_user()
    r = client.post(
        f"/v1/admin/users/{user_id}/credits",
        json={"delta": 10, "note": "welcome pack"},
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 200
    d = r.json()
    assert d["credit_balance"] == 10
    ev = d["recent_events"][0]
    assert ev["event_type"] == "credits_added"
    assert ev["from_value"] == "0"
    assert ev["to_value"] == "10"


def test_deduct_credits(client: TestClient) -> None:
    user_id, _, _ = _make_user()
    client.post(f"/v1/admin/users/{user_id}/credits", json={"delta": 5}, headers=_ADMIN_HDR)
    r = client.post(
        f"/v1/admin/users/{user_id}/credits",
        json={"delta": -3},
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 200
    assert r.json()["credit_balance"] == 2
    ev = r.json()["recent_events"][0]
    assert ev["event_type"] == "credits_deducted"


def test_deduct_credits_floors_at_zero(client: TestClient) -> None:
    user_id, _, _ = _make_user()
    r = client.post(
        f"/v1/admin/users/{user_id}/credits",
        json={"delta": -100},
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 200
    assert r.json()["credit_balance"] == 0


def test_zero_delta_rejected(client: TestClient) -> None:
    user_id, _, _ = _make_user()
    r = client.post(
        f"/v1/admin/users/{user_id}/credits",
        json={"delta": 0},
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 400


# ── Suspend / reinstate ───────────────────────────────────────────────────────

def test_suspend_user(client: TestClient) -> None:
    user_id, _, _ = _make_user()
    r = client.post(
        f"/v1/admin/users/{user_id}/suspend",
        json={"note": "spam reports"},
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 200
    d = r.json()
    assert d["suspended_at"] is not None
    ev = d["recent_events"][0]
    assert ev["event_type"] == "user_suspended"
    assert ev["from_value"] == "active"
    assert ev["to_value"] == "suspended"


def test_double_suspend_conflict(client: TestClient) -> None:
    user_id, _, _ = _make_user()
    client.post(f"/v1/admin/users/{user_id}/suspend", json={}, headers=_ADMIN_HDR)
    r = client.post(f"/v1/admin/users/{user_id}/suspend", json={}, headers=_ADMIN_HDR)
    assert r.status_code == 409


def test_reinstate_user(client: TestClient) -> None:
    user_id, _, _ = _make_user()
    client.post(f"/v1/admin/users/{user_id}/suspend", json={}, headers=_ADMIN_HDR)
    r = client.post(
        f"/v1/admin/users/{user_id}/reinstate",
        json={"note": "false positive"},
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 200
    d = r.json()
    assert d["suspended_at"] is None
    ev = d["recent_events"][0]
    assert ev["event_type"] == "user_reinstated"


def test_reinstate_not_suspended_conflict(client: TestClient) -> None:
    user_id, _, _ = _make_user()
    r = client.post(f"/v1/admin/users/{user_id}/reinstate", json={}, headers=_ADMIN_HDR)
    assert r.status_code == 409


# ── Events pagination ─────────────────────────────────────────────────────────

def test_events_pagination(client: TestClient) -> None:
    user_id, _, _ = _make_user()
    # Generate 3 events
    client.patch(f"/v1/admin/users/{user_id}/plan", json={"plan": "trader"}, headers=_ADMIN_HDR)
    client.post(f"/v1/admin/users/{user_id}/credits", json={"delta": 5}, headers=_ADMIN_HDR)
    client.post(f"/v1/admin/users/{user_id}/suspend", json={}, headers=_ADMIN_HDR)

    r = client.get(f"/v1/admin/users/{user_id}/events?limit=2&offset=0", headers=_ADMIN_HDR)
    assert r.status_code == 200
    d = r.json()
    assert d["total"] == 3
    assert len(d["events"]) == 2
    assert d["limit"] == 2
    assert d["offset"] == 0

    r2 = client.get(f"/v1/admin/users/{user_id}/events?limit=2&offset=2", headers=_ADMIN_HDR)
    assert len(r2.json()["events"]) == 1


# ── Suspension enforcement in get_current_user ────────────────────────────────

def test_suspended_user_gets_403_on_authenticated_route() -> None:
    """A suspended user's scaffold token is still valid but get_current_user
    raises 403 before the route handler runs."""
    from app.api.mandate import router as mandate_router
    from app.db import get_session
    from app.db.models import User
    from datetime import datetime, timezone
    from sqlalchemy import select

    app = FastAPI()
    app.include_router(mandate_router)
    client = TestClient(app, raise_server_exceptions=False)

    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)

    # Suspend the user directly in the DB
    with get_session() as s:
        row = s.execute(select(User).where(User.id == user.id)).scalar_one()
        row.suspended_at = datetime.now(timezone.utc)

    # Authenticated route should now return 403
    r = client.get(
        f"/v1/mandate/{user.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "account_suspended"
