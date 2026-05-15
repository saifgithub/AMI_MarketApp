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
from app.schemas.feedback import BugReportRequest, BugReportResponse
from app.services.bug_attachments import (
    AttachmentRejected,
    is_allowed_mime,
    save_attachment,
)
from app.services.feedback_store import get_feedback_store

router = APIRouter(prefix="/v1/feedback", tags=["feedback"])


def _resolve_user_id(authorization: str | None) -> UUID | None:
    """Extract user_id from a scaffold token (`scaffold:<hex>`).

    Returns None rather than raising — we accept reports from un-authed
    or partially-authed sessions.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    if token.startswith("scaffold:"):
        hex_part = token.removeprefix("scaffold:")
        try:
            return UUID(hex=hex_part)
        except ValueError:
            pass
    return None


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
        # Read upfront — UploadFile streams from disk, so the cap check
        # below is on the in-memory bytes we already paid for. For 5MB
        # this is fine; if we raise the cap, switch to chunked read +
        # write with a running byte counter.
        content = await file.read()
        if not content:
            # Treat an empty <input type=file> like no attachment — don't
            # bounce the whole report just because the picker returned 0 B.
            attachment_path = None
        else:
            mime = (file.content_type or "").lower()
            if not is_allowed_mime(mime):
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail=f"attachment MIME not allowed: {mime!r}",
                )
            try:
                attachment_path = save_attachment(content=content, mime=mime)
                attachment_mime = mime
            except AttachmentRejected as exc:
                # Distinguish 413 (too big) from 415/400.
                msg = str(exc)
                if "exceeds" in msg:
                    raise HTTPException(
                        status_code=413,
                        detail=msg,
                    ) from exc
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=msg,
                ) from exc
            except OSError as exc:  # pragma: no cover — disk-full / permission
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
