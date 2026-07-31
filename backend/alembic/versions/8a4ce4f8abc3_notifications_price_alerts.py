"""notifications + price_alerts — CR027 notification infrastructure + price alerts

Revision ID: 8a4ce4f8abc3
Revises: e5f6a7b80025
Create Date: 2026-07-31

CR027: a generic `notifications` table (one row per notification regardless
of delivery channel/outcome, written unconditionally by
notification_service.notify() before any OneSignal push attempt) plus
`price_alerts` (stop/target/manual price-threshold watches), its first
consumer. See docs/forward_planning/CR027_price_alerts/CR027_price_alerts.md.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "8a4ce4f8abc3"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b80025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("body", sa.String(), nullable=False),
        sa.Column("deep_link", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("source_ref", sa.String(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_notifications_user_created", "notifications", ["user_id", "created_at"],
    )
    op.create_index(
        "ix_notifications_user_read", "notifications", ["user_id", "read_at"],
    )

    op.create_table(
        "price_alerts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("threshold_type", sa.String(), nullable=False),
        sa.Column("threshold_price", sa.Numeric(12, 4), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("trade_ref", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column("fired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("agent_commentary", sa.String(280), nullable=True),
    )
    op.create_index(
        "ix_price_alerts_user_status", "price_alerts", ["user_id", "status"],
    )
    op.create_index(
        "ix_price_alerts_ticker_status", "price_alerts", ["ticker", "status"],
    )
    op.create_index("ix_price_alerts_fired_at", "price_alerts", ["fired_at"])


def downgrade() -> None:
    op.drop_index("ix_price_alerts_fired_at", table_name="price_alerts")
    op.drop_index("ix_price_alerts_ticker_status", table_name="price_alerts")
    op.drop_index("ix_price_alerts_user_status", table_name="price_alerts")
    op.drop_table("price_alerts")
    op.drop_index("ix_notifications_user_read", table_name="notifications")
    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_table("notifications")
