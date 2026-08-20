"""Admin bug triage API — /v1/admin/bugs/* (CR200).

The console's half of the bug lifecycle `/fix-bugs` drives over psql:
open → in_progress (claim) → pending_review → resolved, plus reopen.
Claim/resolve/reopen are single guarded UPDATEs in FeedbackStore, so a
console operator and a psql agent can never double-claim (409 on loss).

Endpoint map:
  GET    /v1/admin/bugs                     List + per-status counts (?status=&limit=&offset=)
  GET    /v1/admin/bugs/{id}                Full detail
  POST   /v1/admin/bugs/{id}/claim          {branch} → in_progress, 409 if not open
  POST   /v1/admin/bugs/{id}/resolve        {note} → resolved, 409 if already resolved
  POST   /v1/admin/bugs/{id}/reopen         → open, releases claim, 409 if already open
  GET    /v1/admin/bugs/{id}/attachment     The submitted photo/file, 404 when none
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.api.admin import get_admin
from app.core.config import settings
from app.db import get_session
from app.db.models import BugReportRow
from app.schemas.admin import (
    AdminBugClaimRequest,
    AdminBugDetail,
    AdminBugListResponse,
    AdminBugResolveRequest,
    AdminBugSummary,
)
from app.services.admin_audit import record_admin_action
from app.services.cf_access import AdminIdentity
from app.services.feedback_store import get_feedback_store

router = APIRouter(prefix="/v1/admin/bugs", tags=["admin"])

# The lifecycle's core statuses (fix-bugs.md) — the console renders these
# first. Deliberately NOT a validation whitelist: live bug_reports already
# carries statuses written freely by psql lanes ("investigating",
# "wont_fix", …), and a filter that 400s on a status the data actually
# holds hides rows instead of showing them. The filter is a plain bound
# equality — any string is safe.
_CORE_STATUSES = ("open", "in_progress", "pending_review", "resolved")


def _summary(r: BugReportRow) -> AdminBugSummary:
    return AdminBugSummary(
        id=r.id,
        user_id=r.user_id,
        category=r.category,
        title=r.title,
        status=r.status,
        assigned_branch=r.assigned_branch,
        app_version=r.app_version,
        platform=r.platform,
        has_attachment=bool(r.attachment_path),
        created_at=r.created_at,
        resolved_at=r.resolved_at,
    )


def _detail(r: BugReportRow) -> AdminBugDetail:
    return AdminBugDetail(
        **_summary(r).model_dump(),
        steps=r.steps,
        route=r.route,
        attachment_mime=r.attachment_mime,
        resolution_note=r.resolution_note,
        acknowledged_at=r.acknowledged_at,
    )


def _get_or_404(report_id: UUID) -> BugReportRow:
    row = get_feedback_store().admin_get(report_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "bug report not found")
    return row


@router.get("", response_model=AdminBugListResponse)
def list_bugs(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: AdminIdentity = Depends(get_admin),
) -> AdminBugListResponse:
    rows, total, counts = get_feedback_store().admin_list(
        status=status_filter, limit=limit, offset=offset,
    )
    return AdminBugListResponse(
        bugs=[_summary(r) for r in rows],
        total=total,
        counts=counts,
        limit=limit,
        offset=offset,
    )


@router.get("/{report_id}", response_model=AdminBugDetail)
def get_bug(
    report_id: UUID, _: AdminIdentity = Depends(get_admin),
) -> AdminBugDetail:
    return _detail(_get_or_404(report_id))


@router.post("/{report_id}/claim", response_model=AdminBugDetail)
def claim_bug(
    report_id: UUID,
    req: AdminBugClaimRequest,
    admin: AdminIdentity = Depends(get_admin),
) -> AdminBugDetail:
    row = _get_or_404(report_id)
    if not get_feedback_store().admin_claim(report_id, req.branch):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"not claimable — status is '{row.status}'"
            + (f", claimed by {row.assigned_branch}" if row.assigned_branch else ""),
        )
    with get_session() as s:
        record_admin_action(
            s, admin, "bug_claimed", target=str(report_id),
            payload={"branch": req.branch},
        )
    return _detail(_get_or_404(report_id))


@router.post("/{report_id}/resolve", response_model=AdminBugDetail)
def resolve_bug(
    report_id: UUID,
    req: AdminBugResolveRequest,
    admin: AdminIdentity = Depends(get_admin),
) -> AdminBugDetail:
    _get_or_404(report_id)
    if not get_feedback_store().admin_resolve(report_id, req.note):
        raise HTTPException(status.HTTP_409_CONFLICT, "already resolved")
    with get_session() as s:
        record_admin_action(
            s, admin, "bug_resolved", target=str(report_id),
            payload={"note": req.note},
        )
    return _detail(_get_or_404(report_id))


@router.post("/{report_id}/reopen", response_model=AdminBugDetail)
def reopen_bug(
    report_id: UUID,
    admin: AdminIdentity = Depends(get_admin),
) -> AdminBugDetail:
    _get_or_404(report_id)
    if not get_feedback_store().admin_reopen(report_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "already open")
    with get_session() as s:
        record_admin_action(s, admin, "bug_reopened", target=str(report_id))
    return _detail(_get_or_404(report_id))


@router.get("/{report_id}/attachment")
def get_attachment(
    report_id: UUID, _: AdminIdentity = Depends(get_admin),
) -> FileResponse:
    row = _get_or_404(report_id)
    if not row.attachment_path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no attachment")
    base = Path(settings.bug_attachments_dir).resolve()
    full = (base / row.attachment_path).resolve()
    # attachment_path is server-written, but a traversal guard costs one
    # line and makes the invariant structural rather than assumed.
    if not full.is_relative_to(base):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no attachment")
    if not full.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "attachment file missing")
    return FileResponse(full, media_type=row.attachment_mime or "application/octet-stream")
