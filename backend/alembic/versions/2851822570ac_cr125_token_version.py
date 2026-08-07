"""cr125_token_version

Revision ID: 2851822570ac
Revises: 1d3f04e6d806
Create Date: 2026-08-07

CR125 — mobile secure session. Adds `users.token_version`, a per-user
revocation counter embedded in every scaffold Bearer token issued from now
on. `get_current_user` 401s a token whose embedded version doesn't match
this column; `DELETE /v1/auth/session` bumps it, so sign-out actually
invalidates every outstanding token for that user (previously a no-op).

Backfilled to 1 for every existing row via `server_default` — every token
issued before this migration carries no version at all (old 3-part format,
now rejected outright per CR040 degrade-loudly), so there is nothing to
reconcile; every device simply re-authenticates once on update (accepted,
CR125 is explicitly breaking).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "2851822570ac"
down_revision: Union[str, Sequence[str], None] = "1d3f04e6d806"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "token_version", sa.Integer(), nullable=False, server_default="1",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "token_version")
