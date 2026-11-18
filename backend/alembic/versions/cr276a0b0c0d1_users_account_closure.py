"""cr276_users_account_closure — closure request, erasure stamp and mode on users

Revision ID: cr276a0b0c0d1
Revises: cr273a0b0c0d1
Create Date: 2026-11-18

AT:B1 CR276 (CR267 WP-30) — in-app account deletion. `closure_requested_at`
starts the grace window; `erased_at` + `erased_mode` record that the post-grace
step ran (only ever visible on `anonymise` tombstones and `archive` rows,
because `delete` removes the row).

All three NULLable, no server_default, NO backfill: NULL means "not closed"
for every existing row. Fully reversible.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "cr276a0b0c0d1"
down_revision: Union[str, Sequence[str], None] = "cr273a0b0c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("closure_requested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("erased_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("users", sa.Column("erased_mode", sa.String(), nullable=True))
    op.create_index(
        "ix_users_closure_requested_at", "users", ["closure_requested_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_users_closure_requested_at", table_name="users")
    op.drop_column("users", "erased_mode")
    op.drop_column("users", "erased_at")
    op.drop_column("users", "closure_requested_at")
