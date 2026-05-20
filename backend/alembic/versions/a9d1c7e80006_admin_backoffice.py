"""Admin back-office: suspended_at, trial columns, subscription_events

Revision ID: a9d1c7e80006
Revises: f7d9b2e60005
Create Date: 2026-05-20

AT:R27 — Admin back-office foundation.

  users table:
    - suspended_at    (nullable timestamp) — single per-user access override;
                       set by admin suspend action; clear to reinstate.
    - trial_started_at (nullable timestamp) — when trial began.
    - trial_expires_at (nullable timestamp) — when trial_trader plan expires.

  subscription_events table — complete audit trail for all plan/credit/trial/
  suspend state changes regardless of source (admin_override | app | revenuecat).
  Every admin write produces a row; RevenueCat webhooks will produce rows in M1.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.db.base  # noqa: F401 — exposes Uuid / JsonB to autogen DDL


revision: str = "a9d1c7e80006"
down_revision: Union[str, Sequence[str], None] = "f7d9b2e60005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users: three new nullable timestamp columns ---
    op.add_column("users", sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("trial_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("trial_expires_at", sa.DateTime(timezone=True), nullable=True))

    # --- subscription_events ---
    op.create_table(
        "subscription_events",
        sa.Column("id", app.db.base.Uuid(), nullable=False),
        sa.Column("user_id", app.db.base.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("from_value", sa.String(), nullable=True),
        sa.Column("to_value", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("admin_id", app.db.base.Uuid(), nullable=True),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sub_events_user_id", "subscription_events", ["user_id"])
    op.create_index("ix_sub_events_created_at", "subscription_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_sub_events_created_at", table_name="subscription_events")
    op.drop_index("ix_sub_events_user_id", table_name="subscription_events")
    op.drop_table("subscription_events")
    op.drop_column("users", "trial_expires_at")
    op.drop_column("users", "trial_started_at")
    op.drop_column("users", "suspended_at")
