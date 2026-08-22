"""notification_service — CR027, the single write path for every
notification in the app.

`notify()` writes a durable `notifications` row unconditionally, then
best-effort attempts an OneSignal push. Push failure, a rate limit, or an
unconfigured key never blocks the row — the row IS the source of truth;
push is best-effort delivery on top of it (CR040: a feature that only
works when an external service cooperates must degrade LOUDLY, never
silently, when it doesn't).

Every feature that wants to notify a user (price alerts, daily challenge,
game events, trial-end, Room verdicts, ...) calls `notify()` — nobody
calls OneSignal directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, Mapping
from uuid import UUID, uuid4

import httpx
from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.logging import logger
from app.db import get_session, init_schema
from app.db.models import NotificationPreferenceRow, NotificationRow
from app.schemas.notifications import (
    NOTIFICATION_TYPES,
    NotificationOut,
    NotificationPreferenceOut,
)
from app.services.rate_limit import RateLimiter

_ONESIGNAL_API_BASE = "https://onesignal.com/api/v1"
_TIMEOUT = httpx.Timeout(10.0)

PushStatus = Literal[
    "sent", "rate_limited", "not_configured", "failed", "skipped", "duplicate",
    # CR135 — the user disabled this type in notification preferences; the
    # durable row is still written, only push delivery is suppressed.
    "pref_disabled",
    # DEF359 — OneSignal accepted the request and delivered it to nobody.
    # A 200 whose body reads {"id":"","errors":["All included players are not
    # subscribed"]} is the normal answer for a user with no registered device,
    # and it is NOT a send. Distinct from "failed", which means the API
    # rejected us.
    "no_recipients",
]

# Service-layer limits, not per-consumer (CR027 acceptance) — every caller
# of notify() shares the same per-user push budget regardless of type.
_push_per_minute = RateLimiter(name="notification_push_per_user_minute", per_minute=1)
_push_per_hour = RateLimiter(
    name="notification_push_per_user_hour", per_minute=3, window_seconds=3600,
)


@dataclass
class NotifyResult:
    notification_id: UUID
    push_status: PushStatus
    push_detail: str | None = None

    @property
    def was_duplicate(self) -> bool:
        """True when `uq_notifications_dedupe` rejected this write because a
        row for the same `(user_id, type, source_ref)` already existed.

        Callers that pass a `source_ref` MUST branch on this: it is the
        signal that they lost a race and someone else already notified this
        user for this business key. Treating it as an ordinary
        push-didn't-send means delivering the message anyway on a fallback
        channel — which is the double-send the constraint exists to stop."""
        return self.push_status == "duplicate"


def notify(
    user_id: UUID,
    type: str,
    title: str,
    body: str,
    deep_link: dict[str, Any],
    source_ref: str | None = None,
    *,
    attempt_push: bool = True,
    created_at: datetime | None = None,
) -> NotifyResult:
    """The only write path. Writes the row, then best-effort pushes.

    `attempt_push=False` (CR095): still writes the durable row — this is
    the only place `notifications` is written, per the table's own
    docstring — but skips the OneSignal call entirely. For a caller that
    has already decided, by product rule rather than by delivery failure,
    that THIS user should not receive a push (e.g. daily_reminder routes
    push to paid tiers only and must not push a free-tier user just
    because they happen to have a device registered). Every existing
    caller is unaffected — this is a keyword-only, default-True addition.

    `created_at` (CR095 audit fix): stamp the row with the caller's own clock
    instead of the column default. A caller whose dedupe reads `created_at`
    back — `daily_reminder` compares it against the `now` its sweep was given
    — otherwise compares two different clocks, and any caller that supplies a
    `now` (every test, and any backfill or replay) silently gets nonsense: the
    row is stamped with real wall time while the comparison uses simulated
    time. Production behaviour is identical either way, because there the two
    clocks are the same one. Default None keeps the column default.
    """
    init_schema()
    notification_id = uuid4()
    try:
        with get_session() as s:
            row = NotificationRow(
                id=notification_id,
                user_id=user_id,
                type=type,
                title=title,
                body=body,
                deep_link=deep_link,
                source_ref=source_ref,
            )
            if created_at is not None:
                row.created_at = created_at
            s.add(row)
    except IntegrityError:
        # `uq_notifications_dedupe` — someone else already wrote a row for
        # this exact (user_id, type, source_ref). The losing racer must see
        # a normal, describable outcome, not an unhandled 500: the whole
        # point of the constraint is that the DB, not a comment about
        # deployment topology, decides who wins. Return the winner's id so
        # the caller can still reference the notification that does exist.
        existing_id = _existing_notification_id(user_id, type, source_ref)
        logger.info(
            "notification_duplicate_suppressed",
            user_id=str(user_id), type=type, source_ref=source_ref,
            existing_notification_id=str(existing_id) if existing_id else None,
        )
        return NotifyResult(
            notification_id=existing_id or notification_id,
            push_status="duplicate",
            push_detail=None,
        )

    if not attempt_push:
        _record_push_outcome(notification_id, "skipped", None)
        return NotifyResult(
            notification_id=notification_id, push_status="skipped", push_detail=None,
        )

    if not _push_enabled_by_preference(user_id, type):
        # CR135 — server-enforced preference: the row above IS in the user's
        # in-app centre; only the OneSignal attempt is suppressed. Checked
        # before the rate limiter so an opted-out type never consumes the
        # user's push budget.
        logger.info(
            "notification_push_pref_disabled",
            user_id=str(user_id), notification_id=str(notification_id), type=type,
        )
        _record_push_outcome(notification_id, "pref_disabled", None)
        return NotifyResult(
            notification_id=notification_id, push_status="pref_disabled",
            push_detail=None,
        )

    push_status, push_detail = _attempt_push(
        user_id=user_id, notification_id=notification_id, type=type, title=title,
        body=body, deep_link=deep_link,
    )
    _record_push_outcome(notification_id, push_status, push_detail)
    return NotifyResult(
        notification_id=notification_id, push_status=push_status, push_detail=push_detail,
    )


def _record_push_outcome(
    notification_id: UUID, status: PushStatus, detail: str | None,
) -> None:
    """Persist what happened to the push (DEF360).

    Best-effort by the same reasoning the push itself is best-effort: the
    durable notification row is the product, and failing to annotate it must
    never turn a delivered push into a 500 for the caller. But it is written,
    because the alternative — logging it — is what made CR176 unanswerable.
    Container logs die at every `docker compose up --build`, i.e. every
    promotion, so a host that had genuinely delivered pushes could not show
    that it had.
    """
    try:
        with get_session() as s:
            row = s.get(NotificationRow, notification_id)
            if row is not None:
                row.push_status = status
                row.push_detail = detail
    except Exception as exc:  # noqa: BLE001 - annotation must not break delivery
        logger.warning(
            "notification_push_outcome_not_recorded",
            notification_id=str(notification_id), error=str(exc)[:200],
        )


def _existing_notification_id(
    user_id: UUID, type: str, source_ref: str | None,
) -> UUID | None:
    """The id of the row that won the dedupe race. Best-effort: a failure to
    look it up must not turn a suppressed duplicate into an exception."""
    try:
        with get_session() as s:
            return s.execute(
                select(NotificationRow.id).where(
                    NotificationRow.user_id == user_id,
                    NotificationRow.type == type,
                    NotificationRow.source_ref == source_ref,
                ).limit(1)
            ).scalars().first()
    except Exception:
        logger.exception("notification_duplicate_lookup_failed")
        return None


def _attempt_push(
    *, user_id: UUID, notification_id: UUID, type: str, title: str, body: str,
    deep_link: dict[str, Any],
) -> tuple[PushStatus, str | None]:
    key = str(user_id)
    try:
        _push_per_minute.check(key)
        _push_per_hour.check(key)
    except HTTPException:
        return "rate_limited", None

    if not settings.onesignal_app_id or not settings.onesignal_rest_key:
        # CR040: a missing key is a LOUD refusal, not a silent no-op. The
        # notifications row above already exists — this only skips push.
        logger.warning(
            "notification_push_not_configured",
            user_id=str(user_id), notification_id=str(notification_id), type=type,
        )
        return "not_configured", None

    payload: dict[str, Any] = {
        "app_id": settings.onesignal_app_id,
        "include_external_user_ids": [str(user_id)],
        "headings": {"en": title},
        "contents": {"en": body},
        "data": deep_link,
    }
    if settings.onesignal_android_channel_id:
        # DEF333 — without this, OneSignal auto-creates a Android fallback
        # channel at IMPORTANCE_DEFAULT: no heads-up banner, and OS-level
        # adaptive notification management (observed on Samsung One UI)
        # mutes it within minutes. This points at a dashboard-configured
        # "Urgent" channel instead. No effect on iOS.
        payload["android_channel_id"] = settings.onesignal_android_channel_id

    try:
        resp = httpx.post(
            f"{_ONESIGNAL_API_BASE}/notifications",
            json=payload,
            headers={
                "Authorization": f"Key {settings.onesignal_rest_key}",
                "Content-Type": "application/json",
            },
            timeout=_TIMEOUT,
        )
    except httpx.RequestError as exc:
        logger.warning(
            "notification_push_error",
            user_id=str(user_id), notification_id=str(notification_id), error=str(exc),
        )
        return "failed", str(exc)

    if resp.status_code >= 400:
        logger.warning(
            "notification_push_rejected",
            user_id=str(user_id), notification_id=str(notification_id),
            status_code=resp.status_code, body=resp.text[:500],
        )
        return "failed", f"onesignal {resp.status_code}"

    # DEF359 — a 200 is not a delivery. OneSignal answers a request naming an
    # external id with no subscribed device with HTTP 200 and a body of
    # {"id":"","errors":["All included players are not subscribed"]}. Reading
    # only the status code logged `notification_push_sent` for that, so "have
    # we ever actually pushed to anyone?" was unanswerable from our own logs:
    # the success line said sent whether one device got it or none did. This is
    # the CR040 shape — the failing state was invisible in the output a human
    # reads — and it is why CR176 could sit for days as "never proven to send"
    # with nothing able to settle it either way.
    try:
        detail = resp.json()
    except ValueError:
        detail = {}
    recipients = detail.get("recipients")
    errors = detail.get("errors")
    if recipients == 0 or (not detail.get("id") and errors):
        reason = errors[0] if isinstance(errors, list) and errors else "0 recipients"
        logger.warning(
            "notification_push_no_recipients",
            user_id=str(user_id), notification_id=str(notification_id),
            type=type, reason=str(reason)[:200],
        )
        return "no_recipients", str(reason)[:200]

    logger.info(
        "notification_push_sent",
        user_id=str(user_id), notification_id=str(notification_id), type=type,
        recipients=recipients,
    )
    return "sent", None


def _push_enabled_by_preference(user_id: UUID, type: str) -> bool:
    """False only when a stored row says enabled=False. No row — including a
    type outside today's vocabulary — means enabled (CR027's behaviour). A
    lookup failure keeps that default but logs loudly (CR040): a broken
    preferences read must not silently kill delivery."""
    try:
        with get_session() as s:
            enabled = s.execute(
                select(NotificationPreferenceRow.enabled).where(
                    NotificationPreferenceRow.user_id == user_id,
                    NotificationPreferenceRow.type == type,
                )
            ).scalars().first()
    except Exception:
        logger.exception(
            "notification_pref_lookup_failed",
        )
        return True
    return enabled is not False


def _out(row: NotificationRow) -> NotificationOut:
    return NotificationOut(
        id=row.id, type=row.type, title=row.title, body=row.body,
        deep_link=row.deep_link, source_ref=row.source_ref,
        read_at=row.read_at, created_at=row.created_at,
    )


def list_notifications(
    user_id: UUID, *, limit: int = 50, offset: int = 0,
) -> tuple[list[NotificationOut], int]:
    """One page of the user's notifications, newest-first, plus the total
    row count for paging. `id` desc as tiebreak keeps equal-timestamp pages
    deterministic across requests."""
    init_schema()
    with get_session() as s:
        total = s.execute(
            select(func.count()).select_from(NotificationRow).where(
                NotificationRow.user_id == user_id,
            )
        ).scalar_one()
        rows = s.execute(
            select(NotificationRow)
            .where(NotificationRow.user_id == user_id)
            .order_by(NotificationRow.created_at.desc(), NotificationRow.id.desc())
            .limit(limit)
            .offset(offset)
        ).scalars().all()
        return [_out(r) for r in rows], total


def mark_read(user_id: UUID, notification_id: UUID) -> bool:
    """Idempotent: an already-read row is success with its original stamp
    untouched. False = no such row FOR THIS USER — the user_id predicate is
    the authorization (CR102 pattern), so the caller 404s identically for a
    foreign row and a nonexistent id."""
    init_schema()
    with get_session() as s:
        row = s.execute(
            select(NotificationRow).where(
                NotificationRow.id == notification_id,
                NotificationRow.user_id == user_id,
            )
        ).scalar_one_or_none()
        if row is None:
            return False
        if row.read_at is None:
            row.read_at = datetime.now(timezone.utc)
        return True


def mark_all_read(user_id: UUID) -> int:
    """Stamp every unread row; returns how many were stamped."""
    init_schema()
    with get_session() as s:
        result = s.execute(
            update(NotificationRow)
            .where(
                NotificationRow.user_id == user_id,
                NotificationRow.read_at.is_(None),
            )
            .values(read_at=datetime.now(timezone.utc))
        )
        return int(result.rowcount or 0)


def unread_count(user_id: UUID) -> int:
    init_schema()
    with get_session() as s:
        return s.execute(
            select(func.count()).select_from(NotificationRow).where(
                NotificationRow.user_id == user_id,
                NotificationRow.read_at.is_(None),
            )
        ).scalar_one()


def get_preferences(user_id: UUID) -> list[NotificationPreferenceOut]:
    """Every type in the vocabulary, defaults filled in: no stored row means
    enabled=True with updated_at=None (never toggled)."""
    init_schema()
    with get_session() as s:
        stored = {
            r.type: r
            for r in s.execute(
                select(NotificationPreferenceRow).where(
                    NotificationPreferenceRow.user_id == user_id,
                )
            ).scalars()
        }
        return [
            NotificationPreferenceOut(
                type=t,
                enabled=stored[t].enabled if t in stored else True,
                updated_at=stored[t].updated_at if t in stored else None,
            )
            for t in NOTIFICATION_TYPES
        ]


def set_preferences(
    user_id: UUID, updates: Mapping[str, bool],
) -> list[NotificationPreferenceOut]:
    """Upsert one row per named type, then return the full refreshed set.
    Unknown types raise ValueError — the API layer's schema already 422s
    them; this keeps a future non-API caller equally loud (CR040)."""
    unknown = sorted(set(updates) - set(NOTIFICATION_TYPES))
    if unknown:
        raise ValueError(f"unknown notification type(s): {', '.join(unknown)}")
    init_schema()
    now = datetime.now(timezone.utc)
    for t, enabled in updates.items():
        # P15: the get-then-add pair races a concurrent writer on the composite
        # PK; the loser's INSERT is converted into the UPDATE it meant to be.
        try:
            with get_session() as s:
                row = s.get(NotificationPreferenceRow, (user_id, t))
                if row is None:
                    s.add(NotificationPreferenceRow(
                        user_id=user_id, type=t, enabled=enabled, updated_at=now,
                    ))
                else:
                    row.enabled = enabled
                    row.updated_at = now
        except IntegrityError:
            with get_session() as s:
                row = s.get(NotificationPreferenceRow, (user_id, t))
                if row is None:
                    raise
                row.enabled = enabled
                row.updated_at = now
    return get_preferences(user_id)
