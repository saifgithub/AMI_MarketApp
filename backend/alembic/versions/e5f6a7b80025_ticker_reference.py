"""ticker_reference — one row per known US-listed ticker (CR128)

Revision ID: e5f6a7b80025
Revises: d4e5f6a70024
Create Date: 2026-07-31

CR128: none of the three ticker-entry points (Convene the Room, Start Trade,
Add to Watchlist) validated that a typed ticker actually exists — a garbage
ticker got a fabricated mock price on the trade path, or ran a full 12-agent
Room debate and spent credits/feed quota before anything noticed.

Unlike the Sharia/classification snapshot tables (append-only, one row per
refresh, list-membership use case), this is one row PER SYMBOL: existence
checks and "did you mean X" suggestions need an O(1) point lookup by symbol.
The daily `_ticker_reference_refresh()` background task upserts every symbol
from NASDAQ Trader's listed-securities files; a symbol missing from the
latest refresh gets `is_active = False` rather than being deleted.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e5f6a7b80025"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a70024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ticker_reference",
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("company_name", sa.String(), nullable=False),
        sa.Column("exchange", sa.String(), nullable=False),
        sa.Column("is_etf", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "last_seen_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("symbol"),
    )
    op.create_index(
        "ix_ticker_reference_is_active",
        "ticker_reference",
        ["is_active"],
    )


def downgrade() -> None:
    op.drop_index("ix_ticker_reference_is_active", table_name="ticker_reference")
    op.drop_table("ticker_reference")
