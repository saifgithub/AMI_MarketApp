"""Feedback routes — in-app bug reporting.

POST /v1/feedback/bug  — submit a bug report (anonymous sessions accepted)

Auth: standard Bearer token. The user_id is extracted from the token when
present; missing or unrecognised tokens fall back to user_id=None so the
report is still accepted (we'd rather lose the user_id than lose the report).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Header, status

from app.schemas.feedback import BugReportRequest, BugReportResponse
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


@router.post("/bug", response_model=BugReportResponse, status_code=status.HTTP_201_CREATED)
async def submit_bug_report(
    req: BugReportRequest,
    authorization: str | None = Header(default=None),
) -> BugReportResponse:
    user_id = _resolve_user_id(authorization)
    return get_feedback_store().submit_bug(req, user_id)
