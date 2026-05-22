"""room_runs.retry_count for startup auto-retry (eeeb866f)

Revision ID: e7a4c5b00010
Revises: d5f2a3b00009
Create Date: 2026-05-22

AT:R34 — eeeb866f close. The startup sweep used to mark every stuck
`running` row as `failed` (forcing the user to manually resubmit). With
this column we can instead auto-retry once: on the next boot the sweep
bumps retry_count, clears transcript + verdict, and re-spawns the
background task with the original run_id. A run that dies twice in a
row gets marked failed (likely a real bug, not a restart).

Single column, defaulted to 0, NOT NULL so the model can read it
without optional-typing. No backfill needed — existing rows pick up
the default.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e7a4c5b00010"
down_revision: Union[str, Sequence[str], None] = "d5f2a3b00009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "room_runs",
        sa.Column(
            "retry_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("room_runs", "retry_count")
