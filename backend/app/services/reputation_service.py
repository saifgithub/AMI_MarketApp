"""Reputation engine (CR004, D-060) — the point ledger behind weekly leagues.

Every engagement moment routes through `award()`: it applies ref-based
dedup, per-type daily count limits, and the global daily cap, then writes a
`reputation_events` row, bumps `users.reputation`, and — when the user holds
a seat in the current ISO week's league — bumps `league_members.points`.

`streak()` derives the activity streak from what the user already does
(challenge attempts, lesson starts/completions, journal entries — journal
captures room/trade/1-on-1/brief activity) in the user's own timezone, and
fires milestone awards + credit grants exactly once per milestone.

Same-transaction pattern as api/admin.py::_record_event — the caller owns
the session and the commit.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import NamedTuple
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.core.config import settings
from app.core.logging import logger
from app.db.models import (
    DailyChallengeAttemptRow,
    JournalEntryRow,
    LeagueMemberRow,
    LessonProgressRow,
    ReputationEventRow,
    SubscriptionEventRow,
    User,
)

# D-060 scoring table (Plan C §C1). Values are deliberately small and
# process-rewarding — no P&L-linked event exists or ever will (store
# declaration + D-060).
POINTS: dict[str, int] = {
    "challenge_attempted": 2,
    "challenge_correct": 3,
    "lesson_passed": 5,
    "agent_unlocked": 10,
    "room_verdict": 3,
    "trade_disciplined": 2,
    "trade_reviewed": 3,
    "streak_7": 10,
    "streak_30": 25,
    "streak_100": 50,
}

# Repeatable-by-design events get a per-type daily count limit so they
# can't be farmed inside the global cap.
PER_TYPE_DAILY_LIMIT: dict[str, int] = {
    "trade_disciplined": 3,
    "trade_reviewed": 3,
}

# Streak milestone → credit grant (daily_and_streaks.md).
STREAK_MILESTONES: tuple[int, ...] = (7, 30, 100)
STREAK_CREDITS: dict[int, int] = {7: 5, 30: 25, 100: 100}


class StreakInfo(NamedTuple):
    current: int
    longest: int
    next_milestone: int | None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso_week(dt: datetime) -> str:
    """ISO week key 'YYYY-Www' — the league partitioning unit."""
    year, week, _ = dt.isocalendar()
    return f"{year}-W{week:02d}"


def _user_tz(user: User) -> ZoneInfo:
    try:
        return ZoneInfo(user.timezone or "UTC")
    except Exception:
        return ZoneInfo("UTC")


def _local_day_bounds_utc(user: User, now: datetime) -> tuple[datetime, datetime]:
    """(start, end) of the user's *local* today, expressed in UTC."""
    tz = _user_tz(user)
    local_now = now.astimezone(tz)
    start_local = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


