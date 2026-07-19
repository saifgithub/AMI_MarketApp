"""Feedback routes — in-app bug reporting.

POST /v1/feedback/bug  — submit a bug report (anonymous sessions accepted)

Accepts multipart/form-data so the iPhone reporter can attach a photo.
All fields except `file` are required; the file is optional. The legacy
JSON shape is dropped — the client has been multipart-only since AT:R20
landed (build 0.1.0+5). If you need to call this from curl, use:

  curl -F category=ui_glitch -F title=foo -F app_version=0.1.0+5 \
       -F platform=ios -F file=@screenshot.png .../v1/feedback/bug

Auth: standard Bearer token. The user_id is extracted from the token
when present; missing or unrecognised tokens fall back to user_id=None
so the report is still accepted (we'd rather lose the user_id than
lose the report).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile, status

from app.core.logging import logger
from app.schemas.feedback import (
    BugReportRequest,
    BugReportResponse,
    BugResolutionUpdate,
)
from app.services.auth_service import parse_scaffold_token
from app.services.bug_attachments import (
    AttachmentRejected,
    is_allowed_mime,
    save_attachment_streaming,
)
from app.services.feedback_store import get_feedback_store

router = APIRouter(prefix="/v1/feedback", tags=["feedback"])


def _resolve_user_id(authorization: str | None) -> UUID | None:
    """Extract user_id from the Bearer token; returns None rather than raising.

    Bug reports are accepted from un-authed or partially-authed sessions.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    return parse_scaffold_token(token)


@router.post(
    "/bug",
    response_model=BugReportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_bug_report(
    category: str = Form(...),
    title: str = Form(...),
    app_version: str = Form(...),
    platform: str = Form(...),
    steps: str | None = Form(default=None),
    route: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    authorization: str | None = Header(default=None),
) -> BugReportResponse:
    user_id = _resolve_user_id(authorization)

    attachment_path: str | None = None
    attachment_mime: str | None = None
    if file is not None and file.filename:
        # B-tier audit (AT:R37): stream chunks to disk so the full body is
        # never resident in memory. The running counter inside
        # save_attachment_streaming aborts mid-stream on cap overrun, and
        # MIME is validated up-front so unsupported types never touch the
        # disk. We still do the MIME check here too, to return 415 rather
        # than 400 (the streaming function only knows AttachmentRejected).
        mime = (file.content_type or "").lower()
        if not is_allowed_mime(mime):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"attachment MIME not allowed: {mime!r}",
            )
        try:
            attachment_path = await save_attachment_streaming(
                upload=file, mime=mime,
            )
            attachment_mime = mime
        except AttachmentRejected as exc:
            msg = str(exc)
            if "empty" in msg:
                # Treat an empty <input type=file> like no attachment —
                # don't bounce the whole report because the picker
                # returned 0 B.
                attachment_path = None
            elif "exceeds" in msg:
                raise HTTPException(
                    status_code=413, detail=msg,
                ) from exc
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=msg,
                ) from exc
        except OSError:  # pragma: no cover — disk-full / permission
            logger.exception("bug_attachment_write_failed")
            # Don't drop the bug report — the text is more valuable than
            # the photo. Log and continue with attachment_path=None.
            attachment_path = None
            attachment_mime = None

    req = BugReportRequest(
        category=category,  # type: ignore[arg-type]
        title=title,
        steps=steps,
        route=route,
        app_version=app_version,
        platform=platform,
        attachment_path=attachment_path,
        attachment_mime=attachment_mime,
    )
    return get_feedback_store().submit_bug(req, user_id)


def _require_user_id(authorization: str | None) -> UUID:
    """Same parse as _resolve_user_id, but 401s instead of shrugging.

    The submit path deliberately tolerates a missing user_id — a report
    without an author still has value. The read paths cannot: with no
    caller identity there is nothing to scope the query to, and an
    unscoped one would hand a stranger someone else's reports.
    """
    user_id = _resolve_user_id(authorization)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
        )
    return user_id


@router.get("/updates", response_model=list[BugResolutionUpdate])
async def list_resolution_updates(
    authorization: str | None = Header(default=None),
) -> list[BugResolutionUpdate]:
    """Resolved reports the caller filed and hasn't been shown yet.

    Polled once per cold start. Normally returns [].
    """
    user_id = _require_user_id(authorization)
    return get_feedback_store().list_unacknowledged(user_id)


@router.post("/{report_id}/ack", status_code=status.HTTP_204_NO_CONTENT)
async def acknowledge_resolution(
    report_id: UUID,
    authorization: str | None = Header(default=None),
) -> None:
    """Mark a resolution message as delivered, so it fires exactly once.

    404s on a report that isn't the caller's — same response as one that
    doesn't exist, so this can't be used to probe for other users' ids.
    """
    user_id = _require_user_id(authorization)
    if not get_feedback_store().acknowledge(user_id, report_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
