"""bug_reports table for in-app bug reporting

Revision ID: c7f2a1d30003
Revises: b5e1f3c20002
Create Date: 2026-05-13

Alpha tier: shake gesture or long-press on the version badge triggers a
bottom sheet that POST /v1/feedback/bug to this table. Triage via Supabase
Table Editor at Alpha volumes. user_id is nullable — anonymous sessions may
report before claim.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.db.base  # noqa: F401 — exposes Uuid / JsonB to autogen DDL


revision: str = "c7f2a1d30003"
down_revision: Union[str, Sequence[str], None] = "b5e1f3c20002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bug_reports",
        sa.Column("id", app.db.base.Uuid(), nullable=False),
        sa.Column("user_id", app.db.base.Uuid(), nullable=True),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("steps", sa.String(), nullable=True),
        sa.Column("route", sa.String(), nullable=True),
        sa.Column("app_version", sa.String(), nullable=False),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_bug_reports_user_id"), "bug_reports", ["user_id"], unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_bug_reports_user_id"), table_name="bug_reports")
    op.drop_table("bug_reports")
