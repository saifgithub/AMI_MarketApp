"""CR109 slice 2 — game portfolios (kind/run_id on sim_portfolios), game_fields, game_entries, game_queued_orders, split flag on sim_holdings

Revision ID: ec77766f771d
Revises: a3dc978f96ec
Create Date: 2026-08-09

implementation_plan.md §4.2/§4.3/§4.4/§4.4.1 — schema specified verbatim
there for `game_fields` / `game_entries`, not re-derived here.

`sim_portfolios.user_id` was UNIQUE on its own (exactly one portfolio per
user). This widens it to `kind` ("training" / "game") + a nullable
`run_id`, replacing that unique index with
`UniqueConstraint(user_id, kind, run_id)` — the shape that lets a user hold
one training portfolio plus one row per game run. Existing rows backfill
`kind='training'` (server_default, then the column is set NOT NULL).

`game_queued_orders` and `sim_holdings.split_adjusted_at` are NOT part of
the plan's verbatim §4 schema — they fill two gaps the plan leaves open
(queued-order storage for the market-hours rule; the split flag for G2).
See their model docstrings in `app/db/models.py` for the reasoning.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.db.base  # noqa: F401 — the portable Uuid the ORM model declares


revision: str = "ec77766f771d"
down_revision: Union[str, Sequence[str], None] = "a3dc978f96ec"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── sim_portfolios: kind + run_id, widen the unique constraint ──────
    op.add_column(
        "sim_portfolios",
        sa.Column(
            "kind", sa.String(), nullable=False, server_default="training",
        ),
    )
    op.add_column(
        "sim_portfolios",
        sa.Column("run_id", app.db.base.Uuid(), nullable=True),
    )
    op.drop_index("ix_sim_portfolios_user_id", table_name="sim_portfolios")
    op.create_unique_constraint(
        "uq_portfolio_user_kind_run", "sim_portfolios", ["user_id", "kind", "run_id"],
    )
    op.create_index(
        "ix_sim_portfolios_user_id", "sim_portfolios", ["user_id"], unique=False,
    )
    op.create_index(
        "ix_sim_portfolios_run_id", "sim_portfolios", ["run_id"], unique=False,
    )
    # server_default was only scaffolding for the backfill above; the ORM
    # model applies "training" as a Python-side default going forward, not
    # a DB-side one — drop it so a future accidental bare INSERT doesn't
    # silently default to "training" instead of failing loudly on a
    # missing value the app forgot to set.
    op.alter_column("sim_portfolios", "kind", server_default=None)

    # ── sim_holdings: the G2 split flag ──────────────────────────────────
    op.add_column(
        "sim_holdings",
        sa.Column("split_adjusted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── game_fields ───────────────────────────────────────────────────────
    op.create_table(
        "game_fields",
        sa.Column("id", app.db.base.Uuid(), nullable=False),
        sa.Column("cadence", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("entry_opens_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locks_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("min_entrants", sa.Integer(), nullable=True),
        sa.Column("max_wait_days", sa.Integer(), nullable=True),
        sa.Column("scoring_basis", sa.String(), nullable=True),
        sa.Column("benchmark_ticker", sa.String(), nullable=True),
        sa.Column("entrant_count", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("join_code", sa.String(), nullable=True),
        sa.Column("owner_user_id", app.db.base.Uuid(), nullable=True),
        sa.Column("points_policy", sa.String(), nullable=False),
        sa.Column("theme", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("join_code", name="uq_game_fields_join_code"),
    )
    op.create_index("ix_game_fields_cadence", "game_fields", ["cadence"])

    # ── game_entries ──────────────────────────────────────────────────────
    op.create_table(
        "game_entries",
        sa.Column("id", app.db.base.Uuid(), nullable=False),
        sa.Column("field_id", app.db.base.Uuid(), nullable=False),
        sa.Column("user_id", app.db.base.Uuid(), nullable=False),
        sa.Column("run_id", app.db.base.Uuid(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("final_twr_pct", sa.Numeric(12, 4), nullable=True),
        sa.Column("final_rank", sa.Integer(), nullable=True),
        sa.Column("career_points_delta", sa.Integer(), nullable=True),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("intent", sa.String(), nullable=True),
        sa.Column("wildness_index", sa.Numeric(12, 4), nullable=True),
        sa.Column("fees_paid", sa.Numeric(12, 2), nullable=False),
        sa.Column("trade_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["field_id"], ["game_fields.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("field_id", "user_id", name="uq_entry_field_user"),
    )
    op.create_index("ix_game_entries_field_id", "game_entries", ["field_id"])
    op.create_index("ix_game_entries_user_id", "game_entries", ["user_id"])
    op.create_index("ix_game_entries_run_id", "game_entries", ["run_id"])

    # ── game_queued_orders ────────────────────────────────────────────────
    op.create_table(
        "game_queued_orders",
        sa.Column("id", app.db.base.Uuid(), nullable=False),
        sa.Column("run_id", app.db.base.Uuid(), nullable=False),
        sa.Column("user_id", app.db.base.Uuid(), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("side", sa.String(), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 4), nullable=False),
        sa.Column("order_type", sa.String(), nullable=False),
        sa.Column("limit_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("stop", sa.Numeric(12, 4), nullable=True),
        sa.Column("target", sa.Numeric(12, 4), nullable=True),
        sa.Column("horizon_days", sa.Integer(), nullable=True),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column(
            "queued_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("filled_trade_id", app.db.base.Uuid(), nullable=True),
        sa.Column("cancel_reason", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_game_queued_orders_run_id", "game_queued_orders", ["run_id"])
    op.create_index("ix_game_queued_orders_user_id", "game_queued_orders", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_game_queued_orders_user_id", table_name="game_queued_orders")
    op.drop_index("ix_game_queued_orders_run_id", table_name="game_queued_orders")
    op.drop_table("game_queued_orders")

    op.drop_index("ix_game_entries_run_id", table_name="game_entries")
    op.drop_index("ix_game_entries_user_id", table_name="game_entries")
    op.drop_index("ix_game_entries_field_id", table_name="game_entries")
    op.drop_table("game_entries")

    op.drop_index("ix_game_fields_cadence", table_name="game_fields")
    op.drop_table("game_fields")

    op.drop_column("sim_holdings", "split_adjusted_at")

    op.drop_index("ix_sim_portfolios_run_id", table_name="sim_portfolios")
    op.drop_index("ix_sim_portfolios_user_id", table_name="sim_portfolios")
    op.drop_constraint(
        "uq_portfolio_user_kind_run", "sim_portfolios", type_="unique",
    )
    op.create_index(
        "ix_sim_portfolios_user_id", "sim_portfolios", ["user_id"], unique=True,
    )
    op.drop_column("sim_portfolios", "run_id")
    op.drop_column("sim_portfolios", "kind")
