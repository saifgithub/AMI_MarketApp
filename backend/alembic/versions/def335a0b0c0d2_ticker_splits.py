"""ticker_splits — recorded stock splits, so a share count can be restated onto
the price store's basis (DEF335)

Revision ID: def335a0b0c0d2
Revises: cr210a0b0c0d1
Create Date: 2026-08-31

DEF335's original prescription was to re-backfill `price_history_daily` with
`auto_adjust=False` so `close` would carry an as-traded quote. Measured
2026-08-31 against yfinance 1.3.0, that is not what the flag does: the OHLC
series is split-adjusted in both modes and `auto_adjust` withholds only the
DIVIDEND adjustment. BKNG's `auto_adjust=False` close across its 2026-04-06
25:1 split moves 167.77 -> 176.19 (ratio 0.95, not 25); NFLX 10:1 gives 1.008
and NOW 5:1 gives 1.020. The migration would have rewritten 119,311 rows,
shifted `close` by the ~0.7% dividend factor, and left the 25x market-cap
error exactly in place while looking like it had worked.

Since the price basis cannot be moved, the share basis moves to meet it, and
that needs the split ratios on disk. Fetching them at fact-sheet time is not
an option: `get_asof_daily_rows` is contractually a pure read so an as-of Room
run is deterministic given the store.

Additive only — no existing row is touched, and nothing reads this table until
`edgar_pit` finds rows in it (an empty table yields a factor of 1.0, i.e.
today's behaviour exactly).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "def335a0b0c0d2"
down_revision: Union[str, Sequence[str], None] = "cr210a0b0c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ticker_splits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("ex_date", sa.Date(), nullable=False),
        sa.Column("ratio", sa.Numeric(18, 8), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column(
            "fetched_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker", "ex_date", name="uq_ticker_splits_ticker_ex_date"),
    )
    op.create_index(
        "ix_ticker_splits_ticker_ex_date", "ticker_splits", ["ticker", "ex_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_ticker_splits_ticker_ex_date", table_name="ticker_splits")
    op.drop_table("ticker_splits")
