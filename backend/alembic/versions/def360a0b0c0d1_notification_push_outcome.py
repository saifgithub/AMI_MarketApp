"""def360_notification_push_outcome — store what happened to the push

Revision ID: def360a0b0c0d1
Revises: cr203a0b0c0d1
Create Date: 2026-08-22

AT:R74 DEF360 — the outcome of a push attempt existed only as a log line, and
container logs do not survive `docker compose up --build`, which is every
promotion.

The cost was measured on 2026-08-22. CR176 had been open for days on "never
proven to send a real push", and the host had in fact written 17 beat
notifications between 2026-08-14 and that morning — three of them hours
earlier. Every notifications row was intact; every record of whether those
pushes were delivered had been destroyed by a routine deploy. The evidence for
the open question was being deleted on a schedule, by us.

Both columns are NULLABLE with no default, deliberately. The 17 existing rows
genuinely have no answer, and backfilling them with anything — 'unknown',
'sent', '' — would manufacture a fact about a delivery nobody observed, which
is the DEF059 shape this codebase keeps paying for. NULL means "written before
we recorded this", and it should stay readable as exactly that.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "def360a0b0c0d1"
down_revision: Union[str, Sequence[str], None] = "cr203a0b0c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("push_status", sa.String(), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column("push_detail", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("notifications", "push_detail")
    op.drop_column("notifications", "push_status")
