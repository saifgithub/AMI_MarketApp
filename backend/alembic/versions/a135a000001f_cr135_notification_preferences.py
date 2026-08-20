"""CR135 — notification_preferences: per-(user, type) push opt-out.

Composite PK (user_id, type); user_id is the leading PK column, so the
per-user preferences read needs no separate index and none is created
(DEF337 class: one index creation path only). Absence of a row means
enabled — notify() suppresses the OneSignal attempt for a disabled type
but still writes the durable notifications row.

Revision ID: a135a000001f
Revises: c102a000001e
"""

from alembic import op
import sqlalchemy as sa

revision = "a135a000001f"
down_revision = "c102a000001e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_preferences",
        sa.Column("user_id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("type", sa.String(), primary_key=True, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("notification_preferences")
