"""cr194_trade_price_provenance — record which provider served each trade price

Revision ID: cr194a0b0c0d1
Revises: def360a0b0c0d1
Create Date: 2026-08-22

AT:R74 CR194 — DEF305's post-mortem could only tell fabricated closes from the
one real stop by an accident of rounding (`round(v, 2)` against Numeric(12,4)
left every mock-walk close ending `.XX00`). That discriminator was never
designed and stops working the day the rounding changes. These two columns
make it a query instead.

Both NULLABLE with no server_default and NO backfill. The 111 existing rows
(34 closed) predate the columns and must stay NULL: backfilling would be
inventing provenance for precisely the rows whose provenance is in question,
including the nine fabricated closes. "We do not know" and "it was a real
quote" are different facts, and only one of them is a measurement.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "cr194a0b0c0d1"
down_revision: Union[str, Sequence[str], None] = "def360a0b0c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sim_trades", sa.Column("price_source", sa.String(), nullable=True))
    op.add_column(
        "sim_trades", sa.Column("close_price_source", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sim_trades", "close_price_source")
    op.drop_column("sim_trades", "price_source")
