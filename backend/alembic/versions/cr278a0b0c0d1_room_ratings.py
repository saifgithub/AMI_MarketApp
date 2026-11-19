"""cr278_room_ratings - the Beta thumbs on a Room's verdict

Revision ID: cr278a0b0c0d1
Revises: m276a0cr239x276
Create Date: 2026-11-19

AT:B1 CR278 (CR267 WP-36) - after each Room the app asks "Did the verdict and
its reasons make sense?" and stores the answer here, one row per Room (UNIQUE
`room_run_id`), changeable. Additive only: a new table, no existing row is
touched. The FK cascades from `room_runs`, so deleting a Room deletes its
rating; the row carries no user column (the owner is the Room's owner).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "cr278a0b0c0d1"
down_revision: Union[str, Sequence[str], None] = "m276a0cr239x276"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "room_ratings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("room_run_id", sa.Uuid(), nullable=False),
        sa.Column("helpful", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["room_run_id"], ["room_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("room_run_id"),
    )


def downgrade() -> None:
    op.drop_table("room_ratings")
