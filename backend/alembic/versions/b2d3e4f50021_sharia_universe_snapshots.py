"""sharia_universe_snapshots — persist the sourced Sharia universe (CR075)

Revision ID: b2d3e4f50021
Revises: a1c2e3f40020
Create Date: 2026-07-25

CR075: the CR069 Sharia allowlist lived only in process memory — built on first
use, re-fetched no more often than every 900 s, and a source outage of any length
paused every halal trade (DEF093's blast radius). This table persists the universe
so the daily `_sharia_universe_refresh()` task writes one row per successful fetch
(append-only) and every request resolves from the latest stored row — no network
on the request path, and a transient source outage serves the held list instead of
blocking.

`fetched_at` is OUR UTC stamp; it is the freshness signal the parent-index mirror
never publishes (a frozen mirror keeps a fixed `as_of` while `fetched_at` advances
across snapshots). `as_of` is the compliant file's own date, nullable because the
parent mirror carries none. The (standard, fetched_at) index backs the
"latest row for a standard" read.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.db.base import JsonB


revision: str = "b2d3e4f50021"
down_revision: Union[str, Sequence[str], None] = "a1c2e3f40020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sharia_universe_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("standard", sa.String(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column("parent_source_url", sa.String(), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=True),
        sa.Column(
            "fetched_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("compliant", JsonB(), nullable=False),
        sa.Column("parent", JsonB(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sharia_snapshot_standard_fetched",
        "sharia_universe_snapshots",
        ["standard", "fetched_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_sharia_snapshot_standard_fetched",
        table_name="sharia_universe_snapshots",
    )
    op.drop_table("sharia_universe_snapshots")
