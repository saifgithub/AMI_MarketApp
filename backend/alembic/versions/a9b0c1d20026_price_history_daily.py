"""price_history_daily — one adjusted daily close per (ticker, trading day) (CR136 M01)

Revision ID: a9b0c1d20026
Revises: 8a4ce4f8abc3
Create Date: 2026-08-02

CR136 Portfolio Health needs 126+ daily returns per holding before a single
Tier-1 metric is publishable. The pre-CR136 market-data layer could not supply
them — `_PERIOD_MAP` served daily bars only via "1m" (22 bars) and "3m" (65),
i.e. 64 returns against a floor of 126 — and the quote path's 60-second cache
is the wrong shape for a 504-bar series regardless: an N-holding evaluation
would be N Yahoo round-trips on every card open.

This table is the read-through store that fixes both. `adj_close` is the
analytic column every metric reads; `close` carries the same value today
(the provider already returns adjusted closes) and exists so a future provider
serving raw closes can diverge honestly. `source` records the leaf provider,
so fabricated mock-walk bars can never be read back as real market data.

Trading days are derived from which rows exist — no trading calendar is
imported anywhere in CR136 — so the (ticker, date) unique constraint is also
the calendar's integrity guarantee.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.db.base  # noqa: F401 — the portable Uuid the ORM model declares


revision: str = "a9b0c1d20026"
down_revision: Union[str, Sequence[str], None] = "8a4ce4f8abc3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "price_history_daily",
        sa.Column("id", app.db.base.Uuid(), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("close", sa.Numeric(12, 4), nullable=False),
        sa.Column("adj_close", sa.Numeric(12, 4), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column(
            "fetched_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker", "date", name="uq_price_history_ticker_date"),
    )
    op.create_index(
        "ix_price_history_ticker_date",
        "price_history_daily",
        ["ticker", "date"],
    )


def downgrade() -> None:
    op.drop_index("ix_price_history_ticker_date", table_name="price_history_daily")
    op.drop_table("price_history_daily")
