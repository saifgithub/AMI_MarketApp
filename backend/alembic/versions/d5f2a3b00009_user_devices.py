"""user_devices table for multi-device tracking (BL2)

Revision ID: d5f2a3b00009
Revises: c4e8f1a90008
Create Date: 2026-05-22

AT:R33 — BL2. Saiful is now testing on iPhone 13 + iPhone 17 with the
same Apple ID; the single users.device_user_id column has no way to
represent "this human has two phones". This migration adds:

  user_devices (
    id              UUID PK,
    user_id         UUID    -- the owning user (re-keyed on claim adoption)
    device_install_id UUID UNIQUE  -- stable per-install identifier (mobile-gen)
    device_model    VARCHAR
    os_version      VARCHAR
    app_version     VARCHAR
    first_seen_at   TIMESTAMPTZ
    last_seen_at    TIMESTAMPTZ
    created_at      TIMESTAMPTZ
  )

Why a separate device_install_id (and not just reuse device_user_id):
on claim adoption (account-linking Phase 1, AT:R32) the mobile overwrites
its local device_user_id with the adopted user's id — so device_user_id
stops being a stable per-install identifier post-claim. device_install_id
is generated once on first launch in shared_prefs and never mutated.

Backfill: each existing users row with device_user_id set gets a single
user_devices row using device_user_id as the install_id approximation
(best we can do — those installs never knew about device_install_id).

users.device_user_id stays in place; it still plays its A2 role (Bearer-
ownership proof for re-bootstrap). Deprecation is a follow-up once nothing
reads it.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d5f2a3b00009"
down_revision: Union[str, Sequence[str], None] = "c4e8f1a90008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_devices",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("device_install_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("device_model", sa.String(), nullable=True),
        sa.Column("os_version", sa.String(), nullable=True),
        sa.Column("app_version", sa.String(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
    )

    # Backfill: copy every existing users.device_user_id into user_devices.
    # gen_random_uuid() lives in pgcrypto on Postgres 13+ (it's already
    # enabled on the alpha host — used by other migrations). On SQLite test
    # fixtures, the table is created via create_all and the backfill skips
    # since the table is empty.
    op.execute("""
        INSERT INTO user_devices (
            id, user_id, device_install_id,
            device_model, os_version, app_version,
            first_seen_at, last_seen_at, created_at
        )
        SELECT
            gen_random_uuid(),
            u.id,
            u.device_user_id,
            u.device_model,
            u.os_version,
            u.last_app_version,
            COALESCE(u.anonymous_session_started_at, u.created_at),
            COALESCE(u.updated_at, u.created_at),
            u.created_at
        FROM users u
        WHERE u.device_user_id IS NOT NULL
        ON CONFLICT (device_install_id) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_table("user_devices")
