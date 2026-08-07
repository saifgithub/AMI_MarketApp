"""cr095_daily_reminder_hour

Revision ID: 4aad7942bba0
Revises: 2a08e21c0dac
Create Date: 2026-08-07

CR095 — daily-challenge reminder (push paid-tier / email free-tier). One new
nullable column: `users.daily_reminder_hour` (0-23 local hour, evaluated
against the already-existing `users.timezone` — no second timezone column).

NULL = reminders off. Nullable with NO server_default and NO backfill: every
pre-CR095 row is correctly NULL (opted out) until the user picks a time —
never silently opt an existing user into a new notification.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "4aad7942bba0"
down_revision: Union[str, Sequence[str], None] = "2a08e21c0dac"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("daily_reminder_hour", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("users", "daily_reminder_hour")
