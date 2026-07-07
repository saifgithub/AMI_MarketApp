"""CR004 (D-060) — /v1/league route tests.

Covers the standings shape + is_me stamping, anonymity (display_name only
when opted in), 404 when unassigned, /me shape (handle mint + streak block),
history rows, and the 409 on a second handle regeneration.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.league import router as league_router
from app.db import get_session
from app.db.models import LeagueMemberRow, LeagueRow, User
from app.services.auth_service import AuthService
from app.services.reputation_service import iso_week


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(league_router)
    return TestClient(app, raise_server_exceptions=False)


def _make_user_and_token(display_name: str | None = None, show: bool = False):
    auth = AuthService()
    au, token, _ = auth.ensure_anonymous(device_user_id=None)
    with get_session() as s:
        user = s.execute(select(User).where(User.id == au.id)).scalar_one()
        user.handle = f"Test Handle {str(au.id)[:8]}"
        if display_name:
            user.display_name = display_name
        user.show_display_name = show
    return au.id, token


def _seat_users(user_ids, points=None):
    """Put users into one current-week league."""
    week = iso_week(datetime.now(timezone.utc))
    with get_session() as s:
        league = LeagueRow(week=week, tier="apprentice")
        s.add(league)
        s.flush()
        for i, uid in enumerate(user_ids):
            s.add(LeagueMemberRow(
                league_id=league.id, user_id=uid, week=week,
                points=(points[i] if points else 0),
                joined_at=datetime.now(timezone.utc) + timedelta(seconds=i),
            ))


def test_standings_404_when_unassigned(client: TestClient):
    _, token = _make_user_and_token()
    r = client.get(
        "/v1/league/standings", headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "not_in_league"


def test_standings_shape_ranking_and_anonymity(client: TestClient):
    me_id, me_token = _make_user_and_token(display_name="Saiful M", show=True)
    other_id, _ = _make_user_and_token(display_name="Hidden Name", show=False)
    _seat_users([me_id, other_id], points=[10, 30])
    r = client.get(
        "/v1/league/standings", headers={"Authorization": f"Bearer {me_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["week"] == iso_week(datetime.now(timezone.utc))
    assert body["tier"] == "apprentice"
    assert "ends_at" in body
    members = body["members"]
    assert len(members) == 2
    # Points desc → other first.
    assert members[0]["points"] == 30
    assert members[0]["rank"] == 1
    assert members[0]["is_me"] is False
    assert members[0]["display_name"] is None  # not opted in
    assert members[1]["is_me"] is True
    assert members[1]["display_name"] == "Saiful M"  # opted in
    for m in members:
        assert m["handle"]


def test_me_mints_handle_and_returns_streak(client: TestClient):
    auth = AuthService()
    au, token, _ = auth.ensure_anonymous(device_user_id=None)
    r = client.get("/v1/league/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["handle"]  # minted on first contact
    assert body["tier"] == "apprentice"
    assert body["reputation"] == 0
    assert body["points_this_week"] == 0
    assert body["rank"] is None
    assert body["streak"] == {"current": 0, "longest": 0, "next_milestone": 7}


def test_me_reports_rank_when_seated(client: TestClient):
    me_id, me_token = _make_user_and_token()
    other_id, _ = _make_user_and_token()
    _seat_users([me_id, other_id], points=[20, 5])
    r = client.get("/v1/league/me", headers={"Authorization": f"Bearer {me_token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["points_this_week"] == 20
    assert body["rank"] == 1


def test_history_lists_finalized_weeks(client: TestClient):
    me_id, me_token = _make_user_and_token()
    last_week = iso_week(datetime.now(timezone.utc) - timedelta(days=7))
    with get_session() as s:
        league = LeagueRow(week=last_week, tier="analyst")
        s.add(league)
        s.flush()
        s.add(LeagueMemberRow(
            league_id=league.id, user_id=me_id, week=last_week,
            points=42, rank_final=3, outcome="promoted",
        ))
    r = client.get(
        "/v1/league/history", headers={"Authorization": f"Bearer {me_token}"},
    )
    assert r.status_code == 200
    rows = r.json()
    assert rows == [{
        "week": last_week, "tier": "analyst",
        "rank_final": 3, "outcome": "promoted", "points": 42,
    }]


def test_regenerate_handle_once_then_409(client: TestClient):
    _, token = _make_user_and_token()
    r1 = client.patch(
        "/v1/league/handle", headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 200
    assert r1.json()["handle"]
    r2 = client.patch(
        "/v1/league/handle", headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 409
    assert r2.json()["detail"] == "already_regenerated"


def test_routes_require_auth(client: TestClient):
    for method, path in [
        ("get", "/v1/league/standings"),
        ("get", "/v1/league/me"),
        ("get", "/v1/league/history"),
        ("patch", "/v1/league/handle"),
    ]:
        r = getattr(client, method)(path)
        assert r.status_code == 401, f"{path} → {r.status_code}"
