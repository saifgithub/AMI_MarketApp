"""room_runs.interrupted_at — mark a shutdown-cancelled row for immediate
sweep claim (DEF425 round 2)

Revision ID: def425a0interrupt1
Revises: m111a0def416x417
Create Date: 2026-09-25

DEF425 round 1 (auditor U68, MAJOR-1): the shutdown-cancel fix left an
interrupted row `status=running`, but `_sweep_stuck_runs` only claims
`running` rows with `started_at < now - room_dedup_running_minutes` (30
min). A restart brings the process back in seconds, so the row is too
young for that boot's one-shot sweep, and nothing looks at it again —
the credits stay taken and `_find_active_run` attaches a re-convene of
the same ticker to the dead row for the next 30 minutes.

`process_start` was considered and rejected: correct for today's single
uvicorn worker, but it would let one instance's boot steal a still-live
run from a sibling instance once CR126 (Cloud Run, multi-instance)
lands. Marking the row itself is instance-agnostic.

This column lets the shutdown branch say "this row was interrupted by
MY shutdown, not just old" — the sweep claims a marked row immediately
regardless of age, and keeps the 30-minute age rule for unmarked rows
(a SIGKILL/crash leaves no mark, so age is still the only signal there).

Nullable, no default needed — existing/unmarked rows read NULL, which
means exactly "not known to be shutdown-interrupted", the correct
default for both historical rows and any row a genuine crash leaves
behind.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "def425a0interrupt1"
down_revision: Union[str, Sequence[str], None] = "m111a0def416x417"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "room_runs",
        sa.Column("interrupted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("room_runs", "interrupted_at")
