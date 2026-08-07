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
from typing import Any, Literal
from uuid import UUID, uuid4

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.core.logging import logger
from app.db import get_session, init_schema
from app.db.models import NotificationRow
from app.services.rate_limit import RateLimiter

_ONESIGNAL_API_BASE = "https://onesignal.com/api/v1"
_TIMEOUT = httpx.Timeout(10.0)

PushStatus = Literal["sent", "rate_limited", "not_configured", "failed", "skipped"]

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


def notify(
    user_id: UUID,
    type: str,
    title: str,
    body: str,
    deep_link: dict[str, Any],
    source_ref: str | None = None,
    *,
    attempt_push: bool = True,
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
    """
    init_schema()
    notification_id = uuid4()
    with get_session() as s:
        s.add(NotificationRow(
            id=notification_id,
            user_id=user_id,
            type=type,
            title=title,
            body=body,
            deep_link=deep_link,
            source_ref=source_ref,
        ))

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

    try:
        resp = httpx.post(
            f"{_ONESIGNAL_API_BASE}/notifications",
            json={
                "app_id": settings.onesignal_app_id,
                "include_external_user_ids": [str(user_id)],
                "headings": {"en": title},
                "contents": {"en": body},
                "data": deep_link,
            },
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
