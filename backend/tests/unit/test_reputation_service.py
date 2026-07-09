"""CR004 (D-060) — ReputationService unit tests.

Covers the scoring table, ref-based dedup, per-type daily limits, the
global daily-cap clamp, streak calculation across a timezone boundary,
league-points passthrough, and the once-ever milestone credit grant.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import (
    DailyChallengeAttemptRow,
    JournalEntryRow,
    LeagueMemberRow,
    LeagueRow,
    ReputationEventRow,
    SubscriptionEventRow,
    User,
)
from app.services.auth_service import AuthService
from app.services.reputation_service import (
    POINTS,
    ReputationService,
    get_reputation_service,
    iso_week,
)


def _make_user(tz: str = "UTC") -> User:
    auth = AuthService()
    au, _, _ = auth.ensure_anonymous(device_user_id=None)
    with get_session() as s:
        user = s.execute(select(User).where(User.id == au.id)).scalar_one()
        user.timezone = tz
        return user


def _events(user_id) -> list[ReputationEventRow]:
    with get_session() as s:
        return s.execute(
            select(ReputationEventRow)
            .where(ReputationEventRow.user_id == user_id)
            .order_by(ReputationEventRow.created_at)
        ).scalars().all()


def test_award_grants_points_and_increments_user_counter():
    user = _make_user()
    svc = ReputationService()
    with get_session() as s:
        granted = svc.award(
            s, user_id=user.id, event_type="lesson_passed", ref_id="lesson-001",
        )
    assert granted == POINTS["lesson_passed"] == 5
    with get_session() as s:
        row = s.execute(select(User).where(User.id == user.id)).scalar_one()
        assert row.reputation == 5
    events = _events(user.id)
    assert len(events) == 1
    assert events[0].event_type == "lesson_passed"
    assert events[0].points == 5


def test_award_unknown_event_type_raises():
    user = _make_user()
    svc = ReputationService()
    with get_session() as s:
        with pytest.raises(ValueError):
            svc.award(s, user_id=user.id, event_type="pnl_bonus")


def test_award_dedups_on_ref_id():
    user = _make_user()
    svc = ReputationService()
    with get_session() as s:
        first = svc.award(
            s, user_id=user.id, event_type="challenge_correct", ref_id="dc-1",
        )
        second = svc.award(
            s, user_id=user.id, event_type="challenge_correct", ref_id="dc-1",
        )
    assert first == 3
    assert second == 0
    assert len(_events(user.id)) == 1


def test_award_same_type_different_ref_both_grant():
    user = _make_user()
    svc = ReputationService()
    with get_session() as s:
        assert svc.award(s, user_id=user.id, event_type="room_verdict", ref_id="run-1") == 3
        assert svc.award(s, user_id=user.id, event_type="room_verdict", ref_id="run-2") == 3


def test_per_type_daily_limit_trade_events():
    user = _make_user()
    svc = ReputationService()
    with get_session() as s:
        for i in range(3):
            assert svc.award(
                s, user_id=user.id,
                event_type="trade_disciplined", ref_id=f"trade-{i}",
            ) == 2
        # 4th disciplined trade of the local day is limited.
        assert svc.award(
            s, user_id=user.id, event_type="trade_disciplined", ref_id="trade-3",
        ) == 0


def test_daily_cap_clamps_partial_grant():
    user = _make_user()
    svc = ReputationService()
    with get_session() as s:
        # 2 lessons + 2 challenge-corrects + 1 room verdict + 2 challenge
        # attempts = 5+5+3+3+3+2+2 = 23 of the 25 cap.
        svc.award(s, user_id=user.id, event_type="lesson_passed", ref_id="l1")
        svc.award(s, user_id=user.id, event_type="lesson_passed", ref_id="l2")
        svc.award(s, user_id=user.id, event_type="challenge_correct", ref_id="c1")
        svc.award(s, user_id=user.id, event_type="challenge_correct", ref_id="c2")
        svc.award(s, user_id=user.id, event_type="room_verdict", ref_id="r1")
        svc.award(s, user_id=user.id, event_type="challenge_attempted", ref_id="a1")
        svc.award(s, user_id=user.id, event_type="challenge_attempted", ref_id="a2")
        # agent_unlocked is worth 10 — only 2 remain under the cap.
        granted = svc.award(
            s, user_id=user.id, event_type="agent_unlocked", ref_id="agent-1",
        )
        assert granted == 2
        # Cap exhausted → zero.
        assert svc.award(
            s, user_id=user.id, event_type="room_verdict", ref_id="r2",
        ) == 0
    with get_session() as s:
        row = s.execute(select(User).where(User.id == user.id)).scalar_one()
        assert row.reputation == 25


def test_award_bumps_current_week_league_points():
    user = _make_user()
    svc = ReputationService()
    week = iso_week(datetime.now(timezone.utc))
    with get_session() as s:
        league = LeagueRow(week=week, tier="apprentice")
        s.add(league)
        s.flush()
        s.add(LeagueMemberRow(
            league_id=league.id, user_id=user.id, week=week, points=0,
        ))
    with get_session() as s:
        svc.award(s, user_id=user.id, event_type="lesson_passed", ref_id="l1")
    with get_session() as s:
        member = s.execute(
            select(LeagueMemberRow).where(LeagueMemberRow.user_id == user.id)
        ).scalar_one()
        assert member.points == 5


def test_streak_counts_consecutive_local_days():
    user = _make_user()
    svc = ReputationService()
    now = datetime.now(timezone.utc)
    with get_session() as s:
        for days_ago in (0, 1, 2):
            s.add(JournalEntryRow(
                user_id=user.id, entry_type="trade", title=f"d-{days_ago}",
                created_at=now - timedelta(days=days_ago),
            ))
        # A gap at day 3, activity on day 4 — not part of the current run.
        s.add(JournalEntryRow(
            user_id=user.id, entry_type="trade", title="old",
            created_at=now - timedelta(days=4),
        ))
    with get_session() as s:
        info = svc.streak(s, user.id)
    assert info.current == 3
    assert info.longest == 3
    assert info.next_milestone == 7


def test_streak_alive_when_today_unfilled():
    """Yesterday-ending runs still count — the user can extend today."""
    user = _make_user()
    svc = ReputationService()
    now = datetime.now(timezone.utc)
    with get_session() as s:
        for days_ago in (1, 2):
            s.add(DailyChallengeAttemptRow(
                user_id=user.id, challenge_id=f"dc-{days_ago}",
                selected_option=0, correct=True,
                created_at=now - timedelta(days=days_ago),
            ))
    with get_session() as s:
        info = svc.streak(s, user.id)
    assert info.current == 2


def test_streak_respects_user_timezone():
    """23:30 UTC on consecutive UTC days lands in one bucket pair for a
    UTC user but shifts for UTC+10 — the streak must follow the user's
    local dates, not UTC."""
    user = _make_user(tz="Australia/Sydney")
    svc = ReputationService()
    today_utc = datetime.now(timezone.utc)
    with get_session() as s:
        # Sydney "today" and "yesterday" built from local dates.
        from zoneinfo import ZoneInfo
        syd = ZoneInfo("Australia/Sydney")
        local_now = today_utc.astimezone(syd)
        for days_ago in (0, 1):
            local_stamp = (local_now - timedelta(days=days_ago)).replace(
                hour=8, minute=0,
            )
            s.add(JournalEntryRow(
                user_id=user.id, entry_type="trade", title=f"syd-{days_ago}",
                created_at=local_stamp.astimezone(timezone.utc),
            ))
    with get_session() as s:
        info = svc.streak(s, user.id)
    assert info.current == 2


def test_streak_milestone_grants_points_and_credits_once():
    user = _make_user()
    svc = ReputationService()
    now = datetime.now(timezone.utc)
    with get_session() as s:
        for days_ago in range(7):
            s.add(JournalEntryRow(
                user_id=user.id, entry_type="trade", title=f"d{days_ago}",
                created_at=now - timedelta(days=days_ago),
            ))
    with get_session() as s:
        info = svc.streak(s, user.id)
        assert info.current == 7
        assert info.next_milestone == 30
    with get_session() as s:
        # Second call must not double-grant.
        svc.streak(s, user.id)
    events = _events(user.id)
    milestone_events = [e for e in events if e.event_type == "streak_7"]
    assert len(milestone_events) == 1
    assert milestone_events[0].points == 10
    with get_session() as s:
        row = s.execute(select(User).where(User.id == user.id)).scalar_one()
        assert row.credit_balance == 5  # streak-7 credit grant
        credit_events = s.execute(
            select(SubscriptionEventRow).where(
                SubscriptionEventRow.user_id == user.id,
                SubscriptionEventRow.event_type == "credits_added",
            )
        ).scalars().all()
        assert len(credit_events) == 1
        assert credit_events[0].note == "streak_milestone_7"


def test_streak_milestone_credit_grant_idempotent_under_daily_cap():
    """F1 regression (CR004 audit round 1): when the daily point cap is
    already exhausted as a milestone fires, award() clips the milestone to a
    zero-point write — but its reputation_events guard row must still persist,
    or the once-ever credit grant re-fires on every subsequent streak() call
    (GET /v1/league/me runs streak() on each league-screen load). Ported from
    the auditor pin audit/handshake/regression/test_streak_milestone_cap_pin.py
    into the main suite per the round-2 recommendation.
    """
    user = _make_user()
    svc = ReputationService()
    now = datetime.now(timezone.utc)
    with get_session() as s:
        for days_ago in range(7):  # a live 7-day streak → crosses streak_7
            s.add(JournalEntryRow(
                user_id=user.id, entry_type="trade", title=f"d{days_ago}",
                created_at=now - timedelta(days=days_ago),
            ))
    # Exhaust today's 25-point cap with normal activity before the milestone.
    with get_session() as s:
        svc.award(s, user_id=user.id, event_type="lesson_passed", ref_id="l1")
        svc.award(s, user_id=user.id, event_type="lesson_passed", ref_id="l2")
        svc.award(s, user_id=user.id, event_type="challenge_correct", ref_id="c1")
        svc.award(s, user_id=user.id, event_type="challenge_correct", ref_id="c2")
        svc.award(s, user_id=user.id, event_type="room_verdict", ref_id="r1")
        svc.award(s, user_id=user.id, event_type="challenge_attempted", ref_id="a1")
        svc.award(s, user_id=user.id, event_type="challenge_attempted", ref_id="a2")
        svc.award(s, user_id=user.id, event_type="agent_unlocked", ref_id="agent-1")
    # Two league-screen loads under the exhausted cap.
    with get_session() as s:
        svc.streak(s, user.id)
    with get_session() as s:
        svc.streak(s, user.id)

    milestone_events = [e for e in _events(user.id) if e.event_type == "streak_7"]
    assert len(milestone_events) == 1       # guard row written exactly once
    assert milestone_events[0].points == 0  # clipped to zero by the full cap
    with get_session() as s:
        row = s.execute(select(User).where(User.id == user.id)).scalar_one()
        assert row.credit_balance == 5      # granted once — not re-granted
        credit_events = s.execute(
            select(SubscriptionEventRow).where(
                SubscriptionEventRow.user_id == user.id,
                SubscriptionEventRow.event_type == "credits_added",
            )
        ).scalars().all()
        assert len(credit_events) == 1


def test_get_reputation_service_singleton():
    assert get_reputation_service() is get_reputation_service()
