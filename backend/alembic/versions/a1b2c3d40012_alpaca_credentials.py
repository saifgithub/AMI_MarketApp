"""alpaca_credentials — link Alpaca paper trading account to user

Revision ID: a1b2c3d40012
Revises: f8b5d1c00011
Create Date: 2026-06-02

AT:R45 — Alpaca paper trading integration. Stores the OAuth tokens returned
by Alpaca after the user grants access. Tokens are stored plain (same
policy as other tokens in this schema). `alpaca_linked_at` records when
the link was established so the status endpoint can surface it without
exposing the token itself.

Tokens are nullable — NULL means unlinked.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a1b2c3d40012"
down_revision: Union[str, Sequence[str], None] = "f8b5d1c00011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("alpaca_access_token", sa.String(), nullable=True))
    op.add_column("users", sa.Column("alpaca_refresh_token", sa.String(), nullable=True))
    op.add_column(
        "users",
        sa.Column("alpaca_linked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "alpaca_linked_at")
    op.drop_column("users", "alpaca_refresh_token")
    op.drop_column("users", "alpaca_access_token")
