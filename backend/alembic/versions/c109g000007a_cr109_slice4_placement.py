"""CR109 slice 4 — the field: `game_entries.title_multiplier` + `scored_entrant_count`.

Placement (§6.2) is the scoring basis the design was built around, and it needs
two facts the schema never recorded.

`title_multiplier` is FIXED AT RUN OPEN — §6.4's own words. Reading it from the
user at close instead would reprice a whole run on an event that happened after
most of it was traded, in both directions: a player crossing a threshold
mid-run gets a retroactive raise, one falling back through it gets a
retroactive cut. Neither is a thing they did.

`scored_entrant_count` is the `n` the rank was divided by — the entries with a
comparable result. It is deliberately NOT `game_fields.entrant_count`, which
counts everyone who entered including VOID runs whose numbers were never
usable. Both are kept because they answer different questions, and deriving
either from the other is wrong in exactly the case that matters: a field with
voids in it.

Revision ID: c109g000007a
Revises: b109f000006e
Create Date: 2026-08-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c109g000007a"
down_revision = "b109f000006e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "game_entries",
        sa.Column("title_multiplier", sa.Numeric(4, 2), nullable=True),
    )
    op.add_column(
        "game_entries",
        sa.Column("scored_entrant_count", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("game_entries", "scored_entrant_count")
    op.drop_column("game_entries", "title_multiplier")
