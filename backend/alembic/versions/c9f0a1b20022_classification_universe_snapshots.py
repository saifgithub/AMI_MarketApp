"""classification_universe_snapshots — persist the sourced sector/industry
classification (DEF061)

Revision ID: c9f0a1b20022
Revises: b2d3e4f50021
Create Date: 2026-07-25

DEF061: the `no_fossil_fuels`, `no_tobacco_alcohol_gambling` and `esg_lite` mandate
flags were advertised in Settings as hard per-trade filters but never enforced by the
deterministic safety floor — they only became LLM prompt narration. This table gives
them the same sourced-universe backing CR075 gave the halal flag: the daily
`_classification_universe_refresh()` task classifies the ~503 S&P parent constituents
(reused from `sharia_universe_snapshots.parent`) by their yfinance sector/industry
and writes one row per successful run (append-only). Three derived buckets are stored
— fossil, sin, defense — and the curated `esg_lite` set is fossil ∪ sin ∪ defense,
derived at read time (a best-effort proxy, NOT a rated ESG score). Every request resolves from the
latest stored row — the ~500 yfinance calls never touch the request path — and a
classify outage serves the held sets instead of un-enforcing the filters.

`fetched_at` is OUR UTC stamp (the freshness signal); `as_of` mirrors it (yfinance
carries no source date). The `fetched_at` index backs the "latest row" read.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.db.base import JsonB


revision: str = "c9f0a1b20022"
down_revision: Union[str, Sequence[str], None] = "b2d3e4f50021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "classification_universe_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=True),
        sa.Column(
            "fetched_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("classified", JsonB(), nullable=False),
        sa.Column("fossil", JsonB(), nullable=False),
        sa.Column("sin", JsonB(), nullable=False),
        sa.Column("defense", JsonB(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_classification_snapshot_fetched",
        "classification_universe_snapshots",
        ["fetched_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_classification_snapshot_fetched",
        table_name="classification_universe_snapshots",
    )
    op.drop_table("classification_universe_snapshots")
