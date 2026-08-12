"""DEF278 — repair `game_fields.starts_decided_at`, which Alembic believes it
already added.

`c109g000007a` was committed adding two columns, and then EDITED in a later
commit of the same slice to add a third (`starts_decided_at`). The reasoning
at the time was that the revision had never been applied anywhere — Alpha's
head was measured at `a109e000005d`, two revisions behind — so extending it
was cleaner than shipping two migrations for one slice.

That reasoning has a hole that only exists on a shared checkout: **"never
applied" is not a property you can verify once and then rely on.** Another
track promoted from `main` in between the two commits. Alpha ran the
two-column version, stamped `c109g000007a`, and is now at head by Alembic's
reckoning while missing a column the file claims to create. No later
`upgrade head` will ever add it, because there is no revision left to run.

Nothing is broken *yet* — the code that reads the column was not in that
promotion either. It is armed rather than firing, which is the worse shape:
the next promotion ships `run_rolling_start_tick`, the tick reads
`starts_decided_at` every five minutes, and the migration step that was
supposed to prevent exactly this reports success.

**Idempotent by inspection, not by `IF NOT EXISTS`.** A database built fresh
runs `c109g000007a` in its current three-column form and already has the
column; Alpha ran the two-column form and does not. Both must survive this
migration, and the check has to work on SQLite (the unit-test fixture) as
well as Postgres, which `ADD COLUMN IF NOT EXISTS` does not.

Revision ID: d109h000008b
Revises: c109g000007a
Create Date: 2026-08-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d109h000008b"
down_revision = "c109g000007a"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    return column in {
        col["name"] for col in sa.inspect(bind).get_columns(table)
    }


def upgrade() -> None:
    if not _has_column("game_fields", "starts_decided_at"):
        op.add_column(
            "game_fields",
            sa.Column("starts_decided_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    # Deliberately a no-op. `c109g000007a`'s own downgrade drops this column on
    # any database that got it from there, and dropping it here as well would
    # fail on exactly the database this migration exists to repair.
    pass
