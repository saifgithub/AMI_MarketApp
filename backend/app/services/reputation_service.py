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

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.logging import logger
from app.db.models import (
    BadgeRow,
    DailyChallengeAttemptRow,
    JournalEntryRow,
    LeagueMemberRow,
    LessonProgressRow,
    ReputationEventRow,
    StreakFreezeRow,
    SubscriptionEventRow,
    User,
)
from app.schemas.mandate import Plan
from app.services.entitlements import effective_plan_for_user

# D-060 scoring table (Plan C §C1). Values are deliberately small and
# process-rewarding — no P&L-linked event exists or ever will (store
# declaration + D-060).
#
# CR096: challenge_attempted/challenge_correct (2/3, fired as two separate
# awards per attempt) is retired in favour of daily_and_streaks.md's 3-outcome
# table — right / close / wrong-but-tried — as a SINGLE award per attempt.
# "close" (challenge_close) has no reachable answer-space yet: every shipped
# challenge type is strict single-correct multiple-choice with no graded
# partial-credit option (confirmed at build time, CR096's open question) — so
# it's wired into POINTS and the API contract now, unreachable by current
# content until a challenge type defines what "close" means for it. This is a
# future-awards-only change (D3) — no backfill over historical
# reputation_events; existing users' totals stand.
POINTS: dict[str, int] = {
    "challenge_wrong_tried": 1,
    "challenge_close": 2,
    "challenge_correct": 5,
    "lesson_passed": 5,
    "agent_unlocked": 10,
    "room_verdict": 3,
    "trade_disciplined": 2,
    "trade_reviewed": 3,
    "streak_7": 10,
    "streak_30": 25,
    "streak_100": 50,
    "streak_365": 500,
}

# Repeatable-by-design events get a per-type daily count limit so they
# can't be farmed inside the global cap.
PER_TYPE_DAILY_LIMIT: dict[str, int] = {
    "trade_disciplined": 3,
    "trade_reviewed": 3,
}

# Streak milestone → credit grant (daily_and_streaks.md). CR092 adds 365
# ("Marathoner") — the ladder's biggest reward, 5x the next-largest grant.
STREAK_MILESTONES: tuple[int, ...] = (7, 30, 100, 365)
STREAK_CREDITS: dict[int, int] = {7: 5, 30: 25, 100: 100, 365: 500}

# CR091/CR092: streak milestone → badge key (daily_and_streaks.md's named
# ladder). 365 also carries permanent profile flair.
BADGE_KEYS: dict[int, str] = {
    7: "streak_week_one",
    30: "streak_month_strong",
    100: "streak_centurion",
    365: "streak_marathoner",
}
PERMANENT_FLAIR_MILESTONES: frozenset[int] = frozenset({365})

# CR094: Floor Manager streak-freeze allowance. See StreakFreezeRow's
# docstring for the "which year" call (calendar year, flagged for Saiful).
FREEZES_PER_YEAR = 2


class _AwardRaceLost(Exception):
    """DEF049 — internal signal: this award() call lost the concurrent
    insert race for its (user, event_type, ref_id) and rolled back, so it
    wrote NO row. Only raised when the caller opts in via `_raise_on_race`
    (the milestone path), so it can skip its follow-on credit grant. Every
    other caller keeps the plain return-0 contract."""


class StreakInfo(NamedTuple):
    current: int
    longest: int
    next_milestone: int | None


