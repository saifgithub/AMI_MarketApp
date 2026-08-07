"""daily_reminder — CR095. Daily-challenge reminder, push for paid tiers /
email for free tier, at each user's own local hour.

`send_due_reminders()` is the whole feature: for every user with
`users.daily_reminder_hour` set (NULL = reminders off), evaluate their LOCAL
time against `users.timezone` (CR095 reuses the existing column — no second
timezone field), and if their local hour has been reached today, they have
not already been reminded today, and they have not already engaged with
today's daily challenge, send exactly one reminder.

Channel is decided by *effective* plan (`entitlements.effective_plan_for_user`,
never the raw `users.plan` column, so an expired trial correctly falls back to
the free-tier channel): push for paid, email for free. Email is also the
fallback for a paid user whose push could not deliver — CR040 degrade-loudly,
never a silent no-op for someone paying for the app. A user reachable on
*no* channel at all (no email on file, or the email transport itself isn't
configured) is logged at ERROR and counted in the returned stats rather than
silently dropped.

Idempotency is entirely DB-derived, not in-memory: "already reminded today"
is answered by querying the `notifications` table (CR027) for a
`type="daily_reminder"` row whose `source_ref` is the user's *local* calendar
date — the same row `notification_service.notify()` always writes regardless
of channel or outcome. That makes a container restart mid-day safe by
construction (nothing here survives only in process memory) and makes the day
boundary the user's own, not UTC's.

`notify()` is still the ONLY writer of the `notifications` table (see its own
docstring) — including for the free-tier email path, which calls it with
`attempt_push=False` so the durable row still gets written without ever
firing a push to a free-tier user (push is a paid-tier product decision here,
not a delivery-failure fallback).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.logging import logger
from app.db import get_session, init_schema
from app.db.models import DailyChallengeAttemptRow, NotificationRow, User
from app.schemas.mandate import Plan
from app.services.daily_challenge_service import get_daily_challenge_service
from app.services.email_service import send_daily_reminder
from app.services.entitlements import effective_plan_for_user
from app.services.notification_service import notify

_NOTIFICATION_TYPE = "daily_reminder"
_TITLE = "Today's Daily Challenge"
_TEASER_MAX_CHARS = 140


def _teaser(question: str) -> str:
    q = question.strip()
    if len(q) <= _TEASER_MAX_CHARS:
        return q
    return q[: _TEASER_MAX_CHARS - 1].rstrip() + "…"


def _resolve_tz(user: User) -> tuple[ZoneInfo, bool]:
    """(tz, was_invalid). Never raises. A garbage `users.timezone` value
    degrades to UTC — but LOUDLY (logged + reported by the caller), never
    silently (CR040): the tick summary's `invalid_timezone` count is exactly
    this signal surfaced."""
    raw = user.timezone or "UTC"
    try:
        return ZoneInfo(raw), False
    except Exception as exc:
        logger.warning(
            "daily_reminder_invalid_timezone",
            user_id=str(user.id), timezone=raw, chosen="UTC", error=str(exc),
        )
        return ZoneInfo("UTC"), True


def _already_reminded_today(user_id: UUID, local_date: date) -> bool:
    with get_session() as s:
        row = s.execute(
            select(NotificationRow.id).where(
                NotificationRow.user_id == user_id,
                NotificationRow.type == _NOTIFICATION_TYPE,
                NotificationRow.source_ref == local_date.isoformat(),
            ).limit(1)
        ).first()
        return row is not None


def _already_engaged(user_id: UUID, challenge_id: str) -> bool:
    with get_session() as s:
        row = s.execute(
            select(DailyChallengeAttemptRow.id).where(
                DailyChallengeAttemptRow.user_id == user_id,
                DailyChallengeAttemptRow.challenge_id == challenge_id,
            ).limit(1)
        ).first()
        return row is not None


def send_due_reminders(now: datetime | None = None) -> dict[str, int]:
    """One sweep. Returns a stats dict — every branch a user can take through
    this function has its own counter, so "the tick ran fine" and "every
    reachable user actually got reminded" are two different, both-checkable
    claims (CR040: a job that reports success while quietly dropping users is
    exactly the failure mode this guards)."""
    init_schema()
    now = now or datetime.now(timezone.utc)
    stats = {
        "eligible": 0,
        "hour_not_reached": 0,
        "already_reminded": 0,
        "already_engaged": 0,
        "no_challenge_today": 0,
        "invalid_timezone": 0,
        "sent_push": 0,
        "sent_email": 0,
        "fallback_email": 0,
        "unreachable": 0,
        "errors": 0,
    }
    svc = get_daily_challenge_service()

    with get_session() as s:
        users = s.execute(
            select(User).where(User.daily_reminder_hour.is_not(None))
        ).scalars().all()

    for user in users:
        stats["eligible"] += 1
        try:
            _process_one_user(user, now, svc, stats)
        except Exception:
            stats["errors"] += 1
            logger.exception("daily_reminder_error", user_id=str(user.id))

    return stats


def _process_one_user(user: User, now: datetime, svc, stats: dict[str, int]) -> None:
    tz, invalid = _resolve_tz(user)
    if invalid:
        stats["invalid_timezone"] += 1

    local_now = now.astimezone(tz)
    if local_now.hour < user.daily_reminder_hour:
        stats["hour_not_reached"] += 1
        return
    local_date = local_now.date()

    if _already_reminded_today(user.id, local_date):
        stats["already_reminded"] += 1
        return

    challenge = svc.for_date(local_date)
    if challenge is None:
        stats["no_challenge_today"] += 1
        logger.warning(
            "daily_reminder_no_challenge_today",
            user_id=str(user.id), local_date=local_date.isoformat(),
        )
        return

    if _already_engaged(user.id, challenge.id):
        stats["already_engaged"] += 1
        return

    teaser = _teaser(challenge.question)
    body = f"AMI: {teaser}"
    deep_link = {"route": "open_daily_challenge", "challenge_id": challenge.id}
    source_ref = local_date.isoformat()
    plan = effective_plan_for_user(user.id)
    is_paid = plan != Plan.FLOOR_PASS

    if is_paid:
        result = notify(user.id, _NOTIFICATION_TYPE, _TITLE, body, deep_link, source_ref=source_ref)
        if result.push_status == "sent":
            stats["sent_push"] += 1
            logger.info("daily_reminder_sent", user_id=str(user.id), channel="push")
            return
        # Push could not deliver (not_configured / failed / rate_limited).
        # The `notifications` row is already written (notify()'s
        # unconditional row-write) — this only decides the fallback channel.
        if not user.email:
            stats["unreachable"] += 1
            logger.error(
                "daily_reminder_unreachable",
                user_id=str(user.id), plan=plan.value,
                push_status=result.push_status, reason="push_failed_no_email_on_file",
            )
            return
        attempted = send_daily_reminder(user.email, teaser)
        if attempted:
            stats["fallback_email"] += 1
            logger.warning(
                "daily_reminder_push_failed_email_fallback",
                user_id=str(user.id), push_status=result.push_status,
            )
        else:
            stats["unreachable"] += 1
            logger.error(
                "daily_reminder_unreachable",
                user_id=str(user.id), plan=plan.value,
                push_status=result.push_status,
                reason="push_failed_and_email_transport_not_configured",
            )
        return

    # Free tier: email only. Push is never attempted — not a delivery
    # failure, a product decision — but the durable row still gets written
    # via notify(attempt_push=False), same idempotency guarantee as the
    # paid path.
    if not user.email:
        notify(
            user.id, _NOTIFICATION_TYPE, _TITLE, body, deep_link,
            source_ref=source_ref, attempt_push=False,
        )
        stats["unreachable"] += 1
        logger.error(
            "daily_reminder_unreachable",
            user_id=str(user.id), plan=plan.value, reason="no_email_on_file_free_tier",
        )
        return

    attempted = send_daily_reminder(user.email, teaser)
    notify(
        user.id, _NOTIFICATION_TYPE, _TITLE, body, deep_link,
        source_ref=source_ref, attempt_push=False,
    )
    if attempted:
        stats["sent_email"] += 1
        logger.info("daily_reminder_sent", user_id=str(user.id), channel="email")
    else:
        stats["unreachable"] += 1
        logger.error(
            "daily_reminder_unreachable",
            user_id=str(user.id), plan=plan.value, reason="email_transport_not_configured",
        )
