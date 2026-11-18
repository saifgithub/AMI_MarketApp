"""Merge the CR239 and CR276 migration heads — no schema change.

CR239 (`bug_reports.trace_ids`, WP-38) and CR276 (account closure columns on
`users`, WP-30) were built in parallel worktrees and both chained onto
`cr273a0b0c0d1`, leaving two heads. Editing either migration to re-chain it
would trip the DEF278 immutability guard, so the two branches are joined here
instead, the standard Alembic way (same pattern as `m111a0def416x417`). They
touch disjoint tables (`bug_reports` vs `users`), so their relative order does
not matter.
"""
from __future__ import annotations

from typing import Sequence, Union

revision: str = "m276a0cr239x276"
down_revision: Union[str, Sequence[str], None] = ("cr239a0b0c0d1", "cr276a0b0c0d1")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
