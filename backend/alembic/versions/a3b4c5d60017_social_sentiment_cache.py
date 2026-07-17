"""social_sentiment_cache — durable Adanos cache (CR041)

Revision ID: a3b4c5d60017
Revises: e2f3a4b50016
Create Date: 2026-07-17

AT:R59 — CR041. The Adanos sentiment cache was an in-process dict, so every
container recreate re-burned the 250-calls/month free tier from zero. Saiful's
150-ticker benchmark plan (150 calls, 30-day reuse) is only arithmetically
possible if the cache outlives the process; api-alpha mounts no /data volume
and Redis is unused by the app, so Postgres is the durable surface.

`found` distinguishes "Adanos has no coverage for this ticker" from "not yet
fetched" — negatives are cached too, closing a quota leak where an uncovered
ticker cost a live call on every convene.

No expiry column: readers compare fetched_at against SOCIAL_CACHE_TTL_DAYS, so
retuning the TTL re-dates every row without a backfill.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.db.base import JsonB


revision: str = "a3b4c5d60017"
down_revision: Union[str, Sequence[str], None] = "e2f3a4b50016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "social_sentiment_cache",
        sa.Column("ticker", sa.String(), primary_key=True),
        sa.Column("found", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("payload", JsonB(), nullable=True),
        sa.Column(
            "fetched_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_social_sentiment_cache_fetched_at", "social_sentiment_cache", ["fetched_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_social_sentiment_cache_fetched_at", table_name="social_sentiment_cache")
    op.drop_table("social_sentiment_cache")
