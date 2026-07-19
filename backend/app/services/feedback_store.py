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
from app.schemas.feedback import (
    BugCategory,
    BugReportRequest,
    BugReportResponse,
    BugResolutionUpdate,
)


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

    def list_unacknowledged(self, user_id: UUID) -> list[BugResolutionUpdate]:
        """Resolved reports this user filed and hasn't been told about.

        Deliberately `resolved` only — `pending_review` means the fix is
        committed on a branch, not shipped. Telling a reporter it's fixed
        at that point invites them to retest against a server that still
        has the bug.
        """
        with get_session() as s:
            rows = s.scalars(
                select(BugReportRow)
                .where(
                    BugReportRow.user_id == user_id,
                    BugReportRow.status == "resolved",
                    BugReportRow.acknowledged_at.is_(None),
                )
                .order_by(BugReportRow.resolved_at)
            ).all()
            return [
                BugResolutionUpdate(
                    id=r.id,
                    title=r.title,
                    resolved_at=r.resolved_at,
                    resolution_note=r.resolution_note,
                )
                for r in rows
            ]

    def acknowledge(self, user_id: UUID, report_id: UUID) -> bool:
        """Stamp acknowledged_at. Scoped to the caller's own rows.

        The user_id predicate is the authorization check, not a filter —
        it is what stops user A acking user B's report. Idempotent: a
        second ack finds nothing unacknowledged and returns False.
        """
        with get_session() as s:
            row = s.scalars(
                select(BugReportRow).where(
                    BugReportRow.id == report_id,
                    BugReportRow.user_id == user_id,
                    BugReportRow.acknowledged_at.is_(None),
                )
            ).one_or_none()
            if row is None:
                return False
            row.acknowledged_at = datetime.now(timezone.utc)
            return True

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
