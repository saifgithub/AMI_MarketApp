"""CR171 §3 — `sim_short_positions`, the training lane's short book.

A second table alongside `game_short_positions` rather than a `kind` column on
it: the two lanes post different collateral (the game posts full notional and
is never margin-called; training posts §7's 1.50 initial margin and IS), so one
table would need a branch on every read to know which arithmetic applies.

Emphatically NOT a negative `sim_holdings.quantity` — `def110_backfill`,
`compute_lots_fifo` and sector concentration all assume non-negative and would
each fail silently.

Revision ID: a171a000001b
Revises: a170a000001a
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a171a000001b"
down_revision = "a170a000001a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sim_short_positions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "portfolio_id", sa.Uuid(),
            sa.ForeignKey("sim_portfolios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 4), nullable=False),
        sa.Column("entry_price", sa.Numeric(12, 4), nullable=False),
        sa.Column("cash_posted", sa.Numeric(12, 2), nullable=False),
        sa.Column("collateral_posted", sa.Numeric(12, 2), nullable=False),
        sa.Column("borrow_rate_pct", sa.Numeric(6, 3), nullable=False),
        sa.Column("borrow_rate_source", sa.String(), nullable=False),
        sa.Column("borrow_rate_basis", sa.Numeric(8, 4), nullable=True),
        sa.Column("borrow_rate_as_of", sa.String(), nullable=True),
        sa.Column(
            "borrow_accrued_total", sa.Numeric(12, 2),
            nullable=False, server_default="0",
        ),
        sa.Column("last_borrow_accrual_date", sa.String(), nullable=True),
        sa.Column("stop", sa.Numeric(12, 4), nullable=True),
        sa.Column("target", sa.Numeric(12, 4), nullable=True),
        sa.Column(
            "opened_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("state", sa.String(), nullable=False, server_default="open"),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("close_reason", sa.String(), nullable=True),
        sa.Column("realised_pnl", sa.Numeric(12, 2), nullable=True),
    )
    op.create_index(
        "ix_sim_short_positions_user_id", "sim_short_positions", ["user_id"],
    )
    op.create_index(
        "ix_sim_short_positions_portfolio_id", "sim_short_positions",
        ["portfolio_id"],
    )
    op.create_index(
        "ix_sim_short_positions_state", "sim_short_positions", ["state"],
    )
    # The sweep's only query is "every OPEN short", and on a healthy book that
    # is a small fraction of the table. Partial, for the same reason CR170's
    # book has one: a full-table index on a column that is 'closed' for almost
    # every row is mostly dead weight.
    op.create_index(
        "ix_sim_short_positions_open",
        "sim_short_positions",
        ["portfolio_id", "ticker"],
        unique=False,
        postgresql_where=sa.text("state = 'open'"),
        sqlite_where=sa.text("state = 'open'"),
    )


def downgrade() -> None:
    op.drop_index("ix_sim_short_positions_open", table_name="sim_short_positions")
    op.drop_index("ix_sim_short_positions_state", table_name="sim_short_positions")
    op.drop_index(
        "ix_sim_short_positions_portfolio_id", table_name="sim_short_positions",
    )
    op.drop_index("ix_sim_short_positions_user_id", table_name="sim_short_positions")
    op.drop_table("sim_short_positions")
