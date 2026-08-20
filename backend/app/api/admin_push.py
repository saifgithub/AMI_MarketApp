"""Admin push console API — /v1/admin/push/* (CR200).

The first HTTP path into `notify()` — until now an admin push meant
`docker exec … scripts.send_notification` on melehost (CR193). Same
contract as every automated consumer: durable `notifications` row first,
best-effort OneSignal push on top, dedupe intact.

Preview-before-send, copying the CR102 messages mis-blast guard: the
console arms SEND only against the exact previewed target, and the
preview shows the device list + whether push is even configured in this
container, so "sent" can't silently mean "row written, pushed nowhere".

Endpoint map:
  POST /v1/admin/push/preview   Resolve target user (id or email) → summary + devices + push_configured
  POST /v1/admin/push           Send: notify() → {notification_id, push_status, push_detail}
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.admin import _get_user_or_404, _load_devices, _user_summary, get_admin
from app.core.config import settings
from app.db import get_session
from app.db.models import User
from app.schemas.admin import (
    AdminPushPreviewRequest,
    AdminPushPreviewResponse,
    AdminPushSendRequest,
    AdminPushSendResponse,
    AdminUserDevice,
)
from app.services.admin_audit import record_admin_action
from app.services.cf_access import AdminIdentity
from app.services.notification_service import notify

router = APIRouter(prefix="/v1/admin/push", tags=["admin"])


@router.post("/preview", response_model=AdminPushPreviewResponse)
def preview_push(
    req: AdminPushPreviewRequest, _: AdminIdentity = Depends(get_admin),
) -> AdminPushPreviewResponse:
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


@router.post("", response_model=AdminPushSendResponse)
def send_push(
    req: AdminPushSendRequest, admin: AdminIdentity = Depends(get_admin),
) -> AdminPushSendResponse:
    with get_session() as s:
        _get_user_or_404(s, req.user_id)

    deep_link: dict[str, Any] = {}
    if req.route:
        deep_link["route"] = req.route
    if req.ticker:
        deep_link["ticker"] = req.ticker
    if req.params:
        deep_link.update(req.params)

    result = notify(
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
