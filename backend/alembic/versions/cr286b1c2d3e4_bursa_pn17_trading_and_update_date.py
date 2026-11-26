"""cr286_bursa_pn17_trading_and_update_date - trading status + Bursa's own "Last updated" date

Revision ID: cr286b1c2d3e4
Revises: cr286a0b0c0d1
Create Date: 2026-11-26

AT:B1 CR286 follow-up. Additive nullable columns only, no data touched:

- `bursa_pn17_current.trading_status`          trading | suspended (null = not known).
- `bursa_pn17_changes.trading_status`          the status a `trading_changed` row moved to.
- `bursa_pn17_changes.previous_trading_status` the status it moved from.
- `bursa_pn17_runs.bursa_updated_on`           Bursa's own "Last updated" date for that read
  (null = not known), so the sheet can say how current Bursa's data is, not only when AMI read it.

Idempotent: each column is added only when absent. Downgrade drops them.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "cr286b1c2d3e4"
down_revision: Union[str, Sequence[str], None] = "cr286a0b0c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = (
    ("bursa_pn17_current", "trading_status", sa.String()),
    ("bursa_pn17_changes", "trading_status", sa.String()),
    ("bursa_pn17_changes", "previous_trading_status", sa.String()),
    ("bursa_pn17_runs", "bursa_updated_on", sa.Date()),
)


def _has(conn, table: str, column: str) -> bool:
    insp = sa.inspect(conn)
    return table in insp.get_table_names() and column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    conn = op.get_bind()
    for table, column, kind in _COLUMNS:
        if not _has(conn, table, column):
            op.add_column(table, sa.Column(column, kind, nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    for table, column, _ in reversed(_COLUMNS):
        if _has(conn, table, column):
            with op.batch_alter_table(table) as batch:
                batch.drop_column(column)
