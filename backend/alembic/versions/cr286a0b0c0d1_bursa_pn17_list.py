"""cr286_bursa_pn17_list - Bursa PN17/GN3 list: current rows, change log, refresh runs

Revision ID: cr286a0b0c0d1
Revises: cr282a0b0c0d1
Create Date: 2026-11-26

AT:B1 CR286. Three new tables, no existing table touched:

- `bursa_pn17_current`  the list as of the last successful read (unique on stock_code,
  NOT NULL so the key is real on Postgres and SQLite, ISS001).
- `bursa_pn17_changes`  append-only history (added / category_changed / removed).
- `bursa_pn17_runs`     one row per refresh attempt (ok / refused / parse_failed /
  fetch_failed; weekly / manual), the source of the 14-day stale rule.

Idempotent: each table is created only when absent. Downgrade drops all three.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "cr286a0b0c0d1"
down_revision: Union[str, Sequence[str], None] = "cr282a0b0c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables(conn) -> set[str]:
    return set(sa.inspect(conn).get_table_names())


def upgrade() -> None:
    have = _tables(op.get_bind())
    if "bursa_pn17_current" not in have:
        op.create_table(
            "bursa_pn17_current",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("stock_code", sa.String(), nullable=False),
            sa.Column("company_name", sa.String(), nullable=False),
            sa.Column("market", sa.String(), nullable=False),
            sa.Column("status_category", sa.String(), nullable=False),
            sa.Column("status_group", sa.String(), nullable=True),
            sa.Column("first_seen", sa.Date(), nullable=False),
            sa.Column("last_seen", sa.Date(), nullable=False),
            sa.Column("source_url", sa.String(), nullable=False),
            sa.UniqueConstraint("stock_code", name="uq_bursa_pn17_current_code"),
        )
    if "bursa_pn17_changes" not in have:
        op.create_table(
            "bursa_pn17_changes",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("run_id", sa.Uuid(), nullable=False),
            sa.Column("change_type", sa.String(), nullable=False),
            sa.Column("stock_code", sa.String(), nullable=False),
            sa.Column("company_name", sa.String(), nullable=False),
            sa.Column("market", sa.String(), nullable=False),
            sa.Column("status_category", sa.String(), nullable=False),
            sa.Column("status_group", sa.String(), nullable=True),
            sa.Column("previous_category", sa.String(), nullable=True),
            sa.Column("observed_on", sa.Date(), nullable=False),
            sa.Column("source_url", sa.String(), nullable=False),
        )
        op.create_index("ix_bursa_pn17_changes_run_id", "bursa_pn17_changes", ["run_id"])
        op.create_index("ix_bursa_pn17_changes_stock_code", "bursa_pn17_changes", ["stock_code"])
    if "bursa_pn17_runs" not in have:
        op.create_table(
            "bursa_pn17_runs",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("trigger", sa.String(), nullable=False),
            sa.Column("outcome", sa.String(), nullable=False),
            sa.Column("http_status", sa.Integer(), nullable=True),
            sa.Column("rows_found", sa.Integer(), nullable=False),
            sa.Column("added", sa.Integer(), nullable=False),
            sa.Column("changed", sa.Integer(), nullable=False),
            sa.Column("removed", sa.Integer(), nullable=False),
            sa.Column("detail", sa.String(), nullable=True),
            sa.Column("source_url", sa.String(), nullable=False),
        )
        op.create_index("ix_bursa_pn17_runs_started_at", "bursa_pn17_runs", ["started_at"])


def downgrade() -> None:
    have = _tables(op.get_bind())
    for name in ("bursa_pn17_runs", "bursa_pn17_changes", "bursa_pn17_current"):
        if name in have:
            op.drop_table(name)
