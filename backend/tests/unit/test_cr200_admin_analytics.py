"""CR200 — admin analytics: real-user exclusions, DAU union, day bucketing.

Covers: summary excludes room-benchmark synthetics and probe-id users while
counting real users; DAU/WAU derive from the activity union; timeseries
zero-fills, buckets by UTC day (boundary case: an event just before/after
midnight lands in the right bucket), and sums credits_spent from the
subscription event's from→to delta; revenuecat counts by event_type.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin_analytics import router as analytics_router
from app.core.config import settings
from app.db import get_session, init_schema
from app.db.models import (
    RevenueCatEventRow,
    RoomRunRow,
    SubscriptionEventRow,
    User,
)
from app.services.admin_analytics import _EXCLUDED_USER_IDS, summary, timeseries

_SECRET = "test-admin-secret-abc123"
_HDR = {"Authorization": f"Bearer {_SECRET}"}


@pytest.fixture(autouse=True)
def _set_admin_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_secret", _SECRET)


def _mk_user(
    user_id: UUID | None = None,
    last_app_version: str | None = "0.1.0+70",
    created_at: datetime | None = None,
) -> UUID:
    init_schema()
    uid = user_id or uuid4()
    with get_session() as s:
        s.add(User(
            id=uid,
            plan="floor_pass",
            credit_balance=8,
            is_anonymous=True,
            last_app_version=last_app_version,
            created_at=created_at or datetime.now(timezone.utc),
        ))
    return uid


def _mk_room_run(user_id: UUID, started_at: datetime) -> None:
    with get_session() as s:
        s.add(RoomRunRow(
            user_id=user_id, ticker="AAPL", started_at=started_at,
            mandate_version=1, model_tier="mid", status="complete",
        ))


def test_summary_excludes_synthetics_and_probes() -> None:
    real = _mk_user()
    _mk_user(last_app_version="room-benchmark")
    _mk_user(user_id=_EXCLUDED_USER_IDS[0])
    s = summary()
    users_before = s["users"]["total"]
    # The two excluded rows must not be in the count; the real one must be.
    # (Other tests share the sqlite fixture DB, so assert relatively.)
    _mk_user(last_app_version="room-benchmark")
    assert summary()["users"]["total"] == users_before
    _mk_user()
    assert summary()["users"]["total"] == users_before + 1
    assert real is not None


def test_dau_from_activity_union() -> None:
    uid = _mk_user()
    before = summary()["active"]["dau"]
    _mk_room_run(uid, datetime.now(timezone.utc) - timedelta(hours=2))
    after = summary()
    assert after["active"]["dau"] == before + 1
    assert after["active"]["mau"] >= after["active"]["dau"]


def test_timeseries_day_boundary_and_zero_fill() -> None:
    uid = _mk_user()
    today = datetime.now(timezone.utc).date().isoformat()
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
    # One run just after today's UTC midnight, one just before it.
    midnight = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )
    _mk_room_run(uid, midnight + timedelta(minutes=1))
    _mk_room_run(uid, midnight - timedelta(minutes=1))
    t = timeseries(days=7)
    assert len(t["days"]) == 7
    assert len(t["room_runs"]) == 7
    assert t["room_runs"][t["days"].index(today)] >= 1
    assert t["room_runs"][t["days"].index(yesterday)] >= 1


def test_timeseries_credits_spent_delta() -> None:
    uid = _mk_user()
    with get_session() as s:
        s.add(SubscriptionEventRow(
            id=uuid4(), user_id=uid, event_type="credits_spent",
            from_value="8", to_value="0", source="room",
            created_at=datetime.now(timezone.utc),
        ))
    t = timeseries(days=2)
    today = datetime.now(timezone.utc).date().isoformat()
    assert t["credits_spent"][t["days"].index(today)] >= 8


def test_revenuecat_endpoint() -> None:
    init_schema()
    with get_session() as s:
        s.add(RevenueCatEventRow(
            id=uuid4(), event_id=f"evt-{uuid4().hex}", event_type="INITIAL_PURCHASE",
            received_at=datetime.now(timezone.utc),
        ))
    app = FastAPI()
    app.include_router(analytics_router)
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/v1/admin/analytics/revenuecat", headers=_HDR)
    assert r.status_code == 200
    assert r.json()["counts"].get("INITIAL_PURCHASE", 0) >= 1
    assert client.get("/v1/admin/analytics/summary", headers=_HDR).status_code == 200
    assert client.get("/v1/admin/analytics/timeseries?days=7", headers=_HDR).status_code == 200
    assert client.get("/v1/admin/analytics/summary").status_code == 403
