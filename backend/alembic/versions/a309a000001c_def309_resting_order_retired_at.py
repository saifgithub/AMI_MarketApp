"""DEF309 — `sim_resting_orders.retired_at`, so a closed order can be dated.

The recent-history window in `SimEngine.list_resting_orders` was keyed on
`filled_at or placed_at`. `filled_at` is set on exactly ONE of the four exits
from the book, so cancelled, expired and rejected orders fell through to *when
they were placed* — and a GTD-90 order placed last week and refused at fill this
morning was filtered straight out of the 24h window. The longer an order had
rested, the more certainly its refusal was hidden, which inverts the guarantee
the window exists to give.

The backfill uses the same `COALESCE(filled_at, placed_at)` the old filter did,
because that is the only signal the existing rows carry — it is not a
reconstruction of when they actually retired and does not claim to be. Its job
is to leave no terminal row with a NULL, so the new filter has a value to read
on rows that predate the column.

Revision ID: a309a000001c
Revises: a171a000001b
Create Date: 2026-08-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a309a000001c"
down_revision = "a171a000001b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sim_resting_orders",
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_sim_resting_orders_retired_at", "sim_resting_orders", ["retired_at"],
    )
    op.execute(
        """
        UPDATE sim_resting_orders
           SET retired_at = COALESCE(filled_at, placed_at)
         WHERE state IN ('filled', 'cancelled', 'expired', 'rejected')
           AND retired_at IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_sim_resting_orders_retired_at", table_name="sim_resting_orders")
    op.drop_column("sim_resting_orders", "retired_at")
