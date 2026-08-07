"""CR121 — POST /v1/admin/release-floor: the write side's operational
footgun guard (refuse a min_build above the highest build ever observed,
unless force=true) plus the ordinary write happy-path.

Floor-resolution + read-endpoint + 426-enforcement tests live in
test_cr121_release_floor.py.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin import router as admin_router
from app.core.config import settings
from app.services.auth_service import AuthService

_SECRET = "cr121-admin-secret"
_HDR = {"Authorization": f"Bearer {_SECRET}"}


@pytest.fixture(autouse=True)
def _set_admin_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_secret", _SECRET)


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(admin_router)
    return TestClient(app, raise_server_exceptions=False)


def _seed_observed_build(version: str) -> None:
    """Give the server ONE piece of evidence that `version` has actually
    been installed, via the same path a real bootstrap call takes — also
    upserts a user_devices row so both scanned columns are exercised."""
    AuthService().ensure_anonymous(
        device_user_id=None,
        app_version=version,
        device_install_id=uuid4(),
    )


def _payload(min_build: int, **overrides) -> dict:
    body = {
        "min_build": min_build,
        "headline": "Update required",
        "body_en": "This build is no longer supported.",
    }
    body.update(overrides)
    return body


def test_requires_admin_secret(client: TestClient) -> None:
    r = client.post("/v1/admin/release-floor", json=_payload(10))
    assert r.status_code == 403


def test_footgun_refuses_min_build_above_highest_observed(client: TestClient) -> None:
    # No user has ever bootstrapped — highest observed build is 0.
    r = client.post("/v1/admin/release-floor", headers=_HDR, json=_payload(10))
    assert r.status_code == 409
    body = r.json()["detail"]
    assert body["error"] == "min_build_exceeds_highest_observed"
    assert body["min_build"] == 10
    assert body["highest_observed_build"] == 0


def test_footgun_allows_min_build_at_or_below_highest_observed(
    client: TestClient,
) -> None:
    _seed_observed_build("0.1.0+69")
    r = client.post("/v1/admin/release-floor", headers=_HDR, json=_payload(69))
    assert r.status_code == 200
    body = r.json()
    assert body["min_build"] == 69
    assert body["highest_observed_build"] == 69

    r2 = client.post("/v1/admin/release-floor", headers=_HDR, json=_payload(40))
    assert r2.status_code == 200


def test_force_overrides_the_footgun_refusal(client: TestClient) -> None:
    r = client.post(
        "/v1/admin/release-floor", headers=_HDR, json=_payload(999, force=True),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["min_build"] == 999
    assert body["active"] is True
    assert body["highest_observed_build"] == 0


def test_duplicate_min_build_is_rejected(client: TestClient) -> None:
    _seed_observed_build("0.1.0+69")
    r1 = client.post("/v1/admin/release-floor", headers=_HDR, json=_payload(69))
    assert r1.status_code == 200
    r2 = client.post("/v1/admin/release-floor", headers=_HDR, json=_payload(69))
    assert r2.status_code == 409
    assert r2.json()["detail"]["error"] == "min_build_already_exists"


def test_successful_raise_carries_the_per_raise_message(client: TestClient) -> None:
    _seed_observed_build("0.1.0+69")
    r = client.post(
        "/v1/admin/release-floor",
        headers=_HDR,
        json=_payload(
            69,
            recommended_build=72,
            headline="Security fix required",
            body_en="Please update immediately.",
            body_ar="يرجى التحديث فورا.",
            body_ms="Sila kemas kini segera.",
            created_by="saiful",
        ),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["recommended_build"] == 72
    assert body["headline"] == "Security fix required"
    assert body["body_ar"] == "يرجى التحديث فورا."
    assert body["body_ms"] == "Sila kemas kini segera."
    assert body["created_by"] == "saiful"


def test_config_check_surfaces_the_active_floor(client: TestClient) -> None:
    r0 = client.get("/v1/admin/config-check", headers=_HDR)
    assert r0.json()["client_release_floor_configured"] is False
    assert r0.json()["client_release_floor_min_build"] is None

    _seed_observed_build("0.1.0+69")
    client.post("/v1/admin/release-floor", headers=_HDR, json=_payload(69))

    r1 = client.get("/v1/admin/config-check", headers=_HDR)
    assert r1.json()["client_release_floor_configured"] is True
    assert r1.json()["client_release_floor_min_build"] == 69
