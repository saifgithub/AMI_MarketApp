"""alpaca_auth_mode — track whether Alpaca was linked via OAuth or API key

Revision ID: b2c3d4e50013
Revises: a1b2c3d40012
Create Date: 2026-06-25

AT:R47 — Adds alpaca_auth_mode to support API key auth alongside OAuth.
NULL = unlinked; 'oauth' = linked via OAuth flow; 'apikey' = linked with
API key + secret (paper trading key from app.alpaca.markets dashboard).

When auth_mode = 'apikey', alpaca_access_token holds the key ID and
alpaca_refresh_token holds the key secret.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b2c3d4e50013"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d40012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("alpaca_auth_mode", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "alpaca_auth_mode")
