"""CR043 — the reporter-facing half of the bug lifecycle.

Covers GET /v1/feedback/updates and POST /v1/feedback/{id}/ack: which
reports surface, exactly once, and to whom. The cross-user cases are the
load-bearing ones — the user_id predicate in FeedbackStore is an
authorization check, not a convenience filter.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.feedback import router as feedback_router
from app.core.config import settings
from app.db import get_session
from app.db.models import BugReportRow
from app.schemas.feedback import BugReportResponse
from app.services.auth_service import _scaffold_token


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(settings, "bug_attachments_dir", str(tmp_path))
    app = FastAPI()
    app.include_router(feedback_router)
    return TestClient(app)


def _auth(user_id: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {_scaffold_token(user_id)}"}


def _make_report(
    user_id: UUID | None,
    *,
    status: str = "open",
    title: str = "Badge overlaps price",
    acknowledged: bool = False,
    note: str | None = None,
) -> UUID:
    now = datetime.now(timezone.utc)
    row = BugReportRow(
        user_id=user_id,
        category="ui_glitch",
        title=title,
        app_version="0.1.0+37",
        platform="ios",
        status=status,
        created_at=now,
        resolved_at=now if status == "resolved" else None,
        resolution_note=note,
        acknowledged_at=now if acknowledged else None,
    )
    with get_session() as s:
        s.add(row)
        s.flush()
        return row.id


def test_resolved_report_surfaces_once_then_goes_quiet(client: TestClient):
    user = uuid4()
    report_id = _make_report(
        user, status="resolved", note="Fixed in the latest build.",
    )

    r = client.get("/v1/feedback/updates", headers=_auth(user))
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body) == 1
    assert body[0]["id"] == str(report_id)
    assert body[0]["resolution_note"] == "Fixed in the latest build."

    ack = client.post(f"/v1/feedback/{report_id}/ack", headers=_auth(user))
    assert ack.status_code == 204, ack.text

    again = client.get("/v1/feedback/updates", headers=_auth(user))
    assert again.json() == []


def test_second_ack_is_a_404_not_a_double_delivery(client: TestClient):
    user = uuid4()
    report_id = _make_report(user, status="resolved")

    assert client.post(
        f"/v1/feedback/{report_id}/ack", headers=_auth(user)
    ).status_code == 204
    assert client.post(
        f"/v1/feedback/{report_id}/ack", headers=_auth(user)
    ).status_code == 404


@pytest.mark.parametrize(
    "status", ["open", "in_progress", "pending_review", "wont_fix"],
)
def test_only_resolved_notifies(client: TestClient, status: str):
    """pending_review means committed on a branch, not shipped. Telling the
    reporter it's fixed then invites them to retest against a server that
    still has the bug."""
    user = uuid4()
    _make_report(user, status=status)
    r = client.get("/v1/feedback/updates", headers=_auth(user))
    assert r.json() == []


def test_already_acknowledged_report_does_not_resurface(client: TestClient):
    """The migration backfills acknowledged_at on all 35 pre-existing
    terminal rows. This is the assertion that the backfill's intent holds."""
    user = uuid4()
    _make_report(user, status="resolved", acknowledged=True)
    r = client.get("/v1/feedback/updates", headers=_auth(user))
    assert r.json() == []


def test_one_user_cannot_read_anothers_reports(client: TestClient):
    author, stranger = uuid4(), uuid4()
    _make_report(author, status="resolved", title="Author's private report")

    r = client.get("/v1/feedback/updates", headers=_auth(stranger))
    assert r.status_code == 200
    assert r.json() == []


def test_one_user_cannot_ack_anothers_report(client: TestClient):
    author, stranger = uuid4(), uuid4()
    report_id = _make_report(author, status="resolved")

    hijack = client.post(
        f"/v1/feedback/{report_id}/ack", headers=_auth(stranger),
    )
    assert hijack.status_code == 404

    # And the author still gets their message.
    assert len(client.get("/v1/feedback/updates", headers=_auth(author)).json()) == 1


def test_unauthenticated_reads_are_rejected(client: TestClient):
    """Submit tolerates a missing user_id; the read paths cannot — an
    unscoped query would hand a stranger someone else's reports."""
    assert client.get("/v1/feedback/updates").status_code == 401
    assert client.post(f"/v1/feedback/{uuid4()}/ack").status_code == 401


def test_authorless_reports_reach_nobody(client: TestClient):
    """A report filed before the anon bootstrap completes has user_id=None
    and is structurally unnotifiable. It must not leak to an arbitrary
    caller."""
    _make_report(None, status="resolved")
    assert client.get("/v1/feedback/updates", headers=_auth(uuid4())).json() == []


def test_updates_are_ordered_oldest_first(client: TestClient):
    user = uuid4()
    _make_report(user, status="resolved", title="First")
    _make_report(user, status="resolved", title="Second")
    titles = [
        u["title"]
        for u in client.get("/v1/feedback/updates", headers=_auth(user)).json()
    ]
    assert titles == ["First", "Second"]


@pytest.mark.parametrize(
    "status", ["open", "in_progress", "pending_review", "resolved", "wont_fix"],
)
def test_every_canonical_status_serialises(status: str):
    """CR002's minimal half. The old Literal carried triaged/fixed — never
    written — and lacked `resolved`, of which Alpha holds 35 rows. Any read
    endpoint would have ValidationError'd on every one of them."""
    resp = BugReportResponse(
        id=uuid4(),
        status=status,  # type: ignore[arg-type]
        created_at=datetime.now(timezone.utc),
    )
    assert resp.status == status
