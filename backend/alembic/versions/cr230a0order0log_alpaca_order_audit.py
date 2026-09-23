"""CR230 — alpaca_order_audit: log of every Alpaca paper order attempt.

One row per `AlpacaClient.submitOrder()` outcome, written by the device via
`POST /v1/alpaca/order_log`. A report, not an observation — the backend
never holds the Alpaca credential (CR202), so it cannot independently verify
any row against Alpaca's own order book. Follows `admin_audit`'s pattern:
index created explicitly (not via `index=True` in `create_table`, DEF337
class), excluded from `trim_audit_tables()`'s 90-day sweep by design — Saiful
asked for a log of every Alpaca interaction, so this table does not
auto-delete itself.

Revision ID: cr230a0order0log
Revises: e221i000009c
"""

from alembic import op
import sqlalchemy as sa

revision = "cr230a0order0log"
down_revision = "e221i000009c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alpaca_order_audit",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("side", sa.String(), nullable=False),
        sa.Column("qty", sa.Float(), nullable=False),
        sa.Column("destination", sa.String(), nullable=False),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("detail", sa.String(), nullable=True),
        sa.Column("alpaca_order_id", sa.String(), nullable=True),
        sa.Column("alpaca_status", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )
    op.create_index("ix_alpaca_order_audit_created_at", "alpaca_order_audit", ["created_at"])
    op.create_index("ix_alpaca_order_audit_user_id", "alpaca_order_audit", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_alpaca_order_audit_user_id", table_name="alpaca_order_audit")
    op.drop_index("ix_alpaca_order_audit_created_at", table_name="alpaca_order_audit")
    op.drop_table("alpaca_order_audit")
