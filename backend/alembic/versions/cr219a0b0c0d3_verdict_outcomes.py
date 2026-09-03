"""verdict_outcomes — the Room's calibration ledger (CR219 R55)

Revision ID: cr219a0b0c0d3
Revises: def335a0b0c0d2
Create Date: 2026-09-03

One row per banked Room verdict, carrying the reference price the Room was
actually shown and the forward return at the mandate's horizon.

**Sanity floor, not a performance claim.** The ledger exists to answer "are
APPROVEs systematically worse than PASSes" and "does conviction mean anything"
— floors any functioning decision process must clear. AMI Trade is a
simulation-only education product; nothing here is a track record and nothing
here reaches a user (internal, admin-gated only).

Additive only. Nothing reads this table until the writer hook banks rows, and
an empty table yields an aggregates endpoint reporting zero counts — today's
behaviour exactly.

`room_run_id` is UNIQUE, not merely indexed: re-persisting a run must update
its ledger row, never mint a second one. `ondelete="CASCADE"` follows the
`sim_portfolios` children — a purged run leaves no orphan outcome.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "cr219a0b0c0d3"
down_revision: Union[str, Sequence[str], None] = "def335a0b0c0d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "verdict_outcomes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("room_run_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("verdict_action", sa.String(), nullable=False),
        sa.Column("conviction", sa.String(), nullable=True),
        sa.Column("approve_votes", sa.Integer(), nullable=True),
        sa.Column("samples", sa.Integer(), nullable=True),
        sa.Column("size_pct", sa.Float(), nullable=True),
        sa.Column("reference_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("reference_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column(
            "status", sa.String(), nullable=False, server_default=sa.text("'pending'"),
        ),
        sa.Column("outcome_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("outcome_date", sa.Date(), nullable=True),
        sa.Column("forward_return", sa.Float(), nullable=True),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exclusion_reason", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["room_run_id"], ["room_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("room_run_id", name="uq_verdict_outcomes_room_run"),
    )
    op.create_index("ix_verdict_outcomes_user_id", "verdict_outcomes", ["user_id"])
    op.create_index("ix_verdict_outcomes_ticker", "verdict_outcomes", ["ticker"])
    op.create_index("ix_verdict_outcomes_status", "verdict_outcomes", ["status"])
    op.create_index(
        "ix_verdict_outcomes_user_ticker", "verdict_outcomes", ["user_id", "ticker"],
    )


def downgrade() -> None:
    op.drop_index("ix_verdict_outcomes_user_ticker", table_name="verdict_outcomes")
    op.drop_index("ix_verdict_outcomes_status", table_name="verdict_outcomes")
    op.drop_index("ix_verdict_outcomes_ticker", table_name="verdict_outcomes")
    op.drop_index("ix_verdict_outcomes_user_id", table_name="verdict_outcomes")
    op.drop_table("verdict_outcomes")
