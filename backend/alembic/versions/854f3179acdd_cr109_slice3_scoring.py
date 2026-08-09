"""CR109 slice 3 — "the close": scoring-pass columns on game_entries, the
career_events ledger.

Revision ID: 854f3179acdd
Revises: ec77766f771d
Create Date: 2026-08-09

implementation_plan.md §4.4/§4.4.2/§4.5 — schema specified there, not
re-derived here. `game_entries` gains the columns the scoring pass writes
once, at close (`void_reason`, the two alpha numbers, the two private
counterfactual mirrors, `stipend_points`); `career_events` is the new
append-only ledger table, with BOTH the (entry_id, reason) dedup constraint
and the partial (user_id, period_key) stipend-once-per-period index the
design calls for (§6.5's fourth stipend guard).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.db.base  # noqa: F401 — the portable Uuid the ORM model declares


revision: str = "854f3179acdd"
down_revision: Union[str, Sequence[str], None] = "ec77766f771d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── game_entries: the scoring pass's own columns ─────────────────────
    op.add_column(
        "game_entries", sa.Column("void_reason", sa.String(), nullable=True),
    )
    op.add_column(
        "game_entries",
        sa.Column("alpha_scored_pct", sa.Numeric(12, 4), nullable=True),
    )
    op.add_column(
        "game_entries",
        sa.Column("alpha_display_pct", sa.Numeric(12, 4), nullable=True),
    )
    op.add_column(
        "game_entries",
        sa.Column("counterfactual_hold_index_pct", sa.Numeric(12, 4), nullable=True),
    )
    op.add_column(
        "game_entries",
        sa.Column(
            "counterfactual_hold_first_picks_pct", sa.Numeric(12, 4), nullable=True,
        ),
    )
    op.add_column(
        "game_entries",
        sa.Column(
            "stipend_points", sa.Integer(), nullable=False, server_default="0",
        ),
    )
    # server_default was only scaffolding for the backfill above — the ORM
    # model applies 0 as a Python-side default going forward, matching
    # `trade_count`'s own precedent on this table.
    op.alter_column("game_entries", "stipend_points", server_default=None)

    # ── career_events ─────────────────────────────────────────────────────
    op.create_table(
        "career_events",
        sa.Column("id", app.db.base.Uuid(), nullable=False),
        sa.Column("user_id", app.db.base.Uuid(), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("delta_uncapped", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("field_id", app.db.base.Uuid(), nullable=False),
        sa.Column("entry_id", app.db.base.Uuid(), nullable=False),
        sa.Column("period_key", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["field_id"], ["game_fields.id"]),
        sa.ForeignKeyConstraint(["entry_id"], ["game_entries.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entry_id", "reason", name="uq_career_event_entry_reason"),
    )
    op.create_index("ix_career_events_user_id", "career_events", ["user_id"])
    op.create_index("ix_career_events_field_id", "career_events", ["field_id"])
    op.create_index("ix_career_events_entry_id", "career_events", ["entry_id"])
    op.create_index(
        "uq_career_event_stipend_period",
        "career_events",
        ["user_id", "period_key"],
        unique=True,
        sqlite_where=sa.text("reason = 'finish_stipend'"),
        postgresql_where=sa.text("reason = 'finish_stipend'"),
    )


def downgrade() -> None:
    op.drop_index("uq_career_event_stipend_period", table_name="career_events")
    op.drop_index("ix_career_events_entry_id", table_name="career_events")
    op.drop_index("ix_career_events_field_id", table_name="career_events")
    op.drop_index("ix_career_events_user_id", table_name="career_events")
    op.drop_table("career_events")

    op.drop_column("game_entries", "stipend_points")
    op.drop_column("game_entries", "counterfactual_hold_first_picks_pct")
    op.drop_column("game_entries", "counterfactual_hold_index_pct")
    op.drop_column("game_entries", "alpha_display_pct")
    op.drop_column("game_entries", "alpha_scored_pct")
    op.drop_column("game_entries", "void_reason")
