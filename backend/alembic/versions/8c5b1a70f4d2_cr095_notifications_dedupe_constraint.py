"""CR095 audit fix — make notification dedupe a DB guarantee, not a topology assumption.

Adds `uq_notifications_dedupe` on `(user_id, type, source_ref)`.

Until this existed, the only thing preventing a duplicate daily reminder under
concurrent execution was that exactly one process happens to run the sweep
today. `_already_reminded_today` is a plain SELECT and `notify()` a plain
INSERT, so two overlapping ticks both observe "not yet reminded" and both send.
An auditor reproduced it with two real threads.

SQL treats NULLs as distinct in a unique constraint, so the majority of
`notify()` callers — the ones that pass no `source_ref` — are unaffected by
design. Passing a `source_ref` is what opts a caller into dedupe.

The existing-duplicate sweep below runs first, because the constraint cannot be
created over data that already violates it, and Alpha has been running the
CR095 sweep. It keeps the earliest row of each group (by `created_at`, then by
`id` to break exact ties deterministically) — the one that actually caused the
delivery — and drops the rest.

Revision ID: 8c5b1a70f4d2
Revises: 2851822570ac
Create Date: 2026-08-07
"""

from __future__ import annotations

from alembic import op

revision = "8c5b1a70f4d2"
down_revision = "2851822570ac"
branch_labels = None
depends_on = None


_DEDUPE_SQL = """
DELETE FROM notifications AS a
WHERE a.source_ref IS NOT NULL
  AND EXISTS (
      SELECT 1 FROM notifications AS b
      WHERE b.user_id = a.user_id
        AND b.type = a.type
        AND b.source_ref = a.source_ref
        AND (b.created_at < a.created_at
             OR (b.created_at = a.created_at AND b.id < a.id))
  )
"""


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Aliased DELETE is Postgres syntax and Postgres is the only dialect
        # that ever reaches this migration: a fresh SQLite DB is built by
        # `Base.metadata.create_all()` and stamped to head (see
        # `init_schema`'s docstring), so it gets the constraint from the model
        # and never replays the chain.
        op.execute(_DEDUPE_SQL)

    with op.batch_alter_table("notifications") as batch:
        batch.create_unique_constraint(
            "uq_notifications_dedupe", ["user_id", "type", "source_ref"],
        )


def downgrade() -> None:
    with op.batch_alter_table("notifications") as batch:
        batch.drop_constraint("uq_notifications_dedupe", type_="unique")
