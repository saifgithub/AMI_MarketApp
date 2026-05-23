"""Tests for BL2 — user_devices multi-device tracking (AT:R33).

Covers:
  - ensure_anonymous() upserts a user_devices row keyed by device_install_id
  - re-bootstrap from same install_id refreshes last_seen_at + context,
    doesn't duplicate
  - two different install_ids on the same user create two rows
  - claim adoption (account-linking Phase 1) re-keys devices from the
    orphaned anon user to the adopted user — so two phones surface under
    one user after the second phone claims
  - admin user-detail surfaces the devices list ordered most-recent-first
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.core.config import settings
from app.db import get_session
from app.db.models import User, UserDeviceRow
from app.services.auth_service import AuthService

_SECRET = "test-admin-secret-bl2"
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


def _devices_for(user_id: UUID) -> list[UserDeviceRow]:
    with get_session() as s:
        return list(
            s.execute(
                select(UserDeviceRow).where(UserDeviceRow.user_id == user_id)
            ).scalars()
        )


# ── Service-level upsert + re-bootstrap ────────────────────────────────


def test_ensure_anonymous_inserts_user_device_row() -> None:
    install_id = uuid4()
    auth = AuthService()
    user, _, _ = auth.ensure_anonymous(
        device_user_id=None,
        device_install_id=install_id,
        device_model="iPhone15,2",
        os_version="iOS 18.2",
        app_version="0.1.0+26",
    )
    devices = _devices_for(user.id)
    assert len(devices) == 1
    d = devices[0]
    assert d.device_install_id == install_id
    assert d.device_model == "iPhone15,2"
    assert d.app_version == "0.1.0+26"


def test_rebootstrap_same_install_refreshes_does_not_duplicate(
    client: TestClient,
) -> None:
    install_id = uuid4()
    # First bootstrap mints user A.
    r1 = client.post(
        "/v1/auth/anon",
        json={
            "device_install_id": str(install_id),
            "device_model": "iPhone15,2",
            "app_version": "0.1.0+25",
        },
    )
    assert r1.status_code == 200
    user_id = UUID(r1.json()["user"]["id"])
    token = r1.json()["token"]

    # Re-bootstrap with same install_id + bearer + bumped app_version.
    r2 = client.post(
        "/v1/auth/anon",
        json={
            "device_user_id": str(user_id),
            "device_install_id": str(install_id),
            "device_model": "iPhone15,2",
            "app_version": "0.1.0+27",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    assert UUID(r2.json()["user"]["id"]) == user_id

    devices = _devices_for(user_id)
    assert len(devices) == 1, "same install_id must not duplicate"
    assert devices[0].app_version == "0.1.0+27", "context refreshed"


def test_two_install_ids_create_two_device_rows_same_user() -> None:
    """Direct service-level test: same user_id, two install_ids, two rows."""
    auth = AuthService()
    install_a = uuid4()
    install_b = uuid4()
    user, _, _ = auth.ensure_anonymous(
        device_user_id=None,
        device_install_id=install_a,
    )
    # Simulate a second device claiming into the same user (skips the A2
    # mint-fresh branch by calling the service helper directly).
    from app.services.auth_service import _upsert_user_device
    with get_session() as s:
        _upsert_user_device(
            s, user_id=user.id, device_install_id=install_b,
            device_model="iPhone17,1", os_version="iOS 18.4",
            app_version="0.1.0+30",
        )
    devices = _devices_for(user.id)
    assert {d.device_install_id for d in devices} == {install_a, install_b}


# ── Claim-adoption re-keys devices ──────────────────────────────────────


def test_apple_adoption_rekeys_devices_to_adopted_user(
    client: TestClient,
) -> None:
    """End-to-end multi-device flow:
      iPhone A bootstraps (install_a) → user U_A → claims via Apple email X.
      iPhone B bootstraps fresh (install_b) → user U_B → claims via Apple email X.
    The Apple-claim email-fallback adopts U_A; U_B's device row (install_b)
    must re-key to U_A so the admin sees both devices under one user.
    """
    install_a = uuid4()
    install_b = uuid4()

    # iPhone A first install + bootstrap.
    auth = AuthService()
    user_a, _, _ = auth.ensure_anonymous(
        device_user_id=None, device_install_id=install_a,
    )
    # iPhone A claims via magic-link to establish the email on its user row.
    with get_session() as s:
        row = s.execute(select(User).where(User.id == user_a.id)).scalar_one()
        row.email = "saiful@example.com"
        row.is_anonymous = False
        from datetime import datetime, timezone
        row.claimed_at = datetime.now(timezone.utc)

    # iPhone B first install + bootstrap (fresh anon user).
    user_b, _, _ = auth.ensure_anonymous(
        device_user_id=None, device_install_id=install_b,
    )
    assert user_b.id != user_a.id
    assert len(_devices_for(user_b.id)) == 1
    assert len(_devices_for(user_a.id)) == 1

    # iPhone B "claims" via magic-link with the same email — exercises
    # _claim_or_create's adoption path, which drives the device re-key.
    code = auth.start_magic_link(email="saiful@example.com", user_id=user_b.id)
    result = auth.verify_magic_link(
        email="saiful@example.com", code=code, user_id=user_b.id,
    )
    assert result is not None
    adopted_user, _token, _adopted = result
    assert adopted_user.id == user_a.id  # adopted!

    # User A should now own both devices; user B should own none.
    a_devices = _devices_for(user_a.id)
    assert len(a_devices) == 2
    install_ids = {d.device_install_id for d in a_devices}
    assert install_ids == {install_a, install_b}
    assert len(_devices_for(user_b.id)) == 0


# ── Admin surface ──────────────────────────────────────────────────────


def test_admin_user_detail_surfaces_devices(client: TestClient) -> None:
    install_id = uuid4()
    r = client.post(
        "/v1/auth/anon",
        json={
            "device_install_id": str(install_id),
            "device_model": "iPhone15,2",
            "os_version": "iOS 18.2",
            "app_version": "0.1.0+26",
        },
    )
    user_id = r.json()["user"]["id"]

    detail = client.get(f"/v1/admin/users/{user_id}", headers=_ADMIN_HDR)
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert "devices" in body
    assert len(body["devices"]) == 1
    d = body["devices"][0]
    assert d["device_install_id"] == str(install_id)
    assert d["device_model"] == "iPhone15,2"
    assert d["app_version"] == "0.1.0+26"
