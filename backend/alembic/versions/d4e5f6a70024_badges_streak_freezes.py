"""badges_streak_freezes — CR091/CR092/CR094 tables

Revision ID: d4e5f6a70024
Revises: d1e2f3a40023
Create Date: 2026-07-27

Two new tables, no changes to existing ones:

  - badges: earned-once streak badges (Week One / Month Strong / Centurion /
    Marathoner), UNIQUE(user_id, badge_key). is_permanent_flair marks the
    365-day Marathoner badge for permanent profile display (CR092).
  - streak_freezes: consumed Floor-Manager streak freezes (CR094),
    UNIQUE(user_id, frozen_date). period_key is the calendar-year bucket the
    2-per-year allowance resets on.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.db.base  # noqa: F401 — exposes Uuid / JsonB to autogen DDL


revision: str = "d4e5f6a70024"
down_revision: Union[str, Sequence[str], None] = "d1e2f3a40023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "badges",
        sa.Column("id", app.db.base.Uuid(), nullable=False),
        sa.Column("user_id", app.db.base.Uuid(), nullable=False),
        sa.Column("badge_key", sa.String(), nullable=False),
        sa.Column("ref_type", sa.String(), nullable=False),
        sa.Column("ref_id", sa.String(), nullable=False),
        sa.Column(
            "is_permanent_flair", sa.Boolean(), nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("earned_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "badge_key", name="uq_badge_user_key"),
    )
    op.create_index(op.f("ix_badges_user_id"), "badges", ["user_id"], unique=False)

    op.create_table(
        "streak_freezes",
        sa.Column("id", app.db.base.Uuid(), nullable=False),
        sa.Column("user_id", app.db.base.Uuid(), nullable=False),
        sa.Column("frozen_date", sa.Date(), nullable=False),
        sa.Column("period_key", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "frozen_date", name="uq_streak_freeze_user_date"),
    )
    op.create_index(
        op.f("ix_streak_freezes_user_id"), "streak_freezes", ["user_id"], unique=False,
    )
    op.create_index(
        op.f("ix_streak_freezes_period_key"), "streak_freezes", ["period_key"], unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_streak_freezes_period_key"), table_name="streak_freezes")
    op.drop_index(op.f("ix_streak_freezes_user_id"), table_name="streak_freezes")
    op.drop_table("streak_freezes")
    op.drop_index(op.f("ix_badges_user_id"), table_name="badges")
    op.drop_table("badges")
