"""CR200 — admin bug triage API.

Covers: list + counts + status filter, detail, atomic claim (double-claim
409 — the /fix-bugs coexistence contract), resolve requires a note and 409s
when already resolved, reopen releases the claim and clears resolution
fields while preserving acknowledged_at, attachment 404s (none / missing
file / traversal).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.admin_bugs import router as bugs_router
from app.core.config import settings
from app.db import get_session, init_schema
from app.db.models import BugReportRow

_SECRET = "test-admin-secret-abc123"
_HDR = {"Authorization": f"Bearer {_SECRET}"}


@pytest.fixture(autouse=True)
def _set_admin_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_secret", _SECRET)


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(bugs_router)
    return TestClient(app, raise_server_exceptions=False)


def _make_bug(status: str = "open", **kw) -> str:
    init_schema()
    row = BugReportRow(
        id=uuid4(),
        user_id=None,
        category=kw.get("category", "ui"),
        title=kw.get("title", "button misaligned"),
        steps=kw.get("steps"),
        app_version="0.1.0+70",
        platform="ios",
        status=status,
        assigned_branch=kw.get("assigned_branch"),
        attachment_path=kw.get("attachment_path"),
        attachment_mime=kw.get("attachment_mime"),
        acknowledged_at=kw.get("acknowledged_at"),
        created_at=datetime.now(timezone.utc),
    )
    with get_session() as s:
        s.add(row)
    return str(row.id)


def _row(bug_id: str) -> BugReportRow:
    with get_session() as s:
        return s.execute(
            select(BugReportRow).where(BugReportRow.id == bug_id)
        ).scalar_one()


def test_list_counts_and_filter(client: TestClient) -> None:
    a = _make_bug("open")
    _make_bug("resolved")
    r = client.get("/v1/admin/bugs", headers=_HDR)
    assert r.status_code == 200
    data = r.json()
    assert data["counts"]["open"] >= 1
    assert data["counts"]["resolved"] >= 1
    r = client.get("/v1/admin/bugs?status=open", headers=_HDR)
    assert all(b["status"] == "open" for b in r.json()["bugs"])
    assert a in [b["id"] for b in r.json()["bugs"]]
    assert client.get("/v1/admin/bugs?status=nope", headers=_HDR).status_code == 400


def test_claim_is_atomic_double_claim_409(client: TestClient) -> None:
    bug_id = _make_bug("open")
    r = client.post(
        f"/v1/admin/bugs/{bug_id}/claim", json={"branch": "fix/a"}, headers=_HDR,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "in_progress"
    assert r.json()["assigned_branch"] == "fix/a"
    # Second claimer loses — same guarded-UPDATE semantics as /fix-bugs psql.
    r = client.post(
        f"/v1/admin/bugs/{bug_id}/claim", json={"branch": "fix/b"}, headers=_HDR,
    )
    assert r.status_code == 409
    assert _row(bug_id).assigned_branch == "fix/a"


def test_resolve_requires_note_and_409_when_resolved(client: TestClient) -> None:
    bug_id = _make_bug("in_progress")
    r = client.post(f"/v1/admin/bugs/{bug_id}/resolve", json={"note": ""}, headers=_HDR)
    assert r.status_code == 422
    r = client.post(
        f"/v1/admin/bugs/{bug_id}/resolve", json={"note": "fixed in +71"}, headers=_HDR,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "resolved"
    assert _row(bug_id).resolved_at is not None
    r = client.post(
        f"/v1/admin/bugs/{bug_id}/resolve", json={"note": "again"}, headers=_HDR,
    )
    assert r.status_code == 409


def test_reopen_releases_claim_preserves_ack(client: TestClient) -> None:
    ack = datetime.now(timezone.utc)
    bug_id = _make_bug("resolved", assigned_branch="fix/x", acknowledged_at=ack)
    r = client.post(f"/v1/admin/bugs/{bug_id}/reopen", headers=_HDR)
    assert r.status_code == 200
    row = _row(bug_id)
    assert row.status == "open"
    assert row.assigned_branch is None
    assert row.resolution_note is None
    assert row.acknowledged_at is not None
    assert client.post(f"/v1/admin/bugs/{bug_id}/reopen", headers=_HDR).status_code == 409


def test_attachment_paths(client: TestClient, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "bug_attachments_dir", str(tmp_path))
    no_attach = _make_bug("open")
    assert client.get(f"/v1/admin/bugs/{no_attach}/attachment", headers=_HDR).status_code == 404
    (tmp_path / "shot.png").write_bytes(b"\x89PNG fake")
    with_attach = _make_bug(
        "open", attachment_path="shot.png", attachment_mime="image/png",
    )
    r = client.get(f"/v1/admin/bugs/{with_attach}/attachment", headers=_HDR)
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    traversal = _make_bug("open", attachment_path="../../etc/passwd")
    assert client.get(f"/v1/admin/bugs/{traversal}/attachment", headers=_HDR).status_code == 404


def test_missing_bug_404(client: TestClient) -> None:
    assert client.get(f"/v1/admin/bugs/{uuid4()}", headers=_HDR).status_code == 404
