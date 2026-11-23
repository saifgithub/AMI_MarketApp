"""cr282_sim_portfolios_market - which market a simulated book belongs to ('US' | 'MY')

Revision ID: cr282a0b0c0d1
Revises: def308a0b0c0d3
Create Date: 2026-11-24

AT:B1 CR282 lane C. Additive: `sim_portfolios.market` VARCHAR NOT NULL DEFAULT 'US'. The
server default backfills every existing row to 'US' in the same statement (every portfolio
today is a US book), so no separate UPDATE is needed. The MYR book is a separate row with
`kind='training_my'`, `market='MY'`, created on a user's first Bursa action; the existing
unique constraints on (user_id, kind, run_id) already keep it to one per user.

Idempotent: skips when the column already exists. Downgrade drops it (batch mode, so SQLite
works) and also deletes nothing else: MY rows are removed only if the operator drops them
first, otherwise they remain as orphan `training_my` kinds that old code never queries.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "cr282a0b0c0d1"
down_revision: Union[str, Sequence[str], None] = "def308a0b0c0d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(conn) -> bool:
    return any(c["name"] == "market" for c in sa.inspect(conn).get_columns("sim_portfolios"))


def upgrade() -> None:
    if _has_column(op.get_bind()):
        return
    op.add_column(
        "sim_portfolios",
        sa.Column("market", sa.String(), nullable=False, server_default="US"),
    )


def downgrade() -> None:
    if not _has_column(op.get_bind()):
        return
    with op.batch_alter_table("sim_portfolios") as batch:
        batch.drop_column("market")
