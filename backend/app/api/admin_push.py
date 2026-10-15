"""Admin push console API — /v1/admin/push/* (CR200, audience mode CR200-R003).

The first HTTP path into `notify()` — until now an admin push meant
`docker exec … scripts.send_notification` on melehost (CR193). Same
contract as every automated consumer: durable `notifications` row first,
best-effort OneSignal push on top, dedupe intact.

Preview-before-send, copying the CR102 messages mis-blast guard: the
console arms SEND only against the exact previewed target, and the
preview shows the device list (single user) or the measured recipient
count (audience) plus whether push is even configured in this container,
so "sent" can't silently mean "row written, pushed nowhere".

Audience mode reuses the CR102 resolver, never a re-implementation: every
mode — including explicit `mode=user` ids — passes through the base
real-tester filter (suspended, house desks, CR035 synthetics, seed rows,
by-id exclusions), so a broadcast can never reach a non-tester.

Endpoint map:
  POST /v1/admin/push/preview   user_id | email → summary + devices + push_configured;
                                audience → {audience_mode, recipient_count, push_configured}
  POST /v1/admin/push           user_id → notify() → {notification_id, push_status, push_detail}
                                audience → per-user notify() loop → {recipient_count, status_counts},
                                one admin_audit "push_broadcast" row for the whole blast
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.admin import _get_user_or_404, _load_devices, _user_summary, get_admin
from app.core.config import settings
from app.core.logging import logger
from app.db import get_session
from app.db.models import User
from app.schemas.admin import (
    AdminPushAudiencePreviewResponse,
    AdminPushAudienceSendResponse,
    AdminPushPreviewRequest,
    AdminPushPreviewResponse,
    AdminPushSendRequest,
    AdminPushSendResponse,
    AdminUserDevice,
)
from app.services.admin_audit import record_admin_action
from app.services.cf_access import AdminIdentity
from app.services.inbox_store import resolve_audience
from app.services.notification_service import NotifyResult, notify

router = APIRouter(prefix="/v1/admin/push", tags=["admin"])


def _deep_link(req: AdminPushSendRequest) -> dict[str, Any]:
    deep_link: dict[str, Any] = {}
    if req.route:
        deep_link["route"] = req.route
    if req.ticker:
        deep_link["ticker"] = req.ticker
    if req.params:
        deep_link.update(req.params)
    return deep_link


@router.post(
    "/preview",
    response_model=AdminPushPreviewResponse | AdminPushAudiencePreviewResponse,
)
def preview_push(
    req: AdminPushPreviewRequest, _: AdminIdentity = Depends(get_admin),
) -> AdminPushPreviewResponse | AdminPushAudiencePreviewResponse:
    if req.audience is not None:
        with get_session() as s:
            recipient_count = len(resolve_audience(s, req.audience))
        return AdminPushAudiencePreviewResponse(
            audience_mode=req.audience.mode,
            recipient_count=recipient_count,
            push_configured=bool(
                settings.onesignal_app_id and settings.onesignal_rest_key
            ),
        )
    if not req.user_id and not req.email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "provide user_id or email")
    with get_session() as s:
        if req.user_id:
            user = _get_user_or_404(s, req.user_id)
        else:
            user = s.execute(
                select(User).where(User.email == req.email)
            ).scalar_one_or_none()
            if user is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
        devices = _load_devices(s, user.id)
        return AdminPushPreviewResponse(
            user=_user_summary(user),
            devices=[
                AdminUserDevice(
                    device_install_id=d.device_install_id,
                    device_model=d.device_model,
                    os_version=d.os_version,
                    app_version=d.app_version,
                    first_seen_at=d.first_seen_at,
                    last_seen_at=d.last_seen_at,
                )
                for d in devices
            ],
            push_configured=bool(
                settings.onesignal_app_id and settings.onesignal_rest_key
            ),
        )


@router.post(
    "",
    response_model=AdminPushSendResponse | AdminPushAudienceSendResponse,
)
def send_push(
    req: AdminPushSendRequest, admin: AdminIdentity = Depends(get_admin),
) -> AdminPushSendResponse | AdminPushAudienceSendResponse:
    deep_link = _deep_link(req)
    if req.audience is not None:
        with get_session() as s:
            recipients = resolve_audience(s, req.audience)
        status_counts: dict[str, int] = {}
        for uid in recipients:
            try:
                outcome = notify(
                    user_id=uid,
                    type=req.type,
                    title=req.title,
                    body=req.body,
                    deep_link=deep_link,
                )
                key: str = outcome.push_status
            except Exception:
                # CR040 — one bad recipient must not abort the blast, but the
                # failure lands in status_counts (and the audit payload), not
                # just a log line.
                logger.exception(
                    "admin_push_broadcast_recipient_failed",
                    user_id=str(uid), audience_mode=req.audience.mode,
                )
                key = "error"
            status_counts[key] = status_counts.get(key, 0) + 1
        with get_session() as s:
            record_admin_action(
                s, admin, "push_broadcast",
                target=f"audience:{req.audience.mode}",
                payload={
                    "title": req.title,
                    "type": req.type,
                    "recipient_count": len(recipients),
                    "status_counts": status_counts,
                },
            )
        return AdminPushAudienceSendResponse(
            recipient_count=len(recipients),
            status_counts=status_counts,
        )

    assert req.user_id is not None  # the request schema's xor guarantees this
    with get_session() as s:
        _get_user_or_404(s, req.user_id)

    result: NotifyResult = notify(
        user_id=req.user_id,
        type=req.type,
        title=req.title,
        body=req.body,
        deep_link=deep_link,
    )
    with get_session() as s:
        record_admin_action(
            s, admin, "push_sent", target=str(req.user_id),
            payload={
                "title": req.title,
                "type": req.type,
                "push_status": result.push_status,
            },
        )
    return AdminPushSendResponse(
        notification_id=result.notification_id,
        push_status=result.push_status,
        push_detail=result.push_detail,
    )
