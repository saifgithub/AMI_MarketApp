"""cr267_room_input_bank - same inputs return the same Room

Revision ID: cr267a24bank01
Revises: def499a0b0c0d2
Create Date: 2026-11-20

AT:B1 CR267 (WP-24). Additive only. `room_fact_sheets` freezes a ticker's fact
sheet for one trading day (UNIQUE ticker/day/variant). `room_runs.bank_key` is
the Room's input key, UNIQUE where non-NULL, and `bank_inputs` the components it
was hashed from. Existing rows keep both NULL, i.e. none of them is banked:
a Room that predates the key is never handed to a new convene.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "cr267a24bank01"
down_revision: Union[str, Sequence[str], None] = "def499a0b0c0d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "room_fact_sheets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("trading_date", sa.Date(), nullable=False),
        sa.Column("variant", sa.String(), nullable=False),
        sa.Column("sheet", postgresql.JSONB(), nullable=False),
        sa.Column("sheet_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ticker", "trading_date", "variant", name="uq_room_fact_sheet_day",
        ),
    )
    op.add_column("room_runs", sa.Column("bank_key", sa.String(), nullable=True))
    op.add_column("room_runs", sa.Column("bank_inputs", postgresql.JSONB(), nullable=True))
    op.create_index("uq_room_runs_bank_key", "room_runs", ["bank_key"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_room_runs_bank_key", table_name="room_runs")
    op.drop_column("room_runs", "bank_inputs")
    op.drop_column("room_runs", "bank_key")
    op.drop_table("room_fact_sheets")
