"""classification_universe_snapshots — add per-ticker liquidity maps (DEF417)

Revision ID: def417a0b0c0d1
Revises: cr230a0order0log
Create Date: 2026-09-24

DEF417: the `liquid_only` mandate flag ("Liquid only. Avoid microcaps (< $500M
market cap) and illiquid names.") was rendered into every PM-lineage prompt but
never enforced by the deterministic safety floor. This adds `market_caps` (ticker
-> USD millions) and `avg_volumes` (ticker -> shares/day) JSON maps onto the
DEF061 classification snapshot — populated in the SAME daily
`_classification_universe_refresh()` pass from the `info["marketCap"]` /
`info["averageVolume"]` fields the fossil/sin classifier already reads via the
same `yf.Ticker(t).info` call. No new socket, no new provider, no paid feed. The
request path resolves ticker -> liquidity from this stored map (no yfinance
socket, per CR075/DEF089); a ticker absent from both maps resolves UNKNOWN
(permitted + disclosed — the DEF059 inversion guard), never a false EXCLUDED.

Back-fills existing rows to empty maps (`{}`), so a row written before DEF417
simply carries no liquidity data until the next refresh appends a fresh row.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.db.base import JsonB


revision: str = "def417a0b0c0d1"
down_revision: Union[str, Sequence[str], None] = "cr230a0order0log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "classification_universe_snapshots",
        sa.Column(
            "market_caps", JsonB(), nullable=True, server_default=sa.text("'{}'"),
        ),
    )
    op.add_column(
        "classification_universe_snapshots",
        sa.Column(
            "avg_volumes", JsonB(), nullable=True, server_default=sa.text("'{}'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("classification_universe_snapshots", "avg_volumes")
    op.drop_column("classification_universe_snapshots", "market_caps")
