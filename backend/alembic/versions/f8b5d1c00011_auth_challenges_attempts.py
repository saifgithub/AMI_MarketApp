"""auth_challenges.attempts for magic-link brute-force counter (B-tier audit)

Revision ID: f8b5d1c00011
Revises: e7a4c5b00010
Create Date: 2026-05-23

AT:R37 — B-tier audit close. Magic-link verify accepted unlimited wrong
attempts against the same code until expiry. With this column the service
bumps `attempts` on every wrong-code submission against the still-active
challenge, marks the row consumed once attempts >= MAX_MAGIC_LINK_ATTEMPTS,
and the user has to request a fresh code.

Single column, defaulted to 0, NOT NULL. No backfill needed — existing
unconsumed rows pick up the default and start counting from zero.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f8b5d1c00011"
down_revision: Union[str, Sequence[str], None] = "e7a4c5b00010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "auth_challenges",
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("auth_challenges", "attempts")
