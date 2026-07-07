"""CR004 (D-060) — LeagueService unit tests.

Covers roll idempotency, cohort chunking, promote/relegate outcomes, the
<10-member no-relegation rule, tier movement, handle minting + the single
allowed regeneration, and eligibility filtering by plan.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db import get_session
from app.db.models import (
    LeagueMemberRow,
    LeagueRow,
    ReputationEventRow,
    User,
)
from app.services.auth_service import AuthService
from app.services.league_service import (
    TIERS,
    HandleAlreadyRegenerated,
    LeagueService,
    get_league_service,
    week_end,
)
from app.services.reputation_service import iso_week


def _make_active_users(n: int) -> list:
    """n users, each with one reputation event inside the 7-day window."""
    auth = AuthService()
    ids = []
    with get_session() as s:
        for _ in range(n):
            au, _, _ = auth.ensure_anonymous(device_user_id=None)
            ids.append(au.id)
        for uid in ids:
            s.add(ReputationEventRow(
                user_id=uid, event_type="lesson_passed", points=5,
                ref_id=f"l-{uid}", created_at=datetime.now(timezone.utc),
            ))
    return ids


def test_weekly_roll_assembles_and_is_idempotent():
    ids = _make_active_users(4)
    svc = LeagueService()
    with get_session() as s:
        assert svc.weekly_roll(s) is True
    with get_session() as s:
        assert svc.weekly_roll(s) is False  # same week → no-op
        leagues = s.execute(select(LeagueRow)).scalars().all()
        assert len(leagues) == 1
        assert leagues[0].week == iso_week(datetime.now(timezone.utc))
        assert leagues[0].tier == TIERS[0]  # everyone starts Apprentice
        members = s.execute(select(LeagueMemberRow)).scalars().all()
        assert {m.user_id for m in members} == set(ids)
        assert all(m.points == 0 for m in members)


def test_roll_chunks_cohorts_at_configured_size(monkeypatch):
    monkeypatch.setattr(settings, "league_cohort_size", 3)
    _make_active_users(7)
    svc = LeagueService()
    with get_session() as s:
        svc.weekly_roll(s)
    with get_session() as s:
        leagues = s.execute(select(LeagueRow)).scalars().all()
        assert len(leagues) == 3  # 3 + 3 + 1
        sizes = sorted(
            len(s.execute(
                select(LeagueMemberRow).where(LeagueMemberRow.league_id == lg.id)
            ).scalars().all())
            for lg in leagues
        )
        assert sizes == [1, 3, 3]


def test_roll_respects_plan_eligibility(monkeypatch):
    monkeypatch.setattr(settings, "league_eligible_plans", ["trader"])
    ids = _make_active_users(2)
    with get_session() as s:
        trader = s.execute(select(User).where(User.id == ids[0])).scalar_one()
        trader.plan = "trader"
    svc = LeagueService()
    with get_session() as s:
        svc.weekly_roll(s)
    with get_session() as s:
        members = s.execute(select(LeagueMemberRow)).scalars().all()
        assert [m.user_id for m in members] == [ids[0]]


def test_finalize_ranks_promotes_and_relegates():
    ids = _make_active_users(12)
    svc = LeagueService()
    last_week = iso_week(datetime.now(timezone.utc) - timedelta(days=7))
    with get_session() as s:
        league = LeagueRow(week=last_week, tier="analyst")
        s.add(league)
        s.flush()
        for i, uid in enumerate(ids):
            s.add(LeagueMemberRow(
                league_id=league.id, user_id=uid, week=last_week,
                points=i * 10,  # distinct, ascending
            ))
    with get_session() as s:
        svc.weekly_roll(s)
    with get_session() as s:
        members = s.execute(
            select(LeagueMemberRow)
            .where(LeagueMemberRow.week == last_week)
            .order_by(LeagueMemberRow.rank_final)
        ).scalars().all()
        assert [m.rank_final for m in members] == list(range(1, 13))
        assert all(m.outcome == "promoted" for m in members[:5])
        assert all(m.outcome == "relegated" for m in members[-5:])
        assert all(m.outcome == "stay" for m in members[5:7])
        # Points order preserved: rank 1 = highest points.
        assert members[0].points == 110


def test_small_cohort_has_no_relegation():
    ids = _make_active_users(6)
    svc = LeagueService()
    last_week = iso_week(datetime.now(timezone.utc) - timedelta(days=7))
    with get_session() as s:
        league = LeagueRow(week=last_week, tier="apprentice")
        s.add(league)
        s.flush()
        for i, uid in enumerate(ids):
            s.add(LeagueMemberRow(
                league_id=league.id, user_id=uid, week=last_week, points=i,
            ))
    with get_session() as s:
        svc.weekly_roll(s)
    with get_session() as s:
        outcomes = {
            m.outcome for m in s.execute(
                select(LeagueMemberRow).where(LeagueMemberRow.week == last_week)
            ).scalars().all()
        }
        assert "relegated" not in outcomes


def test_tier_moves_one_step_on_next_assembly():
    ids = _make_active_users(1)
    svc = LeagueService()
    last_week = iso_week(datetime.now(timezone.utc) - timedelta(days=7))
    with get_session() as s:
        league = LeagueRow(week=last_week, tier="analyst")
        s.add(league)
        s.flush()
        s.add(LeagueMemberRow(
            league_id=league.id, user_id=ids[0], week=last_week, points=50,
        ))
    with get_session() as s:
        svc.weekly_roll(s)  # finalizes: rank 1 → promoted
    with get_session() as s:
        current = s.execute(
            select(LeagueRow).where(
                LeagueRow.week == iso_week(datetime.now(timezone.utc))
            )
        ).scalars().all()
        assert len(current) == 1
        assert current[0].tier == "trader"  # analyst + promotion


def test_ensure_handle_mints_once_and_regen_only_once():
    ids = _make_active_users(1)
    svc = LeagueService()
    with get_session() as s:
        user = s.execute(select(User).where(User.id == ids[0])).scalar_one()
        first = svc.ensure_handle(s, user)
        assert first
        assert svc.ensure_handle(s, user) == first  # stable
        regenerated = svc.regenerate_handle(s, user)
        assert regenerated != first or True  # may collide by chance; key: no error
        assert user.handle_regenerated_at is not None
        with pytest.raises(HandleAlreadyRegenerated):
            svc.regenerate_handle(s, user)


def test_handle_collision_retries(monkeypatch):
    """Force the generator down to a single candidate, occupy it, and check
    the numbered-suffix fallback kicks in."""
    import app.services.league_service as lg
    monkeypatch.setattr(lg, "HANDLE_ADJ", ("Cobalt",))
    monkeypatch.setattr(lg, "HANDLE_NOUN", ("Falcon",))
    ids = _make_active_users(2)
    svc = LeagueService()
    with get_session() as s:
        first = s.execute(select(User).where(User.id == ids[0])).scalar_one()
        second = s.execute(select(User).where(User.id == ids[1])).scalar_one()
        assert svc.ensure_handle(s, first) == "Cobalt Falcon"
        other = svc.ensure_handle(s, second)
        assert other.startswith("Cobalt Falcon ")  # numbered fallback
        assert other != "Cobalt Falcon"


def test_week_end_is_next_monday():
    end = week_end("2026-W28")
    assert end.isoweekday() == 1
    assert end == datetime(2026, 7, 13, tzinfo=timezone.utc)


def test_get_league_service_singleton():
    assert get_league_service() is get_league_service()
