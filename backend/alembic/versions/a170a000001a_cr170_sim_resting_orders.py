"""CR170 §1 — `sim_resting_orders`, the training path's resting-order book.

A new table rather than a `pending` status on `sim_trades`, and the reason is
not taste: `scripts/def110_backfill.py::expected()` derives what a portfolio's
holdings should be by subtracting `Σ quantity` over `status='open'` SELL rows.
A working resting sell parked in `sim_trades` would start subtracting shares
that never moved, and the phantom-share detector would report false positives
across every user.

The partial index carries `postgresql_where` **and** `sqlite_where`, matching
`career_events`' pair — the unit suite runs on a sqlite tempfile and would
otherwise be testing a different index than production has.

`expires_at` is NOT NULL by design. A nullable "GTC means null" column is one
column meaning two things (P10) and reliably produces the forgotten-null bug.

Revision ID: a170a000001a
Revises: f109j000010d
Create Date: 2026-08-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a170a000001a"
down_revision = "f109j000010d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sim_resting_orders",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "portfolio_id", sa.Uuid(),
            sa.ForeignKey("sim_portfolios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("side", sa.String(), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 4), nullable=False),
        sa.Column("order_type", sa.String(), nullable=False),
        sa.Column("trigger_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("limit_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("stop", sa.Numeric(12, 4), nullable=True),
        sa.Column("target", sa.Numeric(12, 4), nullable=True),
        sa.Column("horizon_days", sa.Integer(), nullable=True),
        sa.Column("verdict_ref", sa.Uuid(), nullable=True),
        sa.Column("tif", sa.String(), nullable=False, server_default="day"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(), nullable=False, server_default="working"),
        sa.Column("placed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fill_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("filled_trade_id", sa.Uuid(), nullable=True),
        sa.Column("cancel_reason", sa.String(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("last_price_source", sa.String(), nullable=True),
    )
    op.create_index(
        "ix_sim_resting_orders_user_id", "sim_resting_orders", ["user_id"],
    )
    op.create_index(
        "ix_sim_resting_orders_ticker", "sim_resting_orders", ["ticker"],
    )
    op.create_index(
        "ix_sim_resting_orders_state", "sim_resting_orders", ["state"],
    )
    op.create_index(
        "ix_sim_resting_order_live",
        "sim_resting_orders",
        ["state", "ticker"],
        postgresql_where=sa.text("state IN ('working','triggered')"),
        sqlite_where=sa.text("state IN ('working','triggered')"),
    )


def downgrade() -> None:
    op.drop_index("ix_sim_resting_order_live", table_name="sim_resting_orders")
    op.drop_index("ix_sim_resting_orders_state", table_name="sim_resting_orders")
    op.drop_index("ix_sim_resting_orders_ticker", table_name="sim_resting_orders")
    op.drop_index("ix_sim_resting_orders_user_id", table_name="sim_resting_orders")
    op.drop_table("sim_resting_orders")