class ReputationService:
    """Stateless; every method takes the caller's session."""

    @property
    def daily_cap(self) -> int:
        return settings.reputation_daily_cap

    def award(
        self,
        session,
        *,
        user_id: UUID,
        event_type: str,
        ref_id: str | None = None,
    ) -> int:
        """Grant points for one engagement moment. Returns points actually
        granted — 0 when deduped, type-limited, or fully capped; a partial
        value when the global daily cap clips the grant.
        """
        if event_type not in POINTS:
            raise ValueError(f"unknown reputation event_type: {event_type}")
        points = POINTS[event_type]

        user = session.execute(
            select(User).where(User.id == user_id)
        ).scalar_one_or_none()
        if user is None:
            return 0

        if ref_id is not None and self._already_awarded(
            session, user_id=user_id, event_type=event_type, ref_id=ref_id,
        ):
            return 0

        now = _utcnow()
        day_start, day_end = _local_day_bounds_utc(user, now)

        type_limit = PER_TYPE_DAILY_LIMIT.get(event_type)
        if type_limit is not None:
            type_count = session.execute(
                select(func.count()).select_from(ReputationEventRow).where(
                    ReputationEventRow.user_id == user_id,
                    ReputationEventRow.event_type == event_type,
                    ReputationEventRow.created_at >= day_start,
                    ReputationEventRow.created_at < day_end,
                )
            ).scalar_one()
            if type_count >= type_limit:
                return 0

        spent_today = session.execute(
            select(func.coalesce(func.sum(ReputationEventRow.points), 0)).where(
                ReputationEventRow.user_id == user_id,
                ReputationEventRow.created_at >= day_start,
                ReputationEventRow.created_at < day_end,
            )
        ).scalar_one()
        remaining = self.daily_cap - int(spent_today)
        if remaining <= 0:
            return 0
        granted = min(points, remaining)

        session.add(ReputationEventRow(
            id=uuid4(),
            user_id=user_id,
            event_type=event_type,
            points=granted,
            ref_id=ref_id,
            created_at=now,
        ))
        user.reputation = (user.reputation or 0) + granted

        member = session.execute(
            select(LeagueMemberRow).where(
                LeagueMemberRow.user_id == user_id,
                LeagueMemberRow.week == iso_week(now),
            )
        ).scalar_one_or_none()
        if member is not None:
            member.points = (member.points or 0) + granted

        # Sessions run autoflush=False (db/session.py) — flush so a second
        # award() in the same transaction sees this grant in its dedup/cap
        # queries.
        session.flush()

        logger.info(
            "reputation_awarded",
            user_id=str(user_id),
            event_type=event_type,
            points=granted,
            ref_id=ref_id,
        )
        return granted

    def streak(self, session, user_id: UUID) -> StreakInfo:
        """Current/longest activity streak in the user's timezone. Fires
        milestone point awards + credit grants (once ever per milestone)
        when `current` has crossed one.
        """
        user = session.execute(
            select(User).where(User.id == user_id)
        ).scalar_one_or_none()
        if user is None:
            return StreakInfo(0, 0, STREAK_MILESTONES[0])

        days = self._activity_days(session, user)
        today = _utcnow().astimezone(_user_tz(user)).date()
        current = _run_ending_at(days, today)
        if current == 0:
            current = _run_ending_at(days, today - timedelta(days=1))
        longest = _longest_run(days)

        for milestone in STREAK_MILESTONES:
            if current >= milestone:
                self._grant_milestone(session, user=user, milestone=milestone)

        next_milestone = next(
            (m for m in STREAK_MILESTONES if m > current), None,
        )
        return StreakInfo(current=current, longest=longest, next_milestone=next_milestone)

    # ── Internals ────────────────────────────────────────────────────────

    def _already_awarded(
        self, session, *, user_id: UUID, event_type: str, ref_id: str,
    ) -> bool:
        return session.execute(
            select(ReputationEventRow.id).where(
                ReputationEventRow.user_id == user_id,
                ReputationEventRow.event_type == event_type,
                ReputationEventRow.ref_id == ref_id,
            ).limit(1)
        ).scalar_one_or_none() is not None

    def _activity_days(self, session, user: User) -> set[date]:
        """Distinct local-date set across every activity source."""
        tz = _user_tz(user)
        stamps: list[datetime] = []
        stamps += session.execute(
            select(DailyChallengeAttemptRow.created_at)
            .where(DailyChallengeAttemptRow.user_id == user.id)
        ).scalars().all()
        rows = session.execute(
            select(LessonProgressRow.started_at, LessonProgressRow.completed_at)
            .where(LessonProgressRow.user_id == user.id)
        ).all()
        for started_at, completed_at in rows:
            if started_at is not None:
                stamps.append(started_at)
            if completed_at is not None:
                stamps.append(completed_at)
        stamps += session.execute(
            select(JournalEntryRow.created_at)
            .where(JournalEntryRow.user_id == user.id)
        ).scalars().all()

        days: set[date] = set()
        for stamp in stamps:
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            days.add(stamp.astimezone(tz).date())
        return days

    def _grant_milestone(self, session, *, user: User, milestone: int) -> None:
        """Points + credits for one streak milestone, exactly once ever —
        the reputation_events ref row doubles as the credit-grant guard."""
        event_type = f"streak_{milestone}"
        ref_id = f"streak-{milestone}"
        if self._already_awarded(
            session, user_id=user.id, event_type=event_type, ref_id=ref_id,
        ):
            return
        self.award(session, user_id=user.id, event_type=event_type, ref_id=ref_id)

        credits = STREAK_CREDITS[milestone]
        old_balance = user.credit_balance or 0
        user.credit_balance = old_balance + credits
        session.add(SubscriptionEventRow(
            id=uuid4(),
            user_id=user.id,
            event_type="credits_added",
            from_value=str(old_balance),
            to_value=str(user.credit_balance),
            source="app",
            note=f"streak_milestone_{milestone}",
            created_at=_utcnow(),
        ))
        logger.info(
            "streak_milestone_granted",
            user_id=str(user.id),
            milestone=milestone,
            credits=credits,
        )


def _run_ending_at(days: set[date], end: date) -> int:
    run = 0
    cursor = end
    while cursor in days:
        run += 1
        cursor -= timedelta(days=1)
    return run


def _longest_run(days: set[date]) -> int:
    longest = 0
    for d in days:
        if d - timedelta(days=1) not in days:  # run start
            run = 1
            cursor = d + timedelta(days=1)
            while cursor in days:
                run += 1
                cursor += timedelta(days=1)
            longest = max(longest, run)
    return longest


# ── Singleton ───────────────────────────────────────────────────────────

_service: ReputationService | None = None


def get_reputation_service() -> ReputationService:
    global _service
    if _service is None:
        _service = ReputationService()
    return _service
