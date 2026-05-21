"""Tests for BL1 — device + build context on /v1/auth/anon (AT:R33).

Covers: device_model + os_version + last_app_version persisted on first
bootstrap, refreshed on re-bootstrap from the same Bearer, and surfaced
through the admin user-detail endpoint.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.core.config import settings
from app.db import get_session
from app.db.models import User
from app.services.auth_service import AuthService

_SECRET = "test-admin-secret-bl1"
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


def test_anon_persists_device_info_on_first_bootstrap(client: TestClient) -> None:
    r = client.post(
        "/v1/auth/anon",
        json={
            "device_model": "iPhone15,2",
            "os_version": "iOS 18.2",
            "app_version": "0.1.0+26",
        },
    )
    assert r.status_code == 200
    user_id = UUID(r.json()["user"]["id"])

    with get_session() as s:
        row = s.execute(select(User).where(User.id == user_id)).scalar_one()
        assert row.device_model == "iPhone15,2"
        assert row.os_version == "iOS 18.2"
        assert row.last_app_version == "0.1.0+26"


def test_anon_omits_device_info_when_not_supplied(client: TestClient) -> None:
    """Backwards-compat: old clients don't send the fields → still bootstrap."""
    r = client.post("/v1/auth/anon", json={})
    assert r.status_code == 200
    user_id = UUID(r.json()["user"]["id"])

    with get_session() as s:
        row = s.execute(select(User).where(User.id == user_id)).scalar_one()
        assert row.device_model is None
        assert row.os_version is None
        assert row.last_app_version is None


def test_anon_refreshes_app_version_on_rebootstrap(client: TestClient) -> None:
    """Re-bootstrapping with the same Bearer + a new app_version updates
    the row (typical case: user upgraded the app)."""
    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(
        device_user_id=None, app_version="0.1.0+25",
    )

    r = client.post(
        "/v1/auth/anon",
        json={
            "device_user_id": str(user.id),
            "device_model": "iPhone15,2",
            "os_version": "iOS 18.3",
            "app_version": "0.1.0+27",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert UUID(r.json()["user"]["id"]) == user.id

    with get_session() as s:
        row = s.execute(select(User).where(User.id == user.id)).scalar_one()
        assert row.device_model == "iPhone15,2"
        assert row.os_version == "iOS 18.3"
        assert row.last_app_version == "0.1.0+27"


def test_admin_detail_surfaces_device_info(client: TestClient) -> None:
    """The /v1/admin/users/{id} detail response includes the new fields so
    Saiful can see 'what build is this anonymous tester on?' in the UI."""
    r = client.post(
        "/v1/auth/anon",
        json={
            "device_model": "iPhone15,2",
            "os_version": "iOS 18.2",
            "app_version": "0.1.0+26",
        },
    )
    assert r.status_code == 200
    user_id = r.json()["user"]["id"]

    r2 = client.get(f"/v1/admin/users/{user_id}", headers=_ADMIN_HDR)
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["device_model"] == "iPhone15,2"
    assert body["os_version"] == "iOS 18.2"
    assert body["last_app_version"] == "0.1.0+26"
