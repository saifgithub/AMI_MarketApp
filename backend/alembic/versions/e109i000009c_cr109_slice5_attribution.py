"""CR109 slice 5 — `game_entries.attribution`, frozen at close.

Per-ticker contribution to the run, `[{"ticker": …, "pct_points": …}]`,
written once by the scoring pass and never again. It is what the Wind-Up
(design §10 — *"a blowup gets a dignified post-mortem with real numbers"*)
and the Record read.

Stored rather than derived because attribution needs MARKS, and the marks
that produced a result are the ones at that close. Deriving it on read would
price a run that ended last Friday at today's prices: the Record's account of
a finished run would drift every day it was reread, and the ceremony's number
would stop matching what the ledger paid on.

Nullable with no backfill. Runs that closed before this slice have no stored
attribution and will report none — an honest gap. Backfilling would mean
inventing the marks, which is the one thing this column exists to avoid.

Revision ID: e109i000009c
Revises: d109h000008b
Create Date: 2026-08-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.db.base import JsonB

revision = "e109i000009c"
down_revision = "d109h000008b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("game_entries", sa.Column("attribution", JsonB(), nullable=True))


def downgrade() -> None:
    op.drop_column("game_entries", "attribution")
