"""Admin routes for the waitlist batch invite (CR267 WP-51).

Guarded by the shared `ADMIN_SECRET` sent as `X-Admin-Secret`. An unset secret
fails CLOSED (503, logged at ERROR): an unconfigured admin surface must never
read as open. Intended use from the Mac:

    curl -H "X-Admin-Secret: $S" https://api-website.agenticmarketintel.ai/admin/waitlist/export > batch.csv
    curl -H "X-Admin-Secret: $S" -H 'content-type: application/json' \
         -d '{"ids": ["<id>", ...], "batch": "wave-1"}' .../admin/waitlist/mark-invited
"""

from __future__ import annotations

import csv
import hmac
import io
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select, update

from app.core.config import settings
from app.core.logging import logger
from app.db.session import get_session
from app.models import WaitlistEntry
from app.services.rate_limit import admin_rate_limit

_COLUMNS = ["id", "email", "name", "country", "platform", "source", "consent_at", "created_at"]


def require_admin(x_admin_secret: str | None = Header(default=None)) -> None:
    if not settings.admin_secret:
        logger.error("admin_secret_not_configured")
        raise HTTPException(status_code=503, detail="admin_not_configured")
    if not x_admin_secret or not hmac.compare_digest(
        x_admin_secret.encode(), settings.admin_secret.encode()
    ):
        raise HTTPException(status_code=403, detail="forbidden")


router = APIRouter(
    prefix="/admin/waitlist",
    dependencies=[Depends(admin_rate_limit), Depends(require_admin)],
)


def _cell(value: object) -> str:
    """Stringify; neutralise spreadsheet formula injection (user-typed names)."""
    if value is None:
        return ""
    text = value.isoformat() if isinstance(value, datetime) else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@router.get("/export")
def export_uninvited(limit: int = Query(default=500, ge=1, le=5000)) -> Response:
    """CSV of sign-ups not yet invited, oldest first."""
    with get_session() as s:
        rows = s.scalars(
            select(WaitlistEntry)
            .where(WaitlistEntry.invited_at.is_(None))
            .order_by(WaitlistEntry.created_at, WaitlistEntry.id)
            .limit(limit)
        ).all()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(_COLUMNS)
        for r in rows:
            w.writerow([_cell(getattr(r, c)) for c in _COLUMNS])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="waitlist_uninvited.csv"'},
    )


class MarkInvitedRequest(BaseModel):
    ids: list[UUID] = Field(min_length=1, max_length=5000)
    batch: str | None = Field(default=None, max_length=64)


class MarkInvitedResponse(BaseModel):
    ok: bool
    marked: int


@router.post("/mark-invited", response_model=MarkInvitedResponse)
def mark_invited(req: MarkInvitedRequest) -> MarkInvitedResponse:
    """Stamp sign-ups as invited. Already-invited rows are left untouched."""
    now = datetime.now(timezone.utc)
    with get_session() as s:
        result = s.execute(
            update(WaitlistEntry)
            .where(WaitlistEntry.id.in_([str(i) for i in req.ids]))
            .where(WaitlistEntry.invited_at.is_(None))
            .values(invited_at=now, invite_batch=req.batch)
        )
        marked = result.rowcount or 0
    return MarkInvitedResponse(ok=True, marked=marked)
