"""journal_entries: add deleted_at for soft-delete

Revision ID: f7d9b2e60005
Revises: d8a3e9f40004
Create Date: 2026-05-14

AT:R19 — entries are never hard-deleted; a DELETE API call sets deleted_at.
All read queries filter deleted_at IS NULL so deleted entries are invisible
to users. The data stays in Postgres so a tier upgrade or admin restore can
recover it later.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f7d9b2e60005"
down_revision: Union[str, None] = "d8a3e9f40004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "journal_entries",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_journal_entries_deleted_at",
        "journal_entries",
        ["deleted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_journal_entries_deleted_at", table_name="journal_entries")
    op.drop_column("journal_entries", "deleted_at")
