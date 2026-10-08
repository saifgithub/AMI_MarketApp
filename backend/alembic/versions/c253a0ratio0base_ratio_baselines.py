"""ratio_baselines: one observed daily ratio value per (ticker, metric, day)

Revision ID: c253a0ratio0base
Revises: cr237a0cio0retry1
Create Date: 2026-10-08

CR253 lane B(a) — rolling historical baselines for the ratios the fact
sheet emits. The put/call overlay and the live-social overlay upsert one
row per ticker/metric/calendar-day on every successful live read;
`app/services/ratio_baselines.py` medians the trailing 90 days so the sheet
can state "vs trailing-90d baseline X" from this ticker's own history.
Nothing backfills: days with no live read leave no row, and the renderers
state the absence.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c253a0ratio0base"
down_revision: Union[str, None] = "cr237a0cio0retry1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ratio_baselines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("metric", sa.String(length=32), nullable=False),
        sa.Column("observed_on", sa.Date(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.UniqueConstraint("ticker", "metric", "observed_on", name="uq_ratio_baselines_day"),
    )
    op.create_index(
        "ix_ratio_baselines_ticker_metric_date",
        "ratio_baselines",
        ["ticker", "metric", "observed_on"],
    )


def downgrade() -> None:
    op.drop_index("ix_ratio_baselines_ticker_metric_date", table_name="ratio_baselines")
    op.drop_table("ratio_baselines")
