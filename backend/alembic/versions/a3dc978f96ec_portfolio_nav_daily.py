"""CR109 slice 1 — create portfolio_nav_daily (one NAV row per user/run/US-market-day; run_id NULL = training; NO FK to sim_portfolios; unique (user_id, run_id, as_of_date))

Revision ID: a3dc978f96ec
Revises: b7c31f9d4e05
Create Date: 2026-08-09

The one table the whole CR109 design rests on. A daily background tick
writes one row per user per US market date; the read path resolves the
whole stored series rather than re-deriving history from `sim_trades`.

FENCE: deliberately NOT foreign-keyed to `sim_portfolios`. `reset_portfolio()`
hard-deletes the portfolio row and every trade, and the replacement gets a
brand-new UUID — a FK here would CASCADE the entire NAV history away on the
player's first restart. Keyed on `user_id` + `run_id` instead, the same
reset-immune shape `reputation_events` already proves.

`run_id` is NULL for the TRAINING portfolio (the only surface this slice
writes); a real run UUID is a slice-2+ concern. `price_source`
(`live` / `mock` / `stale`) and `capital_event` (`open` / `restart` /
`topup`, nullable) are the CR040 + TWR-chain-split columns described on
`PortfolioNavDailyRow`.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.db.base  # noqa: F401 — the portable Uuid the ORM model declares


revision: str = "a3dc978f96ec"
down_revision: Union[str, Sequence[str], None] = "b7c31f9d4e05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "portfolio_nav_daily",
        sa.Column("id", app.db.base.Uuid(), nullable=False),
        sa.Column("user_id", app.db.base.Uuid(), nullable=False),
        sa.Column("run_id", app.db.base.Uuid(), nullable=True),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("nav", sa.Numeric(12, 2), nullable=False),
        sa.Column("cash", sa.Numeric(12, 2), nullable=False),
        sa.Column("price_source", sa.String(), nullable=False),
        sa.Column("capital_event", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "run_id", "as_of_date", name="uq_nav_user_run_date",
        ),
    )
    op.create_index(
        "ix_portfolio_nav_daily_user_id", "portfolio_nav_daily", ["user_id"],
    )
    op.create_index(
        "ix_portfolio_nav_daily_run_id", "portfolio_nav_daily", ["run_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_portfolio_nav_daily_run_id", table_name="portfolio_nav_daily")
    op.drop_index("ix_portfolio_nav_daily_user_id", table_name="portfolio_nav_daily")
    op.drop_table("portfolio_nav_daily")
