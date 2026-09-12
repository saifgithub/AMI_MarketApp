"""DEF278 — repair `edgar_8k_items`'s read index, which Alembic believes it
already created correctly.

`cr221a0b0c0d4` was committed creating `ix_edgar_8k_items_ticker_filed`, and
then EDITED 48 minutes later in the CR221 I1 review round (`94fc8619`) to
create `ix_edgar_8k_items_cik_filed` instead. The rename is correct on its
merits — items are read through the scan row's CIK so that GOOG sees GOOGL's
filings, and GOOG and GOOGL share a CIK — but editing the committed revision
to make it is the DEF278 mistake, for the DEF278 reason: on a shared checkout
"this revision has not run anywhere" is not a property you can verify once and
then rely on. Any database that ran the first form is stamped `cr221a0b0c0d4`,
has the ticker index, lacks the CIK index, and no `upgrade head` will ever
change that, because there is no revision left to run.

Unlike DEF278's original subject this is a performance defect rather than a
correctness one: the read in `edgar_8k.py` filters on `(cik, filed)` and
returns the same rows either way, just without an index to serve it. That is
why it is worth repairing rather than baselining — the repair is cheap, and a
silently unindexed read on a table the Room queries per convene is exactly the
kind of thing that is invisible until the table is large.

**Idempotent by inspection, not by `IF NOT EXISTS`.** A database built fresh
runs `cr221a0b0c0d4` in its current form and already has the CIK index and
never had the ticker one; a database that ran the earlier form has the
opposite. Both must survive this migration, and the check has to work on
SQLite (the unit-test fixture) as well as Postgres, which
`DROP INDEX IF EXISTS` does on Postgres but `CREATE INDEX IF NOT EXISTS`
cannot be relied on across both for our Alembic version. Inspecting the index
names is portable and needs no dialect branch.

Revision ID: e221i000009c
Revises: cr222a0b0c0d4
Create Date: 2026-09-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e221i000009c"
down_revision = "cr222a0b0c0d4"
branch_labels = None
depends_on = None

_TABLE = "edgar_8k_items"
_STALE = "ix_edgar_8k_items_ticker_filed"
_WANTED = "ix_edgar_8k_items_cik_filed"


def _index_names(table: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return set()
    return {ix["name"] for ix in inspector.get_indexes(table)}


def upgrade() -> None:
    names = _index_names(_TABLE)
    if not names and _TABLE not in sa.inspect(op.get_bind()).get_table_names():
        return
    if _STALE in names:
        op.drop_index(_STALE, table_name=_TABLE)
    if _WANTED not in names:
        op.create_index(_WANTED, _TABLE, ["cik", "filed"])


def downgrade() -> None:
    # Deliberately a no-op. `cr221a0b0c0d4`'s own downgrade drops the CIK index
    # on any database that got it from there, and re-creating the ticker index
    # here would leave a database this migration repaired with an index its
    # own revision never created.
    pass
