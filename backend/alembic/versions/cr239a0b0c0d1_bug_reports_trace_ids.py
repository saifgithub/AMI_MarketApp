"""cr239_bug_reports_trace_ids — the recent request trace ids a bug report carries

Revision ID: cr239a0b0c0d1
Revises: cr273a0b0c0d1
Create Date: 2026-11-18

AT:B1 CR239 (CR267 WP-38) — the in-app bug report now attaches the app's most
recent request trace ids (the `X-Request-Id` values from its last failed
calls), so a report can be joined to `http_audit` and the structlog lines for
exactly the requests that failed.

Stored as one comma-separated string of UUIDs (<= 5, validated server-side
before the insert). NULLable, no server_default, NO backfill: NULL means "the
report carried none" — every pre-WP-38 row, and any report filed from a
session that had not yet seen an error.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "cr239a0b0c0d1"
down_revision: Union[str, Sequence[str], None] = "cr273a0b0c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "bug_reports",
        sa.Column("trace_ids", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("bug_reports", "trace_ids")
