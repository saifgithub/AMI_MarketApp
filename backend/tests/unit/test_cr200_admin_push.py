"""CR200 — admin push console API.

Covers: preview by email + by id (devices + push_configured), 404 on
unknown target, 400 on neither; send writes the durable notifications row,
returns the real push_status verbatim (not_configured when OneSignal keys
are absent, sent when the mocked call succeeds), and records an
admin_audit row.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.admin_push import router as push_router
from app.core.config import settings
from app.db import get_session
from app.db.models import AdminAuditRow, NotificationRow, User
from app.services import notification_service
from app.services.auth_service import AuthService

_SECRET = "test-admin-secret-abc123"
_HDR = {"Authorization": f"Bearer {_SECRET}"}


@pytest.fixture(autouse=True)
def _set_admin_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_secret", _SECRET)


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(push_router)
    return TestClient(app, raise_server_exceptions=False)


def _make_user(email: str | None = None) -> str:
    auth = AuthService()
    user, _t, _ = auth.ensure_anonymous(device_user_id=None)
    if email:
        with get_session() as s:
            row = s.execute(select(User).where(User.id == user.id)).scalar_one()
            row.email = email
            row.is_anonymous = False
    return str(user.id)


def test_preview_by_email(client: TestClient) -> None:
    email = f"push-{uuid4().hex[:8]}@example.com"
    user_id = _make_user(email)
    r = client.post("/v1/admin/push/preview", json={"email": email}, headers=_HDR)
    assert r.status_code == 200
    data = r.json()
    assert data["user"]["id"] == user_id
    assert data["devices"] == []
    assert data["push_configured"] is False


def test_preview_by_id_and_errors(client: TestClient) -> None:
    user_id = _make_user()
    assert client.post(
        "/v1/admin/push/preview", json={"user_id": user_id}, headers=_HDR,
    ).status_code == 200
    assert client.post(
        "/v1/admin/push/preview", json={"user_id": str(uuid4())}, headers=_HDR,
    ).status_code == 404
    assert client.post(
        "/v1/admin/push/preview", json={"email": "nobody@nope.invalid"}, headers=_HDR,
    ).status_code == 404
    assert client.post("/v1/admin/push/preview", json={}, headers=_HDR).status_code == 400


def test_send_unconfigured_reports_not_configured(client: TestClient) -> None:
    user_id = _make_user()
    r = client.post(
        "/v1/admin/push",
        json={"user_id": user_id, "title": "Hi", "body": "from the console"},
        headers=_HDR,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["push_status"] == "not_configured"
    with get_session() as s:
        row = s.execute(
            select(NotificationRow).where(NotificationRow.id == data["notification_id"])
        ).scalar_one()
        assert row.title == "Hi"
        assert row.type == "admin_message"
        audit = s.execute(
            select(AdminAuditRow).where(
                AdminAuditRow.action == "push_sent",
                AdminAuditRow.target == user_id,
            )
        ).scalars().all()
    assert len(audit) == 1
    assert audit[0].payload["push_status"] == "not_configured"


def test_send_success_path(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = _make_user()
    monkeypatch.setattr(settings, "onesignal_app_id", "app-id")
    monkeypatch.setattr(settings, "onesignal_rest_key", "rest-key")

    class _Resp:
        status_code = 200
        text = '{"id": "push-1"}'

        def json(self) -> dict:
            return {"id": "push-1"}

    monkeypatch.setattr(notification_service.httpx, "post", lambda *a, **kw: _Resp())
    r = client.post(
        "/v1/admin/push",
        json={
            "user_id": user_id, "title": "Deep", "body": "link test",
            "route": "/room", "ticker": "AAPL",
        },
        headers=_HDR,
    )
    assert r.status_code == 200
    assert r.json()["push_status"] == "sent"
    with get_session() as s:
        row = s.execute(
            select(NotificationRow).where(
                NotificationRow.id == r.json()["notification_id"]
            )
        ).scalar_one()
        assert row.deep_link == {"route": "/room", "ticker": "AAPL"}


def test_send_unknown_user_404(client: TestClient) -> None:
    r = client.post(
        "/v1/admin/push",
        json={"user_id": str(uuid4()), "title": "x", "body": "y"},
        headers=_HDR,
    )
    assert r.status_code == 404
