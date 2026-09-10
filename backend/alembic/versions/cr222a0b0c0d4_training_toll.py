"""training toll charged per fill — CR222 §1, Ruling 1 (option B, no backfill)

Revision ID: cr222a0b0c0d4
Revises: cr221a0b0c0d4 (re-parented from cr219a0b0c0d3 — DEF406: both lanes
branched the same parent, leaving two heads the promotion's `upgrade head`
would refuse)
Create Date: 2026-09-11

Three additive NULLABLE columns, one on each table that records a training fill:
`sim_trades.toll_charged` (equity fills, through `_execute_fill`),
`sim_short_positions.toll_charged` (a short's open plus its cover — that
position writes no trade row, by CR171's separate-table rule), and
`sim_option_trades.toll_charged` (a structure's open, at the option rate on
premium notional).

`sim_short_positions.toll_charged` is deliberately NOT folded into that table's
existing `borrow_accrued_total`: the toll is a transaction cost per fill and the
borrow is a holding cost per day, and one column holding both would make the
daily accrual impossible to audit against its own stored rate.

**No server_default, no data migration, and that is Ruling 1 in schema form.**
Every existing row reads NULL, which means "this fill predates the toll" — a
different fact from "this fill was charged nothing", and only the second is
ever a measurement (CR040). A `server_default='0'` would re-cost the whole
history as free trading, which is a backfill of amounts wearing a default's
clothes; the ruling forbids it.

The cumulative toll is DERIVED by summing these columns per portfolio rather
than kept as a counter on `sim_portfolios`. That choice is what makes both
guarantees free: NULL sums to nothing, so no portfolio's cumulative moves
because of a pre-flag fill; and `reset_portfolio()` destroys the portfolio row
and every trade row under it before recreating with a fresh UUID — the event
`portfolio_nav_daily` records as `restart` — so a wiped book's cumulative is 0
again with no reset code to write and none to forget.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "cr222a0b0c0d4"
down_revision: Union[str, Sequence[str], None] = "cr221a0b0c0d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sim_trades",
        sa.Column("toll_charged", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "sim_short_positions",
        sa.Column("toll_charged", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "sim_option_trades",
        sa.Column("toll_charged", sa.Numeric(12, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sim_option_trades", "toll_charged")
    op.drop_column("sim_short_positions", "toll_charged")
    op.drop_column("sim_trades", "toll_charged")
