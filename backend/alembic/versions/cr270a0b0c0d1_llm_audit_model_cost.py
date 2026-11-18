"""cr270_llm_audit_model_cost — record the served model and the USD cost of each LLM call

Revision ID: cr270a0b0c0d1
Revises: c253a0ratio0base
Create Date: 2026-11-18

AT:B1 CR270 (CR267 WP-12) — `llm_audit` named the provider but never the model,
and no cost was computed anywhere, so a daily spend ceiling had nothing to sum.

Both columns are NULLable with no server_default and NO backfill. NULL `model`
means "not recorded" (every pre-CR270 row); NULL `cost_usd` means "unknown"
(no price for the model, or no token counts) and is never read as free.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "cr270a0b0c0d1"
down_revision: Union[str, Sequence[str], None] = "c253a0ratio0base"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("llm_audit", sa.Column("model", sa.String(), nullable=True))
    op.add_column("llm_audit", sa.Column("cost_usd", sa.Numeric(14, 8), nullable=True))


def downgrade() -> None:
    op.drop_column("llm_audit", "cost_usd")
    op.drop_column("llm_audit", "model")
