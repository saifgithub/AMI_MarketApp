"""CR109 Amendment G — `game_short_positions`: shorting in the game lane.

A separate table, deliberately, rather than a negative `sim_holdings.quantity`
— `scripts/def110_backfill.py::expected()`, `compute_lots_fifo` and sector
concentration all assume that column is non-negative and would each fail
silently. See the model docstring for the cash model.

Revision ID: f109d000004f
Revises: d109c000003c
Create Date: 2026-08-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f109d000004f"
down_revision = "d109c000003c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "game_short_positions",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column(
            "portfolio_id",
            sa.Uuid(),
            sa.ForeignKey("sim_portfolios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 4), nullable=False),
        sa.Column("entry_price", sa.Numeric(12, 4), nullable=False),
        sa.Column("cash_posted", sa.Numeric(12, 2), nullable=False),
        sa.Column("fee_paid", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(), nullable=False, server_default="open"),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("close_reason", sa.String(), nullable=True),
        sa.Column("realised_pnl", sa.Numeric(12, 2), nullable=True),
    )
    op.create_index(
        "ix_game_short_positions_user_id", "game_short_positions", ["user_id"],
    )
    op.create_index(
        "ix_game_short_positions_run_id", "game_short_positions", ["run_id"],
    )
    op.create_index(
        "ix_game_short_positions_portfolio_id",
        "game_short_positions",
        ["portfolio_id"],
    )
    op.create_index(
        "ix_game_short_positions_state", "game_short_positions", ["state"],
    )


def downgrade() -> None:
    op.drop_index("ix_game_short_positions_state", table_name="game_short_positions")
    op.drop_index(
        "ix_game_short_positions_portfolio_id", table_name="game_short_positions",
    )
    op.drop_index("ix_game_short_positions_run_id", table_name="game_short_positions")
    op.drop_index("ix_game_short_positions_user_id", table_name="game_short_positions")
    op.drop_table("game_short_positions")
