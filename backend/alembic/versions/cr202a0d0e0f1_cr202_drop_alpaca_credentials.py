"""cr202_drop_alpaca_credentials — Alpaca credentials move to the device

Revision ID: cr202a0d0e0f1
Revises: a172a000001e
Create Date: 2026-08-20

AT:R74 CR202 — the user's Alpaca key ID and secret now live on their device
(Keychain / Keystore) and never reach this host, so there is nothing left to
store. Drops all four link columns added by a1b2c3d40012 and b2c3d4e50013.

Holding these was the root of DEF044 (cleartext at rest), DEF181 (key leaked
into http_audit), DEF182 (SECRET_KEY reuse + fail-open crypto) and DEF185
(empty key silently disabling that crypto). Removing the secret removes the
class.

**No data is lost.** Measured on live Alpha immediately before this migration
was written (2026-08-20): 296 users, 0 with a non-null alpaca_access_token, 0
in either auth mode. There is no ciphertext anywhere to migrate.

`downgrade()` restores the column *shape* only — as plain String, matching
a1b2c3d40012's original definition. It cannot restore values, because there
were none. Anyone downgrading past this point should read DEF182 before
re-enabling host-side storage.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "cr202a0d0e0f1"
down_revision: Union[str, Sequence[str], None] = "a172a000001e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("users", "alpaca_auth_mode")
    op.drop_column("users", "alpaca_linked_at")
    op.drop_column("users", "alpaca_refresh_token")
    op.drop_column("users", "alpaca_access_token")


def downgrade() -> None:
    op.add_column("users", sa.Column("alpaca_access_token", sa.String(), nullable=True))
    op.add_column("users", sa.Column("alpaca_refresh_token", sa.String(), nullable=True))
    op.add_column(
        "users",
        sa.Column("alpaca_linked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("users", sa.Column("alpaca_auth_mode", sa.String(), nullable=True))
