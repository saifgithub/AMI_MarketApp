"""CR164 — as-of snapshot store: OHLCV on price_history_daily, edgar_facts,
news_archive (reserved), backtest_run_index, backtest_universe_membership.

Revision ID: c164a0f00001
Revises: 854f3179acdd
Create Date: 2026-08-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

import app.db.base

revision = "c164a0f00001"
down_revision = "854f3179acdd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("price_history_daily", sa.Column("open", sa.Numeric(12, 4), nullable=True))
    op.add_column("price_history_daily", sa.Column("high", sa.Numeric(12, 4), nullable=True))
    op.add_column("price_history_daily", sa.Column("low", sa.Numeric(12, 4), nullable=True))
    op.add_column("price_history_daily", sa.Column("volume", sa.BigInteger(), nullable=True))

    op.create_table(
        "edgar_facts",
        sa.Column("id", app.db.base.Uuid(), primary_key=True),
        sa.Column("cik", sa.BigInteger(), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("taxonomy", sa.String(), nullable=False),
        sa.Column("tag", sa.String(), nullable=False),
        sa.Column("unit", sa.String(), nullable=False),
        sa.Column("value", sa.Numeric(20, 4), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("fy", sa.Integer(), nullable=True),
        sa.Column("fp", sa.String(), nullable=True),
        sa.Column("form", sa.String(), nullable=True),
        sa.Column("filed", sa.Date(), nullable=False),
        sa.Column("accession_no", sa.String(), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "cik", "taxonomy", "tag", "unit", "period_end", "filed", "accession_no",
            name="uq_edgar_fact_identity",
        ),
    )
    op.create_index(
        "ix_edgar_facts_ticker_tag_filed", "edgar_facts", ["ticker", "tag", "filed"],
    )

    op.create_table(
        "news_archive",
        sa.Column("id", app.db.base.Uuid(), primary_key=True),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("publisher", sa.String(), nullable=True),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("summary", sa.String(), nullable=True),
        sa.Column("sentiment_score", sa.Numeric(6, 4), nullable=True),
        sa.Column("raw", app.db.base.JsonB(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "ticker", "source", "url", "published_at", name="uq_news_archive_item",
        ),
    )
    op.create_index(
        "ix_news_archive_ticker_pub", "news_archive", ["ticker", "published_at"],
    )

    op.create_table(
        "backtest_run_index",
        sa.Column("room_run_id", app.db.base.Uuid(), primary_key=True),
        sa.Column("batch_id", sa.String(), nullable=False),
        sa.Column("arm", sa.String(), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("batch_id", "ticker", "as_of", name="uq_backtest_run"),
    )
    op.create_index("ix_backtest_run_batch", "backtest_run_index", ["batch_id"])

    op.create_table(
        "backtest_universe_membership",
        sa.Column("id", app.db.base.Uuid(), primary_key=True),
        sa.Column("universe_id", sa.String(), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("eligible_from", sa.Date(), nullable=True),
        sa.Column("eligible_to", sa.Date(), nullable=True),
        sa.Column("exclusion_reason", sa.String(), nullable=True),
        sa.Column("noted_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("universe_id", "ticker", name="uq_backtest_universe"),
    )


def downgrade() -> None:
    op.drop_table("backtest_universe_membership")
    op.drop_index("ix_backtest_run_batch", table_name="backtest_run_index")
    op.drop_table("backtest_run_index")
    op.drop_index("ix_news_archive_ticker_pub", table_name="news_archive")
    op.drop_table("news_archive")
    op.drop_index("ix_edgar_facts_ticker_tag_filed", table_name="edgar_facts")
    op.drop_table("edgar_facts")
    op.drop_column("price_history_daily", "volume")
    op.drop_column("price_history_daily", "low")
    op.drop_column("price_history_daily", "high")
    op.drop_column("price_history_daily", "open")
