"""CR136 M03 — create portfolio_value_snapshots (one valuation row per sim portfolio per trading day, F16 vol columns, unique (portfolio_id, as_of))

Revision ID: b1c2d3e40027
Revises: a9b0c1d20026
Create Date: 2026-08-02

CR136 Tier 2 is the realised history that accumulates behind the forward-looking
Tier-1 metrics — and, per Rev 4 F16, the layer that VALIDATES them. Each row
stores the Tier-1 predicted volatility beside the realised value, so the model
is permanently auditable: the bias test computes z = realised return / predicted
vol and expects sd(z) ~ 1 (band [0.911, 1.089] at T=252). Without the prediction
stored at the time it was made, that check is unreconstructible.

Rows are keyed to `portfolio_id`, not `user_id`, so a series structurally cannot
span a reset — `reset_portfolio` is destroy-and-recreate and the replacement gets
a new UUID. The unique constraint on (portfolio_id, as_of) is the database-level
backstop behind the tick's own check-before-insert.

`drawdown_pct` here is the sim's existing vs-STARTING-CAPITAL number, NOT the
Tier-2 rolling peak-to-trough drawdown. Two different quantities were once both
called "drawdown" in this codebase; the Tier-2 tile computes its own from
total_value history and never reads this column.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.db.base  # noqa: F401 — the portable Uuid the ORM model declares


revision: str = "b1c2d3e40027"
down_revision: Union[str, Sequence[str], None] = "a9b0c1d20026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "portfolio_value_snapshots",
        sa.Column("id", app.db.base.Uuid(), nullable=False),
        sa.Column("user_id", app.db.base.Uuid(), nullable=False),
        sa.Column("portfolio_id", app.db.base.Uuid(), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("total_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("cash", sa.Numeric(12, 2), nullable=False),
        sa.Column("invested_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("drawdown_pct", sa.Float(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column(
            "captured_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("predicted_vol_ann", sa.Float(), nullable=True),
        sa.Column("n_observations", sa.Integer(), nullable=True),
        sa.Column("engine_version", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["portfolio_id"], ["sim_portfolios.id"], ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("portfolio_id", "as_of", name="uq_pvs_portfolio_asof"),
    )
    op.create_index(
        "ix_pvs_portfolio_asof", "portfolio_value_snapshots", ["portfolio_id", "as_of"],
    )
    op.create_index(
        "ix_portfolio_value_snapshots_user_id", "portfolio_value_snapshots", ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_portfolio_value_snapshots_user_id", table_name="portfolio_value_snapshots",
    )
    op.drop_index("ix_pvs_portfolio_asof", table_name="portfolio_value_snapshots")
    op.drop_table("portfolio_value_snapshots")
