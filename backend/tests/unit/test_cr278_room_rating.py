"""CR278 (WP-36) - the Beta Room thumbs and the "Report this response" payload.

`POST /v1/room/{id}/rating` is owner-only, one answer per Room, changeable; the
admin read feeds the WP-53 exit report. The report path is the EXISTING
`POST /v1/feedback/bug`: a response report is a bug report whose `route` names
the Room and the agent and whose `trace_ids` are the app's recent ids - pinned
here so no second endpoint is ever needed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.feedback import router as feedback_router
from app.api.room_rating import admin_router, router
from app.core.config import settings
from app.db import get_session
from app.db.models import BugReportRow, RoomRatingRow, RoomRunRow
from app.services.auth_service import AuthService
from app.services.rate_limit import bug_upload_rate_limit

_SECRET = "test-admin-secret-cr278"
_ADMIN = {"Authorization": f"Bearer {_SECRET}"}
_MIGRATION_ID = "cr278a0b0c0d1"


@pytest.fixture(autouse=True)
def _admin_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_secret", _SECRET)
    bug_upload_rate_limit.reset()


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.include_router(admin_router)
    app.include_router(feedback_router)
    return TestClient(app)


def _user() -> tuple[UUID, dict[str, str]]:
    u, token, _ = AuthService().ensure_anonymous(device_user_id=None)
    return u.id, {"Authorization": f"Bearer {token}"}


def _room(user_id: UUID, *, verdict: dict | None = None, ticker: str = "AAPL") -> UUID:
    rid = uuid4()
    with get_session() as s:
        s.add(RoomRunRow(
            id=rid, user_id=user_id, ticker=ticker,
            started_at=datetime.now(timezone.utc), mandate_version=1,
            model_tier="mid", status="completed",
            verdict={"action": "APPROVE", "reason": "x"} if verdict is None else verdict,
        ))
    return rid


def test_owner_can_rate_and_the_row_is_stored(client: TestClient):
    uid, hdr = _user()
    rid = _room(uid)
    r = client.post(f"/v1/room/{rid}/rating", json={"helpful": True}, headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json()["helpful"] is True and r.json()["changed"] is False
    with get_session() as s:
        row = s.execute(
            select(RoomRatingRow).where(RoomRatingRow.room_run_id == rid)
        ).scalar_one()
        assert row.helpful is True


def test_rating_again_updates_the_single_row(client: TestClient):
    uid, hdr = _user()
    rid = _room(uid)
    client.post(f"/v1/room/{rid}/rating", json={"helpful": True}, headers=hdr)
    same = client.post(f"/v1/room/{rid}/rating", json={"helpful": True}, headers=hdr)
    assert same.json()["changed"] is False
    flipped = client.post(f"/v1/room/{rid}/rating", json={"helpful": False}, headers=hdr)
    assert flipped.status_code == 200
    assert flipped.json()["helpful"] is False and flipped.json()["changed"] is True
    with get_session() as s:
        rows = s.execute(
            select(RoomRatingRow).where(RoomRatingRow.room_run_id == rid)
        ).scalars().all()
        assert len(rows) == 1 and rows[0].helpful is False


def test_only_the_owner_can_rate(client: TestClient):
    owner, _ = _user()
    _, stranger = _user()
    rid = _room(owner)
    r = client.post(f"/v1/room/{rid}/rating", json={"helpful": True}, headers=stranger)
    assert r.status_code == 403
    with get_session() as s:
        assert s.execute(select(RoomRatingRow)).scalars().all() == []


def test_unknown_room_is_404_and_no_token_is_rejected(client: TestClient):
    _, hdr = _user()
    assert client.post(
        f"/v1/room/{uuid4()}/rating", json={"helpful": True}, headers=hdr,
    ).status_code == 404
    uid, _ = _user()
    rid = _room(uid)
    assert client.post(f"/v1/room/{rid}/rating", json={"helpful": True}).status_code in (401, 403)


def test_room_without_a_verdict_cannot_be_rated(client: TestClient):
    uid, hdr = _user()
    rid = _room(uid, verdict={})
    with get_session() as s:
        s.get(RoomRunRow, rid).verdict = None
    r = client.post(f"/v1/room/{rid}/rating", json={"helpful": True}, headers=hdr)
    assert r.status_code == 409


@pytest.mark.parametrize("body", [
    {}, {"helpful": "yes"}, {"helpful": 1}, {"helpful": None}, {"helpful": True, "x": 1},
])
def test_validation_rejects_anything_but_a_bool(client: TestClient, body: dict):
    uid, hdr = _user()
    rid = _room(uid)
    assert client.post(f"/v1/room/{rid}/rating", json=body, headers=hdr).status_code == 422


def test_admin_read_requires_admin_and_summarises(client: TestClient):
    assert client.get("/v1/admin/room-ratings").status_code == 403
    assert client.get(
        "/v1/admin/room-ratings", headers={"Authorization": "Bearer wrong"},
    ).status_code == 403

    u1, h1 = _user()
    u2, h2 = _user()
    u3, h3 = _user()
    r1, r2, r3 = _room(u1, ticker="AAPL"), _room(u2, ticker="MSFT"), _room(u3, ticker="NVDA")
    client.post(f"/v1/room/{r1}/rating", json={"helpful": True}, headers=h1)
    client.post(f"/v1/room/{r2}/rating", json={"helpful": True}, headers=h2)
    client.post(f"/v1/room/{r3}/rating", json={"helpful": False}, headers=h3)

    r = client.get("/v1/admin/room-ratings", headers=_ADMIN)
    assert r.status_code == 200
    body = r.json()
    assert body["totals"] == {
        "ratings": 3, "helpful": 2, "not_helpful": 1, "helpful_pct": 66.7,
    }
    assert {x["ticker"] for x in body["recent"]} == {"AAPL", "MSFT", "NVDA"}
    nvda = next(x for x in body["recent"] if x["ticker"] == "NVDA")
    assert nvda["helpful"] is False and nvda["verdict_action"] == "APPROVE"
    assert nvda["run_id"] == str(r3)

    limited = client.get("/v1/admin/room-ratings?limit=1", headers=_ADMIN).json()
    assert len(limited["recent"]) == 1 and limited["totals"]["ratings"] == 3
    assert client.get("/v1/admin/room-ratings?limit=0", headers=_ADMIN).status_code == 422


def test_response_report_rides_the_existing_bug_endpoint(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """The report payload the app builds (`route` = response:room:<run>:<agent>,
    plus `trace_ids`) is accepted and stored by POST /v1/feedback/bug as is."""
    monkeypatch.setattr(settings, "bug_attachments_dir", str(tmp_path))
    run_id, t1, t2 = uuid4(), uuid4(), uuid4()
    r = client.post("/v1/feedback/bug", data={
        "category": "wrong_data",
        "title": "Reasons did not match the numbers",
        "app_version": "0.1.0+200",
        "platform": "android_gms",
        "route": f"response:room:{run_id}:cio",
        "trace_ids": f"{t1},{t2}",
    })
    assert r.status_code == 201, r.text
    with get_session() as s:
        row = s.get(BugReportRow, UUID(r.json()["id"]))
        assert row.route == f"response:room:{run_id}:cio"
        assert row.trace_ids == f"{t1},{t2}"


def test_migration_chains_onto_the_previous_head():
    mig = (
        Path(__file__).resolve().parents[2] / "alembic" / "versions"
        / f"{_MIGRATION_ID}_room_ratings.py"
    ).read_text()
    assert f'revision: str = "{_MIGRATION_ID}"' in mig
    assert 'down_revision: Union[str, Sequence[str], None] = "m276a0cr239x276"' in mig
    assert '"room_ratings"' in mig


def test_a_lost_insert_race_updates_the_winners_row(client: TestClient, monkeypatch):
    """Two taps race: the loser's INSERT hits UNIQUE(room_run_id). It must end as
    an update of the winner's row (P15), not a 500."""
    from app.services import room_rating

    uid, hdr = _user()
    rid = _room(uid)
    assert client.post(f"/v1/room/{rid}/rating", json={"helpful": True}, headers=hdr).status_code == 200

    real = room_rating._existing
    calls = {"n": 0}

    def blind_first(s, run_id):
        calls["n"] += 1
        return None if calls["n"] == 1 else real(s, run_id)

    monkeypatch.setattr(room_rating, "_existing", blind_first)
    r = client.post(f"/v1/room/{rid}/rating", json={"helpful": False}, headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json()["helpful"] is False and r.json()["changed"] is True
    with get_session() as s:
        rows = s.execute(select(RoomRatingRow).where(RoomRatingRow.room_run_id == rid)).scalars().all()
        assert len(rows) == 1 and rows[0].helpful is False
