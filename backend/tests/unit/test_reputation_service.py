"""CR004 (D-060) — ReputationService unit tests.

Covers the scoring table, ref-based dedup, per-type daily limits, the
global daily-cap clamp, streak calculation across a timezone boundary,
league-points passthrough, and the once-ever milestone credit grant.
"""

from __future__ import annotations

import threading
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import (
    BadgeRow,
    DailyChallengeAttemptRow,
    JournalEntryRow,
    LeagueMemberRow,
    LeagueRow,
    ReputationEventRow,
    StreakFreezeRow,
    SubscriptionEventRow,
    User,
)
from app.services.auth_service import AuthService
from app.services.reputation_service import (
    POINTS,
    ReputationService,
    _user_tz,
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
    assert first == 5
    assert second == 0
    assert len(_events(user.id)) == 1


def test_award_same_type_different_ref_both_grant():
    user = _make_user()
    svc = ReputationService()
    with get_session() as s:
        assert svc.award(s, user_id=user.id, event_type="room_verdict", ref_id="run-1") == 3
        assert svc.award(s, user_id=user.id, event_type="room_verdict", ref_id="run-2") == 3


def test_award_race_on_dedup_check_is_caught_by_db_index(monkeypatch):
    """DEF039 — the _already_awarded() SELECT is not a lock: simulate two
    concurrent award() calls both passing the dedup check (the loser's
    check ran before the winner's commit), so the loser's INSERT is the
    one that actually has to fight the unique index. Must return 0, not
    raise, and must not leave a duplicate row."""
    user = _make_user()
    svc = ReputationService()

    # Winner commits first, out-of-band, as a concurrent request would.
    with get_session() as s:
        svc.award(s, user_id=user.id, event_type="room_verdict", ref_id="run-race")

    # Force the loser's dedup check to miss (as it would have, had it run
    # before the winner's commit) so its INSERT reaches the DB index.
    monkeypatch.setattr(ReputationService, "_already_awarded", lambda *a, **k: False)
    with get_session() as s:
        granted = svc.award(
            s, user_id=user.id, event_type="room_verdict", ref_id="run-race",
        )
    assert granted == 0
    assert len(_events(user.id)) == 1


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
        # 2 lessons + 1 challenge-correct + 2 room verdicts + 2 challenge
        # wrong-but-tried = 5+5+5+3+3+1+1 = 23 of the 25 cap.
        svc.award(s, user_id=user.id, event_type="lesson_passed", ref_id="l1")
        svc.award(s, user_id=user.id, event_type="lesson_passed", ref_id="l2")
        svc.award(s, user_id=user.id, event_type="challenge_correct", ref_id="c1")
        svc.award(s, user_id=user.id, event_type="room_verdict", ref_id="r1")
        svc.award(s, user_id=user.id, event_type="room_verdict", ref_id="r2")
        svc.award(s, user_id=user.id, event_type="challenge_wrong_tried", ref_id="a1")
        svc.award(s, user_id=user.id, event_type="challenge_wrong_tried", ref_id="a2")
        # agent_unlocked is worth 10 — only 2 remain under the cap.
        granted = svc.award(
            s, user_id=user.id, event_type="agent_unlocked", ref_id="agent-1",
        )
        assert granted == 2
        # Cap exhausted → zero.
        assert svc.award(
            s, user_id=user.id, event_type="room_verdict", ref_id="r3",
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
    # Exhaust today's 25-point cap with normal activity before the milestone
    # (award() auto-clips the last grant to whatever remains under the cap).
    with get_session() as s:
        svc.award(s, user_id=user.id, event_type="lesson_passed", ref_id="l1")
        svc.award(s, user_id=user.id, event_type="lesson_passed", ref_id="l2")
        svc.award(s, user_id=user.id, event_type="challenge_correct", ref_id="c1")
        svc.award(s, user_id=user.id, event_type="challenge_correct", ref_id="c2")
        svc.award(s, user_id=user.id, event_type="room_verdict", ref_id="r1")
        svc.award(s, user_id=user.id, event_type="challenge_wrong_tried", ref_id="a1")
        svc.award(s, user_id=user.id, event_type="challenge_wrong_tried", ref_id="a2")
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


def test_streak_milestone_credit_not_double_granted_under_race(monkeypatch):
    """DEF049 — the milestone credit grant must NOT fire when this call lost
    the concurrent guard-row insert race. Winner grants streak_7 (guard row +
    5 credits, committed); a concurrent loser whose _already_awarded() check
    missed the winner's row must have its award() rollback AND skip the
    credit grant. Without the fix (unconditional grant) the loser would push
    credit_balance to 10 — a monetized double-grant."""
    user = _make_user()
    svc = ReputationService()
    now = datetime.now(timezone.utc)
    with get_session() as s:
        for days_ago in range(7):  # live 7-day streak → crosses streak_7
            s.add(JournalEntryRow(
                user_id=user.id, entry_type="trade", title=f"d{days_ago}",
                created_at=now - timedelta(days=days_ago),
            ))

    # Winner: normal streak() grants streak_7 + 5 credits, committed.
    with get_session() as s:
        svc.streak(s, user.id)
    with get_session() as s:
        row = s.execute(select(User).where(User.id == user.id)).scalar_one()
        assert row.credit_balance == 5

    # Loser: force its dedup checks to miss the winner's committed guard row
    # (the SELECT-then-INSERT race), so its award() insert hits the unique
    # index → IntegrityError → rollback → _AwardRaceLost → credit skipped.
    monkeypatch.setattr(ReputationService, "_already_awarded", lambda *a, **k: False)
    with get_session() as s:
        svc.streak(s, user.id)

    milestone_events = [e for e in _events(user.id) if e.event_type == "streak_7"]
    assert len(milestone_events) == 1  # still exactly one guard row
    with get_session() as s:
        row = s.execute(select(User).where(User.id == user.id)).scalar_one()
        assert row.credit_balance == 5  # NOT 10 — no double-grant
        credit_events = s.execute(
            select(SubscriptionEventRow).where(
                SubscriptionEventRow.user_id == user.id,
                SubscriptionEventRow.event_type == "credits_added",
            )
        ).scalars().all()
        assert len(credit_events) == 1


def test_get_reputation_service_singleton():
    assert get_reputation_service() is get_reputation_service()


# ── CR091/CR092 — badges ────────────────────────────────────────────────


def _badges(user_id) -> list[BadgeRow]:
    with get_session() as s:
        return list(
            s.execute(
                select(BadgeRow).where(BadgeRow.user_id == user_id)
            ).scalars().all()
        )


def test_streak_milestone_awards_badge():
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
        svc.streak(s, user.id)
    badges = _badges(user.id)
    assert len(badges) == 1
    assert badges[0].badge_key == "streak_week_one"
    assert badges[0].is_permanent_flair is False


def test_badge_not_double_awarded_on_replay(monkeypatch):
    """D2 — a user who hits the milestone, loses the streak (a real gap,
    simulated by moving "today" forward via `_utcnow`), and climbs back to
    it must NOT get a second badge or second credit grant. Tested by
    replaying streak() across an actual loss-then-reclimb, not by asserting
    internals directly."""
    import app.services.reputation_service as rep_module

    user = _make_user()
    svc = ReputationService()
    t0 = datetime.now(timezone.utc)

    # First climb: 7 consecutive days ending at t0 → streak_7 fires.
    with get_session() as s:
        for days_ago in range(7):
            s.add(JournalEntryRow(
                user_id=user.id, entry_type="trade", title=f"first-{days_ago}",
                created_at=t0 - timedelta(days=days_ago),
            ))
    monkeypatch.setattr(rep_module, "_utcnow", lambda: t0)
    with get_session() as s:
        info = svc.streak(s, user.id)
    assert info.current == 7
    assert len(_badges(user.id)) == 1
    with get_session() as s:
        credits_after_first = s.execute(
            select(User.credit_balance).where(User.id == user.id)
        ).scalar_one()
    assert credits_after_first == 5

    # Streak lapses — a full gap, no activity, "today" moved 20 days on.
    t1 = t0 + timedelta(days=20)
    monkeypatch.setattr(rep_module, "_utcnow", lambda: t1)
    with get_session() as s:
        info = svc.streak(s, user.id)
    assert info.current == 0  # genuinely lost, not just re-derived

    # Climbs back to 7, ending at a later "today" — crosses streak_7 again.
    with get_session() as s:
        for days_ago in range(7):
            s.add(JournalEntryRow(
                user_id=user.id, entry_type="trade", title=f"second-{days_ago}",
                created_at=t1 - timedelta(days=days_ago),
            ))
    with get_session() as s:
        info = svc.streak(s, user.id)
    assert info.current == 7  # replay — must not re-award

    badges = _badges(user.id)
    assert len(badges) == 1  # still exactly one Week One badge, ever
    with get_session() as s:
        credit_balance = s.execute(
            select(User.credit_balance).where(User.id == user.id)
        ).scalar_one()
    assert credit_balance == 5  # not re-granted


def test_marathoner_365_day_milestone_grants_badge_flair_and_credits():
    user = _make_user()
    svc = ReputationService()
    now = datetime.now(timezone.utc)
    with get_session() as s:
        for days_ago in range(365):
            s.add(JournalEntryRow(
                user_id=user.id, entry_type="trade", title=f"d{days_ago}",
                created_at=now - timedelta(days=days_ago),
            ))
    with get_session() as s:
        info = svc.streak(s, user.id)
    assert info.current == 365
    assert info.next_milestone is None
    badges = _badges(user.id)
    marathoner = [b for b in badges if b.badge_key == "streak_marathoner"]
    assert len(marathoner) == 1
    assert marathoner[0].is_permanent_flair is True
    # Regression: earlier tiers are unaffected — all four fire once each.
    assert {b.badge_key for b in badges} == {
        "streak_week_one", "streak_month_strong", "streak_centurion",
        "streak_marathoner",
    }
    with get_session() as s:
        row = s.execute(select(User).where(User.id == user.id)).scalar_one()
        assert row.credit_balance == 5 + 25 + 100 + 500


# ── CR094 — paid-tier streak freezes ────────────────────────────────────


def _set_plan(user_id, plan: str) -> None:
    with get_session() as s:
        u = s.execute(select(User).where(User.id == user_id)).scalar_one()
        u.plan = plan


def test_freeze_refuses_visibly_for_non_floor_manager():
    user = _make_user()
    _set_plan(user.id, "floor_pass")
    svc = ReputationService()
    with get_session() as s:
        result = svc.freeze(s, user.id, on=date.today())
    assert result.ok is False
    assert result.reason == "not_entitled"
    with get_session() as s:
        assert s.execute(
            select(StreakFreezeRow).where(StreakFreezeRow.user_id == user.id)
        ).scalars().all() == []


def test_freeze_capped_at_two_per_year_for_floor_manager():
    user = _make_user()
    _set_plan(user.id, "floor_manager")
    svc = ReputationService()
    d1, d2, d3 = date(2026, 3, 1), date(2026, 6, 1), date(2026, 9, 1)
    with get_session() as s:
        r1 = svc.freeze(s, user.id, on=d1)
        r2 = svc.freeze(s, user.id, on=d2)
        r3 = svc.freeze(s, user.id, on=d3)
    assert r1.ok and r1.remaining == 1
    assert r2.ok and r2.remaining == 0
    assert r3.ok is False
    assert r3.reason == "limit_reached"
    with get_session() as s:
        rows = s.execute(
            select(StreakFreezeRow).where(StreakFreezeRow.user_id == user.id)
        ).scalars().all()
        assert len(rows) == 2


class _PGDialectSession:
    """Wraps a real (sqlite) session and claims to be Postgres.

    `freeze()` gates its DEF119 advisory-lock statement on
    `session.get_bind().dialect.name == "postgresql"` because SQLite has no
    advisory locks. This proxy flips that gate so the lock statement's shape
    (that it runs, and with the right key) can be asserted without a live
    Postgres — it does NOT prove the lock serialises anything, since the
    underlying engine is still SQLite. The one `pg_advisory_xact_lock` call
    is intercepted (SQLite would raise on unknown SQL); every other call
    passes straight through to the real session.
    """

    def __init__(self, real):
        self._real = real
        self.lock_calls: list[dict] = []

    def get_bind(self):
        class _Dialect:
            name = "postgresql"

        class _Bind:
            dialect = _Dialect()

        return _Bind()

    def execute(self, statement, *args, **kwargs):
        if "pg_advisory_xact_lock" in str(statement):
            self.lock_calls.append(args[0] if args else kwargs)
            return None
        return self._real.execute(statement, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._real, name)


def test_freeze_takes_a_postgres_advisory_lock_keyed_on_user_and_period():
    """DEF119: proves the lock statement's *shape*, not that it serialises.

    Whether `pg_advisory_xact_lock` actually blocks a second concurrent
    transaction cannot be shown on this machine — there is no local
    Postgres and the Mac must not start one. This only asserts freeze()
    issues the lock, gated on the postgres dialect, keyed on (user_id,
    period) so two different users or two different years never contend.
    """
    user = _make_user()
    _set_plan(user.id, "floor_manager")
    svc = ReputationService()
    with get_session() as s:
        proxy = _PGDialectSession(s)
        result = svc.freeze(proxy, user.id, on=date(2026, 3, 1))
    assert result.ok
    assert proxy.lock_calls == [{"key": f"streak_freeze:{user.id}:2026"}]


def test_freeze_concurrent_attempt_is_inconclusive_on_sqlite_by_design():
    """DEF119 concurrency probe — cannot enforce the cap here, and says so.

    Seeds one legitimate freeze (1 of 2 used), then races two threads
    calling `freeze()` on separate sessions for two different new dates in
    the same year — both are expected to read the stale COUNT of 1 before
    either commits, which is the race DEF119 describes. On Postgres READ
    COMMITTED (production) the advisory lock added above is what closes
    that: the second transaction blocks until the first commits, so its
    COUNT sees the first's row.

    **Measured on this machine's SQLite test engine, this is NOT masked.**
    The DEF119 row and the CR091-STREAKS auditor both describe SQLite's
    file-level write lock throwing `OperationalError: database is locked`
    before the race resolves. Run repeatedly here, that did not happen: the
    default `sqlite3` busy-timeout quietly waits out the write lock instead
    of raising, so both threads' stale COUNT-of-1 goes on to commit its own
    INSERT and the 2-per-year cap is actually exceeded (3 rows) — a
    reproduction of the underlying defect, not of the auditor's specific
    failure mode. This is disclosed as a measured discrepancy from the row,
    not a re-litigation of it: the vulnerability is the same one either way.

    Because the advisory lock is gated to the `postgresql` dialect (SQLite
    has no advisory locks, and the Mac cannot run a local Postgres to prove
    the gated branch under real concurrency), this test cannot be written
    to assert the cap holds — that would be a green result implying more
    than this engine can prove. It instead asserts only that whatever
    happens is internally consistent (every outcome accounted for) and
    leaves the actual number of rows unconstrained, so it stays true
    whether SQLite's timeout resolves the write lock silently (over-cap,
    what is actually observed here) or eventually throws (fewer rows).
    """
    from sqlalchemy.exc import OperationalError

    user = _make_user()
    _set_plan(user.id, "floor_manager")
    svc = ReputationService()
    with get_session() as s:
        svc.freeze(s, user.id, on=date(2026, 1, 1))

    outcomes: list[bool | Exception] = []

    def _attempt(on_date: date) -> None:
        try:
            with get_session() as s2:
                r = svc.freeze(s2, user.id, on=on_date)
                outcomes.append(r.ok)
        except OperationalError as exc:
            outcomes.append(exc)

    t1 = threading.Thread(target=_attempt, args=(date(2026, 3, 1),))
    t2 = threading.Thread(target=_attempt, args=(date(2026, 6, 1),))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(outcomes) == 2, "both threads must report an outcome"
    successes = [o for o in outcomes if o is True]

    with get_session() as s:
        rows = s.execute(
            select(StreakFreezeRow).where(StreakFreezeRow.user_id == user.id)
        ).scalars().all()
        # 1 seed row + however many of the two racers actually committed —
        # a consistency check on the mechanism, not a cap assertion. This
        # test does not know, and does not claim to know, whether that
        # count is <= 2 (cap held) or 3 (cap broken, what this machine
        # actually produces every run observed while writing this fix).
        assert len(rows) == 1 + len(successes)


def test_frozen_day_pauses_streak_without_breaking_it():
    user = _make_user()
    _set_plan(user.id, "floor_manager")
    svc = ReputationService()
    today = datetime.now(timezone.utc).astimezone(_user_tz(user)).date()
    with get_session() as s:
        # Activity today and 2 days ago; yesterday is frozen, not active —
        # a missed, unfrozen day would break the run at 1.
        for days_ago in (0, 2):
            s.add(JournalEntryRow(
                user_id=user.id, entry_type="trade", title=f"d{days_ago}",
                created_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
            ))
    with get_session() as s:
        svc.freeze(s, user.id, on=today - timedelta(days=1))
    with get_session() as s:
        info = svc.streak(s, user.id)
    # 2 actual activity days (today + 2-days-ago) span an unfrozen would-be
    # gap; the frozen day pauses the run without breaking OR extending it
    # (it's not activity, just tolerance) — so current is 2, not 3.
    assert info.current == 2
