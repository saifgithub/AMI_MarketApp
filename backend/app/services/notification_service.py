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
from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.logging import logger
from app.db import get_session, init_schema
from app.db.models import NotificationRow
from app.services.rate_limit import RateLimiter

_ONESIGNAL_API_BASE = "https://onesignal.com/api/v1"
_TIMEOUT = httpx.Timeout(10.0)

PushStatus = Literal[
    "sent", "rate_limited", "not_configured", "failed", "skipped", "duplicate",
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
        return NotifyResult(
            notification_id=notification_id, push_status="skipped", push_detail=None,
        )

    push_status, push_detail = _attempt_push(
        user_id=user_id, notification_id=notification_id, type=type, title=title,
        body=body, deep_link=deep_link,
    )
    return NotifyResult(
        notification_id=notification_id, push_status=push_status, push_detail=push_detail,
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

    logger.info(
        "notification_push_sent",
        user_id=str(user_id), notification_id=str(notification_id), type=type,
    )
    return "sent", None
