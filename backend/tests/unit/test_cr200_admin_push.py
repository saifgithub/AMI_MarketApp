"""CR200 — admin push console API; CR200-R003 — audience (broadcast) mode.

Covers: preview by email + by id (devices + push_configured), 404 on
unknown target, 400 on neither; send writes the durable notifications row,
returns the real push_status verbatim (not_configured when OneSignal keys
are absent, sent when the mocked call succeeds), and records an
admin_audit row.

Audience mode: preview with {"mode":"all"} counts only real testers
(CR035 synthetics, seed-burst rows, by-id exclusions, desks, suspended
excluded — same fixtures as test_cr102_resolve_audience); broadcast send
loops notify() per resolved user, returns {recipient_count, status_counts},
records ONE admin_audit "push_broadcast" row, and a per-user failure lands
in status_counts as "error" without aborting the loop (CR040).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.admin_push import router as push_router
from app.core.config import settings
from app.db import get_session
from app.db.models import AdminAuditRow, NotificationRow, User
from app.services import notification_service
from app.services.admin_analytics import _EXCLUDED_USER_IDS as EXCLUDED_USER_IDS
from app.services.auth_service import AuthService
from app.services.notification_service import NotifyResult

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


# ── CR200-R003 — audience (broadcast) mode ────────────────────────────────────


def _seed_user(
    *,
    created_at: datetime | None = None,
    device_model: str | None = "iPhone18,1",
    last_app_version: str | None = "0.1.0+54",
    suspended: bool = False,
    is_desk: bool = False,
    user_id: UUID | None = None,
) -> UUID:
    """Direct User-row seed, mirroring test_cr102_resolve_audience so the
    synthetic/seed/desk/suspended cohorts the audience filter must exclude
    are built exactly the way the CR102 exclusion tests build them."""
    uid = user_id or uuid4()
    now = datetime.now(UTC)
    with get_session() as s:
        s.add(User(
            id=uid,
            created_at=created_at or now,
            device_model=device_model,
            last_app_version=last_app_version,
            suspended_at=now if suspended else None,
            is_desk=is_desk,
            desk_key=f"desk-{uid.hex[:8]}" if is_desk else None,
        ))
    return uid


def test_preview_audience_all_counts_real_users_only(client: TestClient) -> None:
    _seed_user()
    _seed_user()
    _seed_user(last_app_version="room-benchmark")              # CR035 synthetic
    _seed_user(                                                # seed-burst shape
        created_at=datetime(2026, 5, 24, 5, 10, 30, tzinfo=UTC),
        device_model=None, last_app_version=None,
    )
    _seed_user(user_id=sorted(EXCLUDED_USER_IDS, key=str)[0])  # by-id exclusion
    _seed_user(is_desk=True)                                   # CR109 house desk
    _seed_user(suspended=True)
    r = client.post(
        "/v1/admin/push/preview",
        json={"audience": {"mode": "all"}}, headers=_HDR,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["recipient_count"] == 2
    assert data["audience_mode"] == "all"
    assert data["push_configured"] is False
    assert "user" not in data and "devices" not in data


def test_send_broadcast_notifies_each_recipient_and_audits_once(
    client: TestClient,
) -> None:
    real_a = _seed_user()
    real_b = _seed_user()
    _seed_user(suspended=True)  # resolved out — never notified
    r = client.post(
        "/v1/admin/push",
        json={
            "audience": {"mode": "all"},
            "title": "Blast", "body": "to everyone real",
            "route": "/inbox", "ticker": "AAPL",
        },
        headers=_HDR,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["recipient_count"] == 2
    assert data["status_counts"] == {"not_configured": 2}
    assert "notification_id" not in data and "push_status" not in data
    with get_session() as s:
        rows = s.execute(select(NotificationRow)).scalars().all()
        assert sorted(str(row.user_id) for row in rows) == sorted(
            [str(real_a), str(real_b)]
        )
        assert all(row.title == "Blast" for row in rows)
        assert all(row.deep_link == {"route": "/inbox", "ticker": "AAPL"} for row in rows)
        audit = s.execute(
            select(AdminAuditRow).where(AdminAuditRow.action == "push_broadcast")
        ).scalars().all()
    assert len(audit) == 1
    assert audit[0].target == "audience:all"
    assert audit[0].payload["recipient_count"] == 2
    assert audit[0].payload["status_counts"] == {"not_configured": 2}
    assert audit[0].payload["title"] == "Blast"


def test_xor_validation_rejects_ambiguous_and_empty_targets(
    client: TestClient,
) -> None:
    user_id = _make_user()
    both = {
        "user_id": user_id, "audience": {"mode": "all"}, "title": "x", "body": "y",
    }
    assert client.post("/v1/admin/push", json=both, headers=_HDR).status_code == 422
    neither = {"title": "x", "body": "y"}
    assert client.post("/v1/admin/push", json=neither, headers=_HDR).status_code == 422
    assert client.post(
        "/v1/admin/push/preview",
        json={"user_id": user_id, "audience": {"mode": "all"}}, headers=_HDR,
    ).status_code == 422


def test_broadcast_partial_failure_reported_not_swallowed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    failing = _seed_user()
    ok = _seed_user()
    calls: list[str] = []

    def _fake_notify(*, user_id, **kwargs):
        calls.append(str(user_id))
        if user_id == failing:
            raise RuntimeError("boom")
        return NotifyResult(notification_id=uuid4(), push_status="sent")

    monkeypatch.setattr("app.api.admin_push.notify", _fake_notify)
    r = client.post(
        "/v1/admin/push",
        json={"audience": {"mode": "all"}, "title": "t", "body": "b"},
        headers=_HDR,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["recipient_count"] == 2
    assert data["status_counts"] == {"error": 1, "sent": 1}
    assert sorted(calls) == sorted([str(failing), str(ok)])
