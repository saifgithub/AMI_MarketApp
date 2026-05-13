"""audit tables — llm_audit, http_audit, one_on_one_messages

Revision ID: d8a3e9f40004
Revises: c7f2a1d30003
Create Date: 2026-05-13

AT:R16 — comprehensive alpha-era audit logging. While the cohort is
tiny (≤ a few dozen testers), record every LLM call, every HTTP
request, and every 1-on-1 chat turn so we can answer "what did the
system do for user X at time T" with a single psql query. None of
these are user-facing; they exist for triage and learning.

Retention is unbounded for now. Add a nightly trim job before scaling
testers (TODO comment in app/services/audit.py).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.db.base  # noqa: F401 — exposes Uuid / JsonB to autogen DDL


revision: str = "d8a3e9f40004"
down_revision: Union[str, Sequence[str], None] = "c7f2a1d30003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "llm_audit",
        sa.Column("id", app.db.base.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", app.db.base.Uuid(), nullable=True),
        sa.Column("agent_id", sa.String(), nullable=True),
        sa.Column("flow", sa.String(), nullable=True),
        sa.Column("tier", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("locale", sa.String(), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("messages", app.db.base.JsonB(), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_llm_audit_user_id"), "llm_audit", ["user_id"], unique=False,
    )
    op.create_index(
        op.f("ix_llm_audit_created_at"), "llm_audit", ["created_at"], unique=False,
    )

    op.create_table(
        "http_audit",
        sa.Column("id", app.db.base.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("method", sa.String(), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("query", sa.String(), nullable=True),
        sa.Column("user_id", app.db.base.Uuid(), nullable=True),
        sa.Column("client_ip", sa.String(), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("request_body", sa.Text(), nullable=True),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("response_truncated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_streaming", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_http_audit_created_at"), "http_audit", ["created_at"], unique=False,
    )
    op.create_index(
        op.f("ix_http_audit_path"), "http_audit", ["path"], unique=False,
    )
    op.create_index(
        op.f("ix_http_audit_user_id"), "http_audit", ["user_id"], unique=False,
    )

    op.create_table(
        "one_on_one_messages",
        sa.Column("id", app.db.base.Uuid(), nullable=False),
        sa.Column("session_id", app.db.base.Uuid(), nullable=False),
        sa.Column("user_id", app.db.base.Uuid(), nullable=False),
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_one_on_one_messages_session_id"),
        "one_on_one_messages",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_one_on_one_messages_user_id"),
        "one_on_one_messages",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_one_on_one_messages_user_id"), table_name="one_on_one_messages")
    op.drop_index(op.f("ix_one_on_one_messages_session_id"), table_name="one_on_one_messages")
    op.drop_table("one_on_one_messages")
    op.drop_index(op.f("ix_http_audit_user_id"), table_name="http_audit")
    op.drop_index(op.f("ix_http_audit_path"), table_name="http_audit")
    op.drop_index(op.f("ix_http_audit_created_at"), table_name="http_audit")
    op.drop_table("http_audit")
    op.drop_index(op.f("ix_llm_audit_created_at"), table_name="llm_audit")
    op.drop_index(op.f("ix_llm_audit_user_id"), table_name="llm_audit")
    op.drop_table("llm_audit")
