"""CR200 — admin_audit: every admin write records an attributed audit row.

Covers: plan change, credits, suspend/reinstate, trial grant → one
admin_audit row each with operator "static_bearer" (bearer path); audit rows
ride the caller's transaction (same-session semantics).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.admin import router as admin_router
from app.core.config import settings
from app.db import get_session
from app.db.models import AdminAuditRow
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


def _make_user():
    auth = AuthService()
    user, _token, _ = auth.ensure_anonymous(device_user_id=None)
    return user.id


def _audit_rows(action: str) -> list[AdminAuditRow]:
    with get_session() as s:
        return list(
            s.execute(
                select(AdminAuditRow).where(AdminAuditRow.action == action)
            ).scalars()
        )


def test_plan_change_writes_audit_row(client: TestClient) -> None:
    user_id = _make_user()
    r = client.patch(
        f"/v1/admin/users/{user_id}/plan",
        json={"plan": "trader", "note": "test"},
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 200
    rows = [x for x in _audit_rows("plan_changed") if x.target == str(user_id)]
    assert len(rows) == 1
    assert rows[0].operator == "static_bearer"
    assert rows[0].auth_kind == "static_bearer"
    assert rows[0].payload["to"] == "trader"


def test_credits_writes_audit_row(client: TestClient) -> None:
    user_id = _make_user()
    r = client.post(
        f"/v1/admin/users/{user_id}/credits",
        json={"delta": 25, "note": "goodwill"},
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 200
    rows = [x for x in _audit_rows("credits_added") if x.target == str(user_id)]
    assert len(rows) == 1
    assert rows[0].payload["delta"] == 25


def test_suspend_reinstate_write_audit_rows(client: TestClient) -> None:
    user_id = _make_user()
    r = client.post(
        f"/v1/admin/users/{user_id}/suspend",
        json={"note": "abuse"}, headers=_ADMIN_HDR,
    )
    assert r.status_code == 200
    r = client.post(
        f"/v1/admin/users/{user_id}/reinstate",
        json={"note": "resolved"}, headers=_ADMIN_HDR,
    )
    assert r.status_code == 200
    assert [x for x in _audit_rows("user_suspended") if x.target == str(user_id)]
    assert [x for x in _audit_rows("user_reinstated") if x.target == str(user_id)]


def test_trial_grant_writes_audit_row(client: TestClient) -> None:
    user_id = _make_user()
    r = client.post(
        f"/v1/admin/users/{user_id}/trial",
        json={"days": 7, "note": "welcome"}, headers=_ADMIN_HDR,
    )
    assert r.status_code == 200
    rows = [x for x in _audit_rows("trial_granted") if x.target == str(user_id)]
    assert len(rows) == 1
    assert rows[0].payload["days"] == 7


def test_failed_write_leaves_no_audit_row(client: TestClient) -> None:
    missing = uuid4()
    r = client.patch(
        f"/v1/admin/users/{missing}/plan",
        json={"plan": "trader"}, headers=_ADMIN_HDR,
    )
    assert r.status_code == 404
    assert not [x for x in _audit_rows("plan_changed") if x.target == str(missing)]
