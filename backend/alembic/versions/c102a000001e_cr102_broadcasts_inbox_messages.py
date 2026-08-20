"""CR102 — broadcasts + inbox_messages for in-app tester messaging.

`broadcasts` is the authored send record (audience spec + measured
recipient_count); `inbox_messages` is the per-user copy, holding both the
send-time fan-out (direction='out') and tester replies (direction='in',
threaded via reply_to_id). Fan-out at send time, never a read-time
predicate — see BroadcastRow / InboxMessageRow in app/db/models.py.

JSON columns are sa.JSON() to match JsonB's create-table behaviour on both
Postgres and sqlite. Rows are permanent — CR102 specifies no retention
policy (~100-user alpha scale).

Revision ID: c102a000001e
Revises: c192f000001d
"""

from alembic import op
import sqlalchemy as sa

revision = "c102a000001e"
down_revision = "c192f000001d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "broadcasts",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("body", sa.String(), nullable=False),
        sa.Column("body_i18n", sa.JSON(), nullable=True),
        sa.Column("priority", sa.String(), nullable=False),
        sa.Column("audience_json", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("recipient_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )
    # index=True is the ONLY index creation for user_id — a second explicit
    # op.create_index with the canonical name is exactly DEF337.
    op.create_table(
        "inbox_messages",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("broadcast_id", sa.Uuid(), nullable=True),
        sa.Column("direction", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("body", sa.String(), nullable=False),
        sa.Column("reply_to_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("toasted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    # drop_table drops the table's indexes with it.
    op.drop_table("inbox_messages")
    op.drop_table("broadcasts")
