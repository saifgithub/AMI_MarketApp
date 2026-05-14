"""bug_reports: add assigned_branch column for /fix-bugs coordination

Revision ID: a8e3c1b50006
Revises: f7d9b2e60005
Create Date: 2026-05-14

AT:R19 — supports the /fix-bugs slash command. When the bug-fix agent
claims a report it sets status='in_progress' AND assigned_branch to the
worktree's branch in a single UPDATE, so parallel sessions can't both
work the same bug. Lifecycle: open → in_progress → pending_review →
resolved (or wont_fix). status remains a plain VARCHAR; no constraint
because we want to extend the vocabulary without migrations.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a8e3c1b50006"
down_revision: Union[str, None] = "f7d9b2e60005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "bug_reports",
        sa.Column("assigned_branch", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("bug_reports", "assigned_branch")
