"""CR136 M08 audit r1 m2 — index journal_entries.reference_id

Revision ID: e4f5a6b70030
Revises: d3e4f5a60029
Create Date: 2026-08-06

`reference_id` was declared `mapped_column(Uuid(), nullable=True)` with no
`index=True`, and no migration added one — correctly disclosed by M08 §5.3 and
confirmed by its auditor. Both of CR136's journal reads filter on it, so every
Health-card open and every Finding write scans.

Non-gating at alpha volume, which is exactly why it is worth doing now: the
table has 1203 rows today and the cost of the index is invisible, whereas the
cost of adding it later is a migration against a table the app is reading. The
column is nullable and the index is non-unique, so this is additive — no
constraint, nothing to reconcile, no backfill.

Named explicitly (`ix_journal_entries_reference_id`) rather than left to
SQLAlchemy's convention, so `downgrade` can drop it by the same name on both
dialects.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "e4f5a6b70030"
down_revision: Union[str, Sequence[str], None] = "d3e4f5a60029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_journal_entries_reference_id", "journal_entries", ["reference_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_journal_entries_reference_id", table_name="journal_entries")
