"""CR136 M07 audit r1 B1 — uq_journal_dedupe becomes PARTIAL on deleted_at IS NULL

Revision ID: d3e4f5a60029
Revises: c2d3e4f50028
Create Date: 2026-08-03

`c2d3e4f50028` added `uq_journal_dedupe` to stop two concurrent POSTs each
writing a Finding. It did that, and it also covered TOMBSTONES, which the
independent audit found and reproduced against the real route:

    POST 1: 200 created=True   id=14f41765…
    soft_delete -> True
    POST 2: 200 created=False  id=14f41765…   <- the DELETED row's id
    store.get(that id) -> None
    journal list_for_user -> 0 rows visible

The user deletes today's Finding, regenerates, and gets back an id pointing into
an empty journal. Worse, `daily_used` counts journal ROWS: the write always
collided, so no row was ever created, so both spend counters froze —

    POST 2..5: 200  daily_used=1 cap=2  trial_used=1  generations=2,3,4,5
    POST 6:    429  <- the RATE LIMITER, not the gate

five generations against a daily cap of two, each a billed LLM call, bounded
only by 5/min for the rest of the UTC day. Reachable by an ordinary user through
the journal's delete-with-undo, no concurrency and no attacker needed. The
design's own §2.3 deliberately counts soft-deleted rows so that deleting a
Finding does not refund the budget; the collision defeated that by guaranteeing
there was no row to count.

The invariant that was wanted all along is "at most one **live** Finding per
user per entry type per day". A tombstone is not live, so the index is made
partial rather than the collision being worked around in application code — the
original migration's own argument, that only a database constraint can serialise
two concurrent writers, still applies and is preserved for live rows.

`WHERE deleted_at IS NULL` is spelled identically on Postgres and SQLite, so this
carries none of the dialect risk that made an expression index on
`payload->>'as_of'` unacceptable in `c2d3e4f50028`: it is enforced in production
AND under test, on the same terms.

Data note: no backfill and nothing to reconcile. A pre-existing duplicate cannot
exist, because the constraint being replaced was strictly tighter than the index
replacing it.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "d3e4f5a60029"
down_revision: Union[str, Sequence[str], None] = "c2d3e4f50028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("journal_entries") as batch:
        batch.drop_constraint("uq_journal_dedupe", type_="unique")
    op.create_index(
        "uq_journal_dedupe",
        "journal_entries",
        ["user_id", "entry_type", "dedupe_key"],
        unique=True,
        sqlite_where="deleted_at IS NULL",
        postgresql_where="deleted_at IS NULL",
    )


def downgrade() -> None:
    # Downgrading re-tightens the rule, so a book that regenerated after a
    # delete now holds two rows the old constraint forbids. Deliberately left to
    # fail loudly rather than deleting a user's journal rows to make room.
    op.drop_index("uq_journal_dedupe", table_name="journal_entries")
    op.create_unique_constraint(
        "uq_journal_dedupe",
        "journal_entries",
        ["user_id", "entry_type", "dedupe_key"],
    )
