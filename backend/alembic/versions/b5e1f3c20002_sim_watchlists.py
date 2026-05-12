"""sim_watchlists table for A18 (user watchlist)

Revision ID: b5e1f3c20002
Revises: a4c7e9d10001
Create Date: 2026-05-12

A18 introduces a per-user watchlist of free-form tickers. Lessons reference
tickers illustratively; this is how the user actually curates the small set
of names they want quotes on and one-tap access to (Ask Market Analyst,
Convene the Room, Add Trade). Unique per (user_id, ticker).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.db.base  # noqa: F401 — exposes Uuid / JsonB to autogen DDL


revision: str = "b5e1f3c20002"
down_revision: Union[str, Sequence[str], None] = "a4c7e9d10001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sim_watchlists",
        sa.Column("id", app.db.base.Uuid(), nullable=False),
        sa.Column("user_id", app.db.base.Uuid(), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "ticker", name="uq_watchlist_user_ticker"),
    )
    op.create_index(
        op.f("ix_sim_watchlists_user_id"), "sim_watchlists", ["user_id"], unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_sim_watchlists_user_id"), table_name="sim_watchlists")
    op.drop_table("sim_watchlists")
