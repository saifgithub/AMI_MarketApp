"""cr210_llm_audit_constraint_status — record whether a decoding grammar was in force

Revision ID: cr210a0b0c0d1
Revises: cr194a0b0c0d1
Create Date: 2026-08-27

AT:R74 CR210 — structured output is config-gated per provider, and only the
on-prem vLLM enforces it. Without this column "the PM verdict parsed" means two
different things depending on which provider answered: a grammar guarantee on
vLLM, and CR143's tolerant parser doing the work everywhere else. That is exactly
the shape that shipped dark twice (DEF038, DEF063).

NULLABLE with no server_default and NO backfill. Every row written before this
column existed had no constraint requested, and NULL is the honest record of
that — distinct from 'unsupported', which means one WAS requested and the
provider could not enforce it. Backfilling either value would be inventing the
answer to the only question the column exists to ask.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "cr210a0b0c0d1"
down_revision: Union[str, Sequence[str], None] = "cr194a0b0c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "llm_audit", sa.Column("constraint_status", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("llm_audit", "constraint_status")
