"""CR181 — persona_events: raw client telemetry behind the four persona
segments (bounce / convene / depth / locale).

`uq_persona_events_user_event` is the idempotency contract: a replayed
ingest batch conflicts per (user_id, event_id) and inserts nothing.
Indexes are created here explicitly and NOT via `index=True` inside
`create_table` (DEF337 class: one index creation path only).
`(user_id, occurred_at)` serves the per-user derivation read;
`occurred_at` alone serves the all-users window scan the segment-counts
query does. Retention (400 days, decided at file time per the CR doc) is
enforced at ingest in services/persona_telemetry.py, not by the schema.

Revision ID: a181a000002a
Revises: a135a000001f
"""

from alembic import op
import sqlalchemy as sa

revision = "a181a000002a"
down_revision = "a135a000001f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "persona_events",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "received_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column("locale", sa.String(16), nullable=True),
        sa.Column(
            "count", sa.Integer(), nullable=False, server_default=sa.text("1"),
        ),
        sa.UniqueConstraint(
            "user_id", "event_id", name="uq_persona_events_user_event",
        ),
    )
    op.create_index(
        "ix_persona_events_user_occurred", "persona_events",
        ["user_id", "occurred_at"],
    )
    op.create_index(
        "ix_persona_events_occurred_at", "persona_events", ["occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_persona_events_occurred_at", table_name="persona_events")
    op.drop_index("ix_persona_events_user_occurred", table_name="persona_events")
    op.drop_table("persona_events")
