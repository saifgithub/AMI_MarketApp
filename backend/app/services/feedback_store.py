"""FeedbackStore — store for in-app bug reports.

User-facing half: write-only submit + the reporter's resolution toasts.
Anonymous sessions are accepted; user_id may be None when the account
hasn't claimed yet (rare but possible if the report fires before the
anon bootstrap completes).

Admin half (CR200): the console's list/claim/resolve/reopen, sharing the
/fix-bugs lifecycle (open → in_progress → pending_review → resolved) with
the same single-statement guarded UPDATEs psql agents use.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, func, select, update

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

    # ── admin triage (CR200) ──────────────────────────────────────────────
    # The console's half of the lifecycle `/fix-bugs` drives over psql.
    # Claim/resolve/reopen use the SAME single-statement guarded UPDATEs, so
    # a console operator and a psql agent can never double-claim.

    def admin_list(
        self, status: str | None = None, limit: int = 50, offset: int = 0,
    ) -> tuple[list[BugReportRow], int, dict[str, int]]:
        """Newest-first page of reports (+ total for the filter, + per-status
        counts across ALL reports so the filter chips stay populated)."""
        with get_session() as s:
            q = select(BugReportRow)
            cq = select(func.count()).select_from(BugReportRow)
            if status:
                q = q.where(BugReportRow.status == status)
                cq = cq.where(BugReportRow.status == status)
            rows = list(
                s.scalars(
                    q.order_by(BugReportRow.created_at.desc())
                    .limit(limit).offset(offset)
                )
            )
            total = s.execute(cq).scalar_one()
            counts = {
                st: n for st, n in s.execute(
                    select(BugReportRow.status, func.count())
                    .group_by(BugReportRow.status)
                )
            }
            return rows, total, counts

    def admin_get(self, report_id: UUID) -> BugReportRow | None:
        with get_session() as s:
            return s.scalars(
                select(BugReportRow).where(BugReportRow.id == report_id)
            ).one_or_none()

    def admin_claim(self, report_id: UUID, branch: str) -> bool:
        """Atomically claim an `open` report. False = lost the race (or not
        open) — identical semantics to the /fix-bugs psql claim: the UPDATE
        that sets status='in_progress' writes the branch in the same
        statement, guarded on status='open'."""
        with get_session() as s:
            result = s.execute(
                update(BugReportRow)
                .where(
                    BugReportRow.id == report_id,
                    BugReportRow.status == "open",
                )
                .values(status="in_progress", assigned_branch=branch)
            )
            return result.rowcount == 1

    def admin_resolve(self, report_id: UUID, note: str) -> bool:
        """Resolve from any non-resolved status. The note is shown to the
        reporter verbatim (CR043 toast), so it is required at the API layer.
        Never touches acknowledged_at."""
        with get_session() as s:
            result = s.execute(
                update(BugReportRow)
                .where(
                    BugReportRow.id == report_id,
                    BugReportRow.status != "resolved",
                )
                .values(
                    status="resolved",
                    resolved_at=datetime.now(timezone.utc),
                    resolution_note=note,
                )
            )
            return result.rowcount == 1

    def admin_reopen(self, report_id: UUID) -> bool:
        """Back to `open`, releasing any claim (mirrors the /fix-bugs
        takeover-release). Clears the resolution fields so a later resolve
        starts clean; acknowledged_at is preserved — an already-shown toast
        stays shown."""
        with get_session() as s:
            result = s.execute(
                update(BugReportRow)
                .where(
                    BugReportRow.id == report_id,
                    BugReportRow.status != "open",
                )
                .values(
                    status="open",
                    assigned_branch=None,
                    resolved_at=None,
                    resolution_note=None,
                )
            )
            return result.rowcount == 1

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
