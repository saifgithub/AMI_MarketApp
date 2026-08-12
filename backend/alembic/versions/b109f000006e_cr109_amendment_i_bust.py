"""CR109 Amendment I — the wipeout: `game_entries.busted_at` + `nav_shortfall`.

Saiful, 2026-08-12: *"keep no leverage, but when the game ends, all positions
must be closed. how do we keep the account from going negative?"*

Amendment G left a short's leg unbounded below and said the run's own clock
was the containment. It is not — a run's NAV feeds the TWR chain, and TWR is
undefined across a sign change, so one negative NAV row makes every link after
it arithmetic about nothing. A forced buy-in at 10% of collateral bounds an
orderly move; these two columns record the case it cannot bound (a gap), where
the run floors at zero and stops.

Both columns, not one: the floored NAV alone would destroy the fact it hides.
`nav_shortfall` is how far past zero the book actually went — what a real
broker would have billed — and the Close states it in words.

Revision ID: b109f000006e
Revises: a109e000005d
Create Date: 2026-08-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b109f000006e"
down_revision = "a109e000005d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "game_entries",
        sa.Column("busted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "game_entries",
        sa.Column("nav_shortfall", sa.Numeric(12, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("game_entries", "nav_shortfall")
    op.drop_column("game_entries", "busted_at")
