"""CR136 M07 — journal_entries.dedupe_key + unique (user_id, entry_type, dedupe_key)

Revision ID: c2d3e4f50028
Revises: b1c2d3e40027
Create Date: 2026-08-02

The Finding route is check-then-act: it reads the prior Finding, reads the gate,
then generates and writes. Nothing between those steps stopped a second request
doing the same. Measured on the real store — five concurrent POSTs produced five
Findings against a daily cap of two, five LLM calls billed for one logical
action, and both the trial budget and the daily cap silently bypassed. The
trigger does not need an attacker: a double-tap before the button disables, or a
mobile client retrying a slow response, is enough.

An application-level re-read cannot fix this; there is no point in the sequence
where reading again is safe, because the competing write may land immediately
after. The fix has to be a constraint the database enforces.

`dedupe_key` is `<portfolio_id>:<as_of>` for a Portfolio Health Finding and NULL
for every other entry type. NULLs do not collide in a unique index on either
Postgres or SQLite, so existing entry types are entirely unaffected — no
backfill, and no behaviour change for the eight other journal writers.

Deliberately NOT a partial index on a JSON expression: `payload->>'as_of'` is
spelled differently on Postgres and SQLite, and the tests run on SQLite, so an
expression index would be enforced in production and silently absent under test
— the one arrangement guaranteed to let this defect come back unnoticed.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c2d3e4f50028"
down_revision: Union[str, Sequence[str], None] = "b1c2d3e40027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "journal_entries",
        sa.Column("dedupe_key", sa.String(), nullable=True),
    )
    op.create_unique_constraint(
        "uq_journal_dedupe",
        "journal_entries",
        ["user_id", "entry_type", "dedupe_key"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_journal_dedupe", "journal_entries", type_="unique")
    op.drop_column("journal_entries", "dedupe_key")