class FreezeResult(NamedTuple):
    ok: bool
    reason: str | None  # None on success; else "not_entitled" | "limit_reached" | "already_frozen"
    remaining: int


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
        always_record: bool = False,
        _raise_on_race: bool = False,
    ) -> int:
        """Grant points for one engagement moment. Returns points actually
        granted — 0 when deduped, type-limited, or fully capped; a partial
        value when the global daily cap clips the grant.

        `always_record=True` writes the `reputation_events` row even when the
        daily cap has clipped the grant to zero points — used for milestone
        awards whose row doubles as the once-ever credit-grant guard, so a
        capped day can't leave the guard unwritten (F1). Dedup and type-limit
        short-circuits still apply.

        `_raise_on_race=True` (DEF049) makes a lost concurrent-insert race
        raise `_AwardRaceLost` instead of returning 0, so a caller that does
        follow-on work gated on "did I write the row?" (the milestone credit
        grant) can tell a rollback apart from a legitimate cap-clipped 0.
        Default False keeps every other caller's return-0-on-race contract.
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
        if remaining <= 0 and not always_record:
            return 0
        granted = min(points, max(remaining, 0))

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
        try:
            session.flush()
        except IntegrityError:
            # DEF039: the _already_awarded() check above is a SELECT, not a
            # lock — two concurrent award() calls for the same
            # (user_id, event_type, ref_id) can both pass it and race to
            # insert. The partial unique index on reputation_events is the
            # backstop; losing the race is equivalent to having deduped,
            # so roll back (which also reverts the in-memory
            # user.reputation / member.points bumps above) and return 0.
            session.rollback()
            # DEF049: a follow-on credit grant gated on "did I write the
            # row?" must not fire on a rollback. Cap-clipped 0 (row written)
            # never reaches here — only a genuine duplicate does — so the
            # raise cleanly distinguishes race-loss from a legitimate 0.
            if _raise_on_race:
                raise _AwardRaceLost() from None
            return 0

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
        frozen = self._frozen_days(session, user)
        today = _utcnow().astimezone(_user_tz(user)).date()
        current = _run_ending_at(days, today, frozen)
        if current == 0:
            current = _run_ending_at(days, today - timedelta(days=1), frozen)
        longest = _longest_run(days, frozen)

        for milestone in STREAK_MILESTONES:
            if current >= milestone:
                self._grant_milestone(session, user=user, milestone=milestone)

        next_milestone = next(
            (m for m in STREAK_MILESTONES if m > current), None,
        )
        return StreakInfo(current=current, longest=longest, next_milestone=next_milestone)

    def freeze(self, session, user_id: UUID, *, on: date | None = None) -> FreezeResult:
        """Consume one of the user's 2 Floor-Manager streak freezes for
        `on` (default: the user's local today). D4: persists a countable
        `StreakFreezeRow`, never a scan-time tolerance. D5: refuses visibly
        (a typed reason, never a silent no-op) when the caller isn't
        entitled — checked via `entitlements.effective_plan_for_user`, not a
        hand-rolled plan comparison.
        """
        user = session.execute(
            select(User).where(User.id == user_id)
        ).scalar_one_or_none()
        if user is None:
            return FreezeResult(False, "not_entitled", 0)

        if effective_plan_for_user(user.id) != Plan.FLOOR_MANAGER:
            return FreezeResult(False, "not_entitled", 0)

        target_date = on or _utcnow().astimezone(_user_tz(user)).date()
        period_key = str(target_date.year)

        # DEF119: the cap is enforced by a COUNT-then-INSERT, which is a
        # check-then-act race — two concurrent calls for the *same* user+year
        # but *different* target dates can both read the stale COUNT before
        # either commits. `UniqueConstraint(user_id, frozen_date)` only
        # blocks re-freezing the same date, not this. A transaction-scoped
        # Postgres advisory lock keyed on (user_id, period) forces the second
        # concurrent call to block until the first commits, so its COUNT
        # sees the first's row. Gated to postgresql: SQLite (the test engine)
        # has no advisory locks and its own coarse file-level write lock
        # already serialises writers, which is exactly why this race could
        # not be mutation-confirmed on this machine (see the test's
        # docstring) — the lock below is load-bearing only in production.
        if session.get_bind().dialect.name == "postgresql":
            session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
                {"key": f"streak_freeze:{user_id}:{period_key}"},
            )

        used = session.execute(
            select(func.count()).select_from(StreakFreezeRow).where(
                StreakFreezeRow.user_id == user_id,
                StreakFreezeRow.period_key == period_key,
            )
        ).scalar_one()
        remaining = FREEZES_PER_YEAR - int(used)
        if remaining <= 0:
            return FreezeResult(False, "limit_reached", 0)

        session.add(StreakFreezeRow(
            id=uuid4(), user_id=user_id, frozen_date=target_date,
            period_key=period_key, created_at=_utcnow(),
        ))
        try:
            session.flush()
        except IntegrityError:
            # Concurrent double-freeze of the same date, or a repeat call —
            # UNIQUE(user_id, frozen_date) is the backstop (DEF039 pattern).
            session.rollback()
            return FreezeResult(False, "already_frozen", remaining)

        logger.info(
            "streak_freeze_consumed",
            user_id=str(user_id), frozen_date=target_date.isoformat(),
            period_key=period_key, remaining=remaining - 1,
        )
        return FreezeResult(True, None, remaining - 1)

    def badges(self, session, user_id: UUID) -> list[BadgeRow]:
        """CR091 read path — every badge this user has ever earned."""
        return list(session.execute(
            select(BadgeRow)
            .where(BadgeRow.user_id == user_id)
            .order_by(BadgeRow.earned_at)
        ).scalars().all())

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

    def _frozen_days(self, session, user: User) -> set[date]:
        return set(session.execute(
            select(StreakFreezeRow.frozen_date)
            .where(StreakFreezeRow.user_id == user.id)
        ).scalars().all())

    def _award_badge(
        self, session, *, user: User, badge_key: str, ref_id: str,
        is_permanent_flair: bool,
    ) -> None:
        """CR091/CR092 — co-located with the credit grant in
        `_grant_milestone`, gated by the SAME reputation_events guard row
        (D1: not a parallel idempotency path). UNIQUE(user_id, badge_key) on
        BadgeRow is defense-in-depth, not the primary guard."""
        already = session.execute(
            select(BadgeRow.id).where(
                BadgeRow.user_id == user.id, BadgeRow.badge_key == badge_key,
            ).limit(1)
        ).scalar_one_or_none()
        if already is not None:
            return
        # DEF220 — chosen outcome on a lost race: SKIP. This is the clean
        # idempotent case: a badge awarded twice IS a skip, the docstring above
        # already says UNIQUE(user_id, badge_key) is defence-in-depth, and the
        # row's existence is the entire desired end state.
        #
        # It is safe to swallow here specifically because the MONETIZED half is
        # guarded elsewhere and separately: `_grant_milestone` gates the credit
        # grant on the `reputation_events` ref row via `award(_raise_on_race)`
        # (DEF049), so swallowing a badge collision cannot double-grant credits.
        # The SAVEPOINT keeps this rollback off the caller's transaction, which
        # is carrying that credit grant.
        try:
            with session.begin_nested():
                session.add(BadgeRow(
                    id=uuid4(), user_id=user.id, badge_key=badge_key,
                    ref_type="streak_milestone", ref_id=ref_id,
                    is_permanent_flair=is_permanent_flair, earned_at=_utcnow(),
                ))
                session.flush()
        except IntegrityError:
            logger.info(
                "badge_award_lost_race", user_id=str(user.id), badge_key=badge_key,
            )
            return
        logger.info("badge_awarded", user_id=str(user.id), badge_key=badge_key)

    def _grant_milestone(self, session, *, user: User, milestone: int) -> None:
        """Points + credits + badge for one streak milestone, exactly once
        ever — the reputation_events ref row doubles as the credit-grant AND
        badge-award guard (D1/D2)."""
        event_type = f"streak_{milestone}"
        ref_id = f"streak-{milestone}"
        if self._already_awarded(
            session, user_id=user.id, event_type=event_type, ref_id=ref_id,
        ):
            return
        # always_record so the guard row persists even when the daily point
        # cap clips this milestone to a zero-point award; without it the
        # credit grant below re-fires on every subsequent streak() call (F1).
        # _raise_on_race (DEF049) so a concurrent same-milestone race that
        # rolled our guard-row insert back skips the credit grant below —
        # otherwise the loser double-grants a monetized currency.
        try:
            self.award(
                session, user_id=user.id, event_type=event_type,
                ref_id=ref_id, always_record=True, _raise_on_race=True,
            )
        except _AwardRaceLost:
            return

        self._award_badge(
            session, user=user, badge_key=BADGE_KEYS[milestone], ref_id=ref_id,
            is_permanent_flair=milestone in PERMANENT_FLAIR_MILESTONES,
        )

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


def _run_ending_at(
    days: set[date], end: date, frozen: frozenset[date] = frozenset(),
) -> int:
    """Consecutive-day run ending at `end`. CR094: a frozen day (no
    activity, but a consumed StreakFreezeRow) pauses the run instead of
    breaking it — it doesn't add to the count either, it's just transparent."""
    run = 0
    cursor = end
    while True:
        if cursor in days:
            run += 1
            cursor -= timedelta(days=1)
        elif cursor in frozen:
            cursor -= timedelta(days=1)
        else:
            break
    return run


def _longest_run(days: set[date], frozen: frozenset[date] = frozenset()) -> int:
    longest = 0
    for d in days:
        prev = d - timedelta(days=1)
        if prev not in days and prev not in frozen:  # run start
            run = 1
            cursor = d + timedelta(days=1)
            while cursor in days or cursor in frozen:
                if cursor in days:
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
