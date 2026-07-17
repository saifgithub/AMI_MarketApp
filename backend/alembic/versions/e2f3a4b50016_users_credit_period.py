"""users.credits_period_start + credits_plan_at_grant (CR039)

Revision ID: e2f3a4b50016
Revises: d1e2f3a40015
Create Date: 2026-07-17

AT:R60 — CR039. `users.credit_balance` already existed but was write-only
(reputation_service granted; nothing ever spent). Metering Convene the Room
needs to know *which allowance window* the balance belongs to, otherwise a
monthly reset can't be distinguished from a balance the user has earned down.

`credits_plan_at_grant` stores the **effective** plan (post-trial-resolution)
the current balance was granted under. Re-granting when it drifts is what
makes trial expiry visible immediately rather than at the next month rollover
— a 7-day trial almost always lapses mid-month.

Both nullable, no server_default: a NULL period reads as "never granted", so
existing rows re-grant on first touch. No backfill.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e2f3a4b50016"
down_revision: Union[str, Sequence[str], None] = "d1e2f3a40015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("credits_period_start", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("credits_plan_at_grant", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "credits_plan_at_grant")
    op.drop_column("users", "credits_period_start")
