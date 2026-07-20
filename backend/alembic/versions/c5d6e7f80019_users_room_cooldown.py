"""users.room_cooldown_until (CR047 — The Winzip)

Revision ID: c5d6e7f80019
Revises: b4c5d6e70018
Create Date: 2026-07-20

AT:R63 — CR047 "The Winzip" (GTM funnel Plan 1 under the CR045 umbrella).
Under GTM_FUNNEL=winzip, an exhausted Floor-Pass user is reset +1 Room the
instant the 402 is sent but blocked from the next convene until this timestamp
— a felt cooldown between free Rooms, without ever actually losing the user.

Nullable, no server_default: NULL = no cooldown pending, which is the correct
reading for every existing row and every non-winzip path. No backfill.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c5d6e7f80019"
down_revision: Union[str, Sequence[str], None] = "b4c5d6e70018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("room_cooldown_until", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "room_cooldown_until")
