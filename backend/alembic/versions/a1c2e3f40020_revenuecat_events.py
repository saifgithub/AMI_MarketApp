"""revenuecat_events — RC webhook idempotency ledger (CR084)

Revision ID: a1c2e3f40020
Revises: c5d6e7f80019
Create Date: 2026-07-24

CR084 (RevenueCat integration): the webhook at POST /v1/webhooks/revenuecat
must not double-grant credits when RevenueCat retries a delivery. This table's
UNIQUE(event_id) is the DB-level dedup backstop — the webhook INSERTs the RC
event id first, inside the same transaction as the grant, and a duplicate
delivery is rejected by the constraint rather than by a racy SELECT-then-INSERT
(DEF039 lesson). Dedup row + grant commit atomically, so a failed delivery
leaves no trace and RC's retry can still succeed.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1c2e3f40020"
down_revision: Union[str, Sequence[str], None] = "c5d6e7f80019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "revenuecat_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("app_user_id", sa.String(), nullable=True),
        sa.Column("product_id", sa.String(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_revenuecat_event_id"),
    )
    op.create_index(
        "ix_revenuecat_events_received_at",
        "revenuecat_events",
        ["received_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_revenuecat_events_received_at", table_name="revenuecat_events")
    op.drop_table("revenuecat_events")
