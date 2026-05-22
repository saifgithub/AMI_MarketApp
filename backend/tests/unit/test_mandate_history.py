"""Tests for BL5 — mandate history API (AT:R33).

Covers:
  - GET /v1/mandate/{u}/versions lists every persisted version newest first,
    flags is_current, decorates with the matching mandate_edit summary
  - GET /v1/mandate/{u}/versions/{v} returns the snapshot or 404
  - POST /v1/mandate/{u}/rollback/{v} creates a new current version,
    preserves old versions, writes a journal entry
  - Ownership: cross-user access 403s
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth import router as auth_router
from app.api.mandate import router as mandate_router
from app.schemas.journal import EntryType
from app.services.auth_service import AuthService
from app.services.journal_store import get_journal_store
from app.services.mandate_store import get_mandate_store


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(mandate_router)
    return TestClient(app, raise_server_exceptions=False)


def _new_user() -> tuple[UUID, str, dict]:
    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)
    return user.id, token, {"Authorization": f"Bearer {token}"}


# ── list_versions ──────────────────────────────────────────────────────


def test_list_versions_empty_when_no_mandate(client: TestClient) -> None:
    user_id, _, hdr = _new_user()
    r = client.get(f"/v1/mandate/{user_id}/versions", headers=hdr)
    assert r.status_code == 200
    assert r.json() == {"versions": []}


def test_list_versions_returns_all_versions_newest_first(
    client: TestClient,
) -> None:
    user_id, _, hdr = _new_user()
    # Three PATCHes → three versions (v1, v2, v3 — upsert starts at v1).
    for risk in (3, 4, 5):
        r = client.patch(
            f"/v1/mandate/{user_id}",
            json={"risk_score": risk},
            headers=hdr,
        )
        assert r.status_code == 200

    r = client.get(f"/v1/mandate/{user_id}/versions", headers=hdr)
    assert r.status_code == 200
    versions = r.json()["versions"]
    assert [v["version"] for v in versions] == [3, 2, 1]
    assert versions[0]["is_current"] is True
    assert versions[1]["is_current"] is False
    assert versions[2]["is_current"] is False


def test_list_versions_decorates_with_journal_change_summary(
    client: TestClient,
) -> None:
    user_id, _, hdr = _new_user()
    r = client.patch(
        f"/v1/mandate/{user_id}",
        json={"risk_score": 5},
        headers=hdr,
    )
    assert r.status_code == 200

    versions = client.get(
        f"/v1/mandate/{user_id}/versions", headers=hdr,
    ).json()["versions"]
    # v1 is the post-PATCH version with the change_summary populated.
    v1 = next(v for v in versions if v["version"] == 1)
    assert v1["change_summary"] is not None
    assert "risk score" in v1["change_summary"]


# ── get_version ────────────────────────────────────────────────────────


def test_get_version_returns_snapshot(client: TestClient) -> None:
    user_id, _, hdr = _new_user()
    # v1 with risk_score=4.
    client.patch(
        f"/v1/mandate/{user_id}", json={"risk_score": 4}, headers=hdr,
    )
    # v2 with risk_score=5.
    client.patch(
        f"/v1/mandate/{user_id}", json={"risk_score": 5}, headers=hdr,
    )

    r = client.get(f"/v1/mandate/{user_id}/versions/1", headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json()["risk_score"] == 4
    assert r.json()["version"] == 1


def test_get_version_missing_returns_404(client: TestClient) -> None:
    user_id, _, hdr = _new_user()
    r = client.get(f"/v1/mandate/{user_id}/versions/99", headers=hdr)
    assert r.status_code == 404


# ── rollback ───────────────────────────────────────────────────────────


def test_rollback_creates_new_current_mirroring_target(
    client: TestClient,
) -> None:
    user_id, _, hdr = _new_user()
    client.patch(f"/v1/mandate/{user_id}", json={"risk_score": 4}, headers=hdr)
    client.patch(f"/v1/mandate/{user_id}", json={"risk_score": 5}, headers=hdr)
    # State: v1 (risk=4), v2 (risk=5, current).

    r = client.post(f"/v1/mandate/{user_id}/rollback/1", headers=hdr)
    assert r.status_code == 200, r.text
    new_current = r.json()
    assert new_current["risk_score"] == 4
    assert new_current["version"] == 3  # bumped past v2

    # All three versions still listed; v3 is current.
    versions = client.get(
        f"/v1/mandate/{user_id}/versions", headers=hdr,
    ).json()["versions"]
    assert [v["version"] for v in versions] == [3, 2, 1]
    assert versions[0]["is_current"] is True


def test_rollback_writes_journal_entry_tagged_rollback(
    client: TestClient,
) -> None:
    user_id, _, hdr = _new_user()
    client.patch(f"/v1/mandate/{user_id}", json={"risk_score": 5}, headers=hdr)
    client.post(f"/v1/mandate/{user_id}/rollback/1", headers=hdr)

    entries, _, _ = get_journal_store().list_for_user(
        user_id, entry_type=EntryType.MANDATE_EDIT, limit=20,
    )
    rollback_entries = [e for e in entries if "rollback" in e.tags]
    assert len(rollback_entries) == 1
    assert rollback_entries[0].payload["rolled_back_to_version"] == 1


def test_rollback_missing_version_returns_404(client: TestClient) -> None:
    user_id, _, hdr = _new_user()
    r = client.post(f"/v1/mandate/{user_id}/rollback/99", headers=hdr)
    assert r.status_code == 404


# ── ownership ──────────────────────────────────────────────────────────


def test_list_versions_blocks_cross_user(client: TestClient) -> None:
    _, _, hdr = _new_user()
    other = uuid4()
    r = client.get(f"/v1/mandate/{other}/versions", headers=hdr)
    assert r.status_code == 403


def test_rollback_blocks_cross_user(client: TestClient) -> None:
    _, _, hdr = _new_user()
    other = uuid4()
    r = client.post(f"/v1/mandate/{other}/rollback/1", headers=hdr)
    assert r.status_code == 403
