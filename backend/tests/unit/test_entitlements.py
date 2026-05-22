"""Tests for BL11 — trial-end entitlement gate (AT:R33).

Covers:
  - effective_plan() pure function across the 5 meaningful states
  - effective_plan_for_user() DB lookup variant
  - admin user detail surfaces effective_plan + trial_active fields
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.core.config import settings
from app.db import get_session
from app.db.models import User
from app.schemas.mandate import Plan
from app.services.auth_service import AuthService
from app.services.entitlements import (
    effective_plan,
    effective_plan_for_user,
    is_trial_active,
)

_SECRET = "test-admin-secret-bl11"
_ADMIN_HDR = {"Authorization": f"Bearer {_SECRET}"}


@pytest.fixture(autouse=True)
def _set_admin_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_secret", _SECRET)


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(admin_router)
    return TestClient(app, raise_server_exceptions=False)


# ── Pure function ──────────────────────────────────────────────────────


def test_effective_plan_floor_pass_no_trial_unchanged() -> None:
    assert effective_plan(Plan.FLOOR_PASS, None) == Plan.FLOOR_PASS


def test_effective_plan_active_trial_promotes_floor_pass_to_trial_trader() -> None:
    """Auto-claim path: plan stays FLOOR_PASS but trial is active → user
    gets TRIAL_TRADER benefits."""
    future = datetime.now(timezone.utc) + timedelta(days=3)
    assert effective_plan(Plan.FLOOR_PASS, future) == Plan.TRIAL_TRADER


def test_effective_plan_active_trial_keeps_trial_trader() -> None:
    """Admin-granted path: plan=TRIAL_TRADER + active trial stays TRIAL_TRADER."""
    future = datetime.now(timezone.utc) + timedelta(days=3)
    assert effective_plan(Plan.TRIAL_TRADER, future) == Plan.TRIAL_TRADER


def test_effective_plan_expired_trial_downgrades_to_floor_pass() -> None:
    """The actual BL11 hole: expired trial must drop to floor_pass."""
    past = datetime.now(timezone.utc) - timedelta(days=1)
    assert effective_plan(Plan.TRIAL_TRADER, past) == Plan.FLOOR_PASS


def test_effective_plan_paid_plan_not_downgraded_even_with_active_trial() -> None:
    """TRADER user happens to also have an active trial → stays TRADER."""
    future = datetime.now(timezone.utc) + timedelta(days=3)
    assert effective_plan(Plan.TRADER, future) == Plan.TRADER


def test_effective_plan_paid_plan_unaffected_by_expired_trial() -> None:
    past = datetime.now(timezone.utc) - timedelta(days=1)
    assert effective_plan(Plan.TRADER, past) == Plan.TRADER


def test_is_trial_active_basic() -> None:
    assert is_trial_active(None) is False
    assert is_trial_active(datetime.now(timezone.utc) - timedelta(days=1)) is False
    assert is_trial_active(datetime.now(timezone.utc) + timedelta(days=1)) is True


# ── DB lookup variant ──────────────────────────────────────────────────


def test_effective_plan_for_user_returns_floor_pass_for_expired_trial() -> None:
    auth = AuthService()
    user, _, _ = auth.ensure_anonymous(device_user_id=None)
    with get_session() as s:
        row = s.execute(select(User).where(User.id == user.id)).scalar_one()
        row.plan = "trial_trader"
        row.trial_expires_at = datetime.now(timezone.utc) - timedelta(days=1)

    assert effective_plan_for_user(user.id) == Plan.FLOOR_PASS


def test_effective_plan_for_user_returns_trial_trader_for_active_trial() -> None:
    auth = AuthService()
    user, _, _ = auth.ensure_anonymous(device_user_id=None)
    with get_session() as s:
        row = s.execute(select(User).where(User.id == user.id)).scalar_one()
        row.trial_expires_at = datetime.now(timezone.utc) + timedelta(days=3)
        # leave plan=floor_pass — the auto-claim path

    assert effective_plan_for_user(user.id) == Plan.TRIAL_TRADER


def test_effective_plan_for_user_unknown_user_returns_floor_pass() -> None:
    assert effective_plan_for_user(uuid4()) == Plan.FLOOR_PASS


# ── Admin surface ──────────────────────────────────────────────────────


def test_admin_user_detail_surfaces_effective_plan_for_expired_trial(
    client: TestClient,
) -> None:
    auth = AuthService()
    user, _, _ = auth.ensure_anonymous(device_user_id=None)
    with get_session() as s:
        row = s.execute(select(User).where(User.id == user.id)).scalar_one()
        row.plan = "trial_trader"
        row.trial_expires_at = datetime.now(timezone.utc) - timedelta(days=1)

    r = client.get(f"/v1/admin/users/{user.id}", headers=_ADMIN_HDR)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["plan"] == "trial_trader"
    assert body["effective_plan"] == "floor_pass"
    assert body["trial_active"] is False


def test_admin_user_detail_active_trial_shows_matching_effective_plan(
    client: TestClient,
) -> None:
    auth = AuthService()
    user, _, _ = auth.ensure_anonymous(device_user_id=None)
    with get_session() as s:
        row = s.execute(select(User).where(User.id == user.id)).scalar_one()
        row.plan = "trial_trader"
        row.trial_expires_at = datetime.now(timezone.utc) + timedelta(days=3)

    r = client.get(f"/v1/admin/users/{user.id}", headers=_ADMIN_HDR)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["effective_plan"] == "trial_trader"
    assert body["trial_active"] is True
