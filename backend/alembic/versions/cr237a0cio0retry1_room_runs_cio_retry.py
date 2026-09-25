"""room_runs.refund_recorded + room_runs.cio_context_snapshot +
room_runs.cio_retried (CR237 — "Ask the CIO again" after a CIO outage)

Revision ID: cr237a0cio0retry1
Revises: def425a0interrupt1
Create Date: 2026-09-25

`refund_recorded`: set True exactly once, at the instant a refund (DEF432
outage or CR039 failed-run) actually fires for this run, and never cleared
afterward. `run_was_refunded` reads this FIRST so a later successful CIO
retry — which replaces the outage PASS with a real verdict on the SAME run —
cannot flip the answer to False for a run that genuinely was refunded (the
DEF437-class "This Room used N credits" fabrication CR237 explicitly guards
against). Non-nullable with a `false` server default so every existing row
reads False, which is correct: nothing before this column shipped could be
retried. DEF432 MINOR-1 (auditor U68, round 1): set ONLY after `refund()`
has actually returned successfully, never on the mere decision to attempt
one — a failed refund must never claim the room was not charged.

`cio_context_snapshot`: nullable JSONB holding the pre-CIO desk-phase
products (trader levels/sizing, withheld/scripted rosters, the fundamentals
`profile`) a CIO-outage PASS needs to replay just the CIO step without
re-running the other eleven desks. Written only on that one verdict shape;
every other row (including every row before this column shipped) reads
NULL, the same absence convention `interrupted_at`/`sheet_state` already use
in this table and the verdict JSONB respectively.

`cio_retried`: set True once a "Ask the CIO again" retry SUCCEEDS on this
run (replaces the outage verdict with a real one). Drives the mobile cost
line's third, truthful branch — a retried run finished (so
`roomResultRefunded`'s "didn't reach a verdict" text would be false) but was
never net-charged (the original DEF432 refund stands, and the retry itself
is free), a fact `refunded`/`verdict` alone cannot distinguish from an
ordinary charged completion. Non-nullable, `false` server default.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.db.base import JsonB


revision: str = "cr237a0cio0retry1"
down_revision: Union[str, Sequence[str], None] = "def425a0interrupt1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "room_runs",
        sa.Column(
            "refund_recorded", sa.Boolean(), nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "room_runs",
        sa.Column("cio_context_snapshot", JsonB(), nullable=True),
    )
    op.add_column(
        "room_runs",
        sa.Column(
            "cio_retried", sa.Boolean(), nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("room_runs", "cio_retried")
    op.drop_column("room_runs", "cio_context_snapshot")
    op.drop_column("room_runs", "refund_recorded")
