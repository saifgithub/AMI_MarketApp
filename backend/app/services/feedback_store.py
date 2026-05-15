"""FeedbackStore — write-only store for in-app bug reports.

Anonymous sessions are accepted; user_id may be None when the account
hasn't claimed yet (rare but possible if the report fires before the
anon bootstrap completes).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select

from app.db import get_session, init_schema
from app.db.models import BugReportRow
from app.schemas.feedback import BugCategory, BugReportRequest, BugReportResponse


class FeedbackStore:
    def __init__(self) -> None:
        init_schema()

    def submit_bug(
        self,
        req: BugReportRequest,
        user_id: UUID | None,
    ) -> BugReportResponse:
        now = datetime.now(timezone.utc)
        row = BugReportRow(
            user_id=user_id,
            category=req.category,
            title=req.title,
            steps=req.steps,
            route=req.route,
            app_version=req.app_version,
            platform=req.platform,
            status="open",
            attachment_path=req.attachment_path,
            attachment_mime=req.attachment_mime,
            created_at=now,
        )
        with get_session() as s:
            s.add(row)
            s.flush()
            return BugReportResponse(
                id=row.id,
                status=row.status,  # type: ignore[arg-type]
                created_at=row.created_at,
                attachment_path=row.attachment_path,
            )

    def clear(self) -> None:
        """Wipe all rows — used by tests."""
        with get_session() as s:
            s.execute(delete(BugReportRow))


_store: FeedbackStore | None = None


def get_feedback_store() -> FeedbackStore:
    global _store
    if _store is None:
        _store = FeedbackStore()
    return _store
