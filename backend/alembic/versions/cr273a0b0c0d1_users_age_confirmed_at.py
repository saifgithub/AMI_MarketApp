"""cr273_users_age_confirmed_at — timestamp of the user's "I am 18 or older" confirmation

Revision ID: cr273a0b0c0d1
Revises: cr270a0b0c0d1
Create Date: 2026-11-18

AT:B1 CR273 (CR267 WP-31, D-084) — onboarding now requires one explicit 18+
confirmation. Only the moment it was given is kept; no birth date or age is
stored anywhere.

NULLable, no server_default, NO backfill: NULL means "never confirmed" (every
pre-CR273 row). Existing Alpha users are deliberately not retrofitted.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "cr273a0b0c0d1"
down_revision: Union[str, Sequence[str], None] = "cr270a0b0c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("age_confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "age_confirmed_at")
