"""CR109 slice 3b — `game_duels`: head-to-head pairings inside a field.

A duel needs n=2, which is the only competitive format that works at alpha
field sizes (design §11.1). Scoring is carved out of the placement formula
deliberately — see the model docstring.

Revision ID: a109e000005d
Revises: f109d000004f
Create Date: 2026-08-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a109e000005d"
down_revision = "f109d000004f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # `game_entries` carried no timestamp, so there was no order to pair
    # duels in. Non-null with a server default so existing rows backfill in
    # one statement; they all share the migration's instant, which falls back
    # to `id` ordering — honest, rather than a fabricated sequence.
    op.add_column(
        "game_entries",
        sa.Column(
            "entered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_table(
        "game_duels",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("field_id", sa.Uuid(), nullable=False),
        sa.Column("cadence", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False, server_default="auto"),
        sa.Column("user_a_id", sa.Uuid(), nullable=False),
        sa.Column("run_a_id", sa.Uuid(), nullable=False),
        sa.Column("user_b_id", sa.Uuid(), nullable=False),
        sa.Column("run_b_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(), nullable=False, server_default="live"),
        sa.Column("pairing_key", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("winner_user_id", sa.Uuid(), nullable=True),
        sa.Column("twr_a_pct", sa.Numeric(10, 4), nullable=True),
        sa.Column("twr_b_pct", sa.Numeric(10, 4), nullable=True),
        sa.Column("points_delta", sa.Integer(), nullable=False, server_default="0"),
        # Side A is always the human, and a human run may be in at most one
        # duel per field. The DB-level backstop for the pairing sweep: it is
        # already idempotent by query, and this makes a double-pair
        # impossible even if two ticks race.
        sa.UniqueConstraint("field_id", "run_a_id", name="uq_duel_field_run_a"),
    )
    op.create_index("ix_game_duels_field_id", "game_duels", ["field_id"])
    op.create_index("ix_game_duels_state", "game_duels", ["state"])
    op.create_index("ix_game_duels_user_a_id", "game_duels", ["user_a_id"])
    op.create_index("ix_game_duels_user_b_id", "game_duels", ["user_b_id"])
    op.create_index("ix_game_duels_run_a_id", "game_duels", ["run_a_id"])
    op.create_index("ix_game_duels_run_b_id", "game_duels", ["run_b_id"])
    # Side B's uniqueness is scoped to `auto` duels only. On a `first_run`
    # duel side B is the Index Desk, which is deliberately the opponent of
    # EVERY beginner in the field at once — a plain unique index there would
    # silently cap the field at one beginner, which is the opposite of what
    # the first-run duel exists to guarantee.
    op.create_index(
        "uq_duel_field_run_b_auto",
        "game_duels",
        ["field_id", "run_b_id"],
        unique=True,
        sqlite_where=sa.text("kind = 'auto'"),
        postgresql_where=sa.text("kind = 'auto'"),
    )


def downgrade() -> None:
    for ix in (
        "uq_duel_field_run_b_auto",
        "ix_game_duels_run_b_id",
        "ix_game_duels_run_a_id",
        "ix_game_duels_user_b_id",
        "ix_game_duels_user_a_id",
        "ix_game_duels_state",
        "ix_game_duels_field_id",
    ):
        op.drop_index(ix, table_name="game_duels")
    op.drop_table("game_duels")
    op.drop_column("game_entries", "entered_at")
