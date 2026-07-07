"""reputation_league — reputation events, challenge attempts, weekly leagues

Revision ID: c3d4e5f60014
Revises: b2c3d4e50013
Create Date: 2026-07-07

CR004 Engagement phase (D-060: reputation-based weekly leagues only).
Four new tables + four users columns:

  - reputation_events: append-only point grants; (user_id, event_type,
    ref_id) is the dedup anchor consulted by reputation_service.award().
  - daily_challenge_attempts: server truth for one-attempt-per-challenge
    (UNIQUE user_id+challenge_id) — closes the tab-switch re-attempt exploit.
  - leagues / league_members: weekly cohorts (≤ LEAGUE_COHORT_SIZE) keyed
    by ISO week 'YYYY-Www'; league_members.week is denormalized so
    UNIQUE(user_id, week) holds without a join.
  - users.handle: anonymous leaderboard identity; reputation: lifetime
    points counter; show_display_name: opt-in to reveal real name.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.db.base  # noqa: F401 — exposes Uuid / JsonB to autogen DDL


revision: str = "c3d4e5f60014"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e50013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reputation_events",
        sa.Column("id", app.db.base.Uuid(), nullable=False),
        sa.Column("user_id", app.db.base.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("ref_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_reputation_events_user_id"),
        "reputation_events", ["user_id"], unique=False,
    )
    op.create_index(
        op.f("ix_reputation_events_created_at"),
        "reputation_events", ["created_at"], unique=False,
    )

    op.create_table(
        "daily_challenge_attempts",
        sa.Column("id", app.db.base.Uuid(), nullable=False),
        sa.Column("user_id", app.db.base.Uuid(), nullable=False),
        sa.Column("challenge_id", sa.String(), nullable=False),
        sa.Column("selected_option", sa.Integer(), nullable=False),
        sa.Column("correct", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "challenge_id", name="uq_challenge_attempt_user"),
    )
    op.create_index(
        op.f("ix_daily_challenge_attempts_user_id"),
        "daily_challenge_attempts", ["user_id"], unique=False,
    )

    op.create_table(
        "leagues",
        sa.Column("id", app.db.base.Uuid(), nullable=False),
        sa.Column("week", sa.String(length=8), nullable=False),
        sa.Column("tier", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_leagues_week"), "leagues", ["week"], unique=False)

    op.create_table(
        "league_members",
        sa.Column("id", app.db.base.Uuid(), nullable=False),
        sa.Column("league_id", app.db.base.Uuid(), nullable=False),
        sa.Column("user_id", app.db.base.Uuid(), nullable=False),
        sa.Column("week", sa.String(length=8), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rank_final", sa.Integer(), nullable=True),
        sa.Column("outcome", sa.String(), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "week", name="uq_league_member_user_week"),
    )
    op.create_index(
        op.f("ix_league_members_league_id"),
        "league_members", ["league_id"], unique=False,
    )
    op.create_index(
        op.f("ix_league_members_user_id"),
        "league_members", ["user_id"], unique=False,
    )

    op.add_column("users", sa.Column("handle", sa.String(), nullable=True))
    op.create_index(op.f("ix_users_handle"), "users", ["handle"], unique=True)
    op.add_column(
        "users",
        sa.Column("handle_regenerated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("reputation", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "users",
        sa.Column(
            "show_display_name",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "show_display_name")
    op.drop_column("users", "reputation")
    op.drop_column("users", "handle_regenerated_at")
    op.drop_index(op.f("ix_users_handle"), table_name="users")
    op.drop_column("users", "handle")
    op.drop_index(op.f("ix_league_members_user_id"), table_name="league_members")
    op.drop_index(op.f("ix_league_members_league_id"), table_name="league_members")
    op.drop_table("league_members")
    op.drop_index(op.f("ix_leagues_week"), table_name="leagues")
    op.drop_table("leagues")
    op.drop_index(
        op.f("ix_daily_challenge_attempts_user_id"),
        table_name="daily_challenge_attempts",
    )
    op.drop_table("daily_challenge_attempts")
    op.drop_index(op.f("ix_reputation_events_created_at"), table_name="reputation_events")
    op.drop_index(op.f("ix_reputation_events_user_id"), table_name="reputation_events")
    op.drop_table("reputation_events")
