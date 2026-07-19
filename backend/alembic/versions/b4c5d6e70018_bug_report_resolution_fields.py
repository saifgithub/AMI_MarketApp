"""bug_reports resolution fields — reporter-facing feedback loop (CR043)

Revision ID: b4c5d6e70018
Revises: a3b4c5d60017
Create Date: 2026-07-19

AT:R60 — CR043. Until now `bug_reports` was write-only from the app's side:
a user filed a report and never heard anything again. 35 reports sit
`resolved` and not one of those reporters was ever told.

Three nullable columns close the loop:

  resolved_at      — when the fix was confirmed shipped
  resolution_note  — plain-English copy shown to the reporter verbatim
  acknowledged_at  — when that reporter was actually shown the message

`acknowledged_at` lives here rather than in device-local storage on purpose:
"you already saw this" must survive a reinstall, and the reporter may be
anonymous-first with no durable client identity beyond the device UUID.

THE BACKFILL IS THE POINT. Without it, the first cold start after this
deploys fires a burst of historical "your bug is fixed" toasts at the 29
users who have a resolved report with a user_id — for bugs they filed and
forgot weeks ago. Stamping every pre-existing terminal row as already
acknowledged means only *future* resolutions notify.

Also folds the single `closed` row into `resolved` (the minimal half of
CR002 — the Pydantic BugStatus Literal never contained `closed`, and the
new GET /v1/feedback/updates route would ValidationError on it). That row
has user_id NULL, so the fold notifies nobody.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b4c5d6e70018"
down_revision = "a3b4c5d60017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "bug_reports",
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "bug_reports",
        sa.Column("resolution_note", sa.String(), nullable=True),
    )
    op.add_column(
        "bug_reports",
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.execute(
        "UPDATE bug_reports SET status = 'resolved' WHERE status = 'closed'"
    )

    # Every report already in a terminal state predates the notification
    # feature. Mark it delivered so nobody gets a retroactive burst.
    op.execute(
        """
        UPDATE bug_reports
           SET acknowledged_at = NOW(),
               resolved_at = COALESCE(resolved_at, created_at)
         WHERE status IN ('resolved', 'wont_fix')
        """
    )


def downgrade() -> None:
    op.drop_column("bug_reports", "acknowledged_at")
    op.drop_column("bug_reports", "resolution_note")
    op.drop_column("bug_reports", "resolved_at")
