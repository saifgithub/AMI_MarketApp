"""CR172 §3 — `sim_option_legs` + `sim_option_trades`, the training lane's
option book. Slice 1: tables only, no lifecycle.

A separate table for the THIRD time (CR170's resting book, CR171's shorts,
now this), for the identical reason: a negative `sim_holdings.quantity`
would break `def110_backfill`'s phantom-share accumulator,
`compute_lots_fifo` and the sector cap. Quantity is SIGNED here — positive
long, negative short — which is safe precisely because nothing outside the
options surface reads these tables.

`sim_option_legs` is per-leg truth (a vertical is two rows sharing
`strategy_id`; an iron condor is four); `sim_option_trades` is the
structure-level record of the user's single yes. `multiplier` is a column,
not the constant 100 — adjusted contracts exist and a hard-coded 100
misprices them silently.

Revision ID: a172a000001e
Revises: b200a000001b
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a172a000001e"
down_revision = "b200a000001b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sim_option_legs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "portfolio_id", sa.Uuid(),
            sa.ForeignKey("sim_portfolios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("occ_symbol", sa.String(), nullable=False),
        sa.Column("underlying", sa.String(), nullable=False),
        sa.Column("right", sa.String(), nullable=False),
        sa.Column("strike", sa.Numeric(12, 4), nullable=False),
        sa.Column("expiry", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 4), nullable=False),
        sa.Column("avg_premium", sa.Numeric(12, 4), nullable=False),
        sa.Column(
            "multiplier", sa.Numeric(8, 2), nullable=False, server_default="100",
        ),
        sa.Column(
            "collateral_posted", sa.Numeric(12, 2),
            nullable=False, server_default="0",
        ),
        sa.Column("strategy_id", sa.Uuid(), nullable=False),
        sa.Column("strategy_name", sa.String(), nullable=False),
        sa.Column(
            "opened_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("state", sa.String(), nullable=False, server_default="open"),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("close_reason", sa.String(), nullable=True),
        sa.Column("realised_pnl", sa.Numeric(12, 2), nullable=True),
        sa.Column("last_mark", sa.Numeric(12, 4), nullable=True),
        sa.Column("last_mark_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_mark_source", sa.String(), nullable=True),
    )
    op.create_index("ix_sim_option_legs_user_id", "sim_option_legs", ["user_id"])
    op.create_index(
        "ix_sim_option_legs_portfolio_id", "sim_option_legs", ["portfolio_id"],
    )
    op.create_index(
        "ix_sim_option_legs_occ_symbol", "sim_option_legs", ["occ_symbol"],
    )
    op.create_index(
        "ix_sim_option_legs_underlying", "sim_option_legs", ["underlying"],
    )
    op.create_index(
        "ix_sim_option_legs_strategy_id", "sim_option_legs", ["strategy_id"],
    )
    op.create_index("ix_sim_option_legs_state", "sim_option_legs", ["state"])
    # The slice-2 sweep's only query is "every OPEN leg" — partial, for the
    # same dead-weight reason CR170's book and CR171's shorts each carry one.
    op.create_index(
        "ix_sim_option_legs_open",
        "sim_option_legs",
        ["portfolio_id", "underlying"],
        unique=False,
        postgresql_where=sa.text("state = 'open'"),
        sqlite_where=sa.text("state = 'open'"),
    )

    op.create_table(
        "sim_option_trades",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "portfolio_id", sa.Uuid(),
            sa.ForeignKey("sim_portfolios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("strategy_id", sa.Uuid(), nullable=False),
        sa.Column("underlying", sa.String(), nullable=False),
        sa.Column("strategy_name", sa.String(), nullable=False),
        sa.Column("net_cost_at_open", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "collateral_posted", sa.Numeric(12, 2),
            nullable=False, server_default="0",
        ),
        sa.Column("verdict_ref", sa.Uuid(), nullable=True),
        sa.Column(
            "opened_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("status", sa.String(), nullable=False, server_default="open"),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("realised_pnl", sa.Numeric(12, 2), nullable=True),
    )
    op.create_index("ix_sim_option_trades_user_id", "sim_option_trades", ["user_id"])
    op.create_index(
        "ix_sim_option_trades_portfolio_id", "sim_option_trades", ["portfolio_id"],
    )
    op.create_index(
        "ix_sim_option_trades_strategy_id", "sim_option_trades",
        ["strategy_id"], unique=True,
    )
    op.create_index(
        "ix_sim_option_trades_underlying", "sim_option_trades", ["underlying"],
    )
    op.create_index("ix_sim_option_trades_status", "sim_option_trades", ["status"])


def downgrade() -> None:
    op.drop_index("ix_sim_option_trades_status", table_name="sim_option_trades")
    op.drop_index("ix_sim_option_trades_underlying", table_name="sim_option_trades")
    op.drop_index("ix_sim_option_trades_strategy_id", table_name="sim_option_trades")
    op.drop_index("ix_sim_option_trades_portfolio_id", table_name="sim_option_trades")
    op.drop_index("ix_sim_option_trades_user_id", table_name="sim_option_trades")
    op.drop_table("sim_option_trades")
    op.drop_index("ix_sim_option_legs_open", table_name="sim_option_legs")
    op.drop_index("ix_sim_option_legs_state", table_name="sim_option_legs")
    op.drop_index("ix_sim_option_legs_strategy_id", table_name="sim_option_legs")
    op.drop_index("ix_sim_option_legs_underlying", table_name="sim_option_legs")
    op.drop_index("ix_sim_option_legs_occ_symbol", table_name="sim_option_legs")
    op.drop_index("ix_sim_option_legs_portfolio_id", table_name="sim_option_legs")
    op.drop_index("ix_sim_option_legs_user_id", table_name="sim_option_legs")
    op.drop_table("sim_option_legs")
