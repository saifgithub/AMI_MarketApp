"""Merge the DEF416 and DEF417 migration heads — no schema change.

DEF416 (OIDC unique indexes) and DEF417 (liquidity columns on the
classification snapshot) were built in parallel worktrees and both chained onto
`cr230a0order0log`, leaving two heads. Editing either migration to re-chain it
would trip the DEF278 immutability guard, so the two branches are joined here
instead, the standard Alembic way. They touch disjoint tables (`users` vs the
classification snapshot), so their relative order does not matter.
"""
from __future__ import annotations

from typing import Sequence, Union

revision: str = "m111a0def416x417"
down_revision: Union[str, Sequence[str], None] = ("def416a0oidc0uq", "def417a0b0c0d1")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
