"""CR141 — llm_audit usage-capture columns

Revision ID: 2a08e21c0dac
Revises: e4f5a6b70030
Create Date: 2026-08-07

`LLMGateway.stream_chat` yielded text and discarded the terminal `usage`
frame, so we could not measure input/output/cache tokens for any provider
from our own data (CR017 §2.4's 18.5% vLLM figure came from the vLLM
server's `/metrics`, not from us). The gateway now threads usage through the
existing DEF125 `meta` channel into `record_llm_call`; these four columns are
where it lands.

All four are nullable with NO server_default and NO backfill — every
pre-CR141 row simply has all four NULL, correctly, because usage was never
captured for it. Going forward, NULL vs 0 is a real distinction the app
depends on (CR040 degrade-loudly, acceptance 2 of CR141): a provider that
does not report a cache field must record NULL ("unmeasured"), never 0
("measured, no hit") — see the LLMAuditRow docstring and
`provider_policy`/`llm_gateway` for where that invariant is enforced in code.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "2a08e21c0dac"
down_revision: Union[str, Sequence[str], None] = "e4f5a6b70030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("llm_audit", sa.Column("input_tokens", sa.Integer(), nullable=True))
    op.add_column("llm_audit", sa.Column("output_tokens", sa.Integer(), nullable=True))
    op.add_column("llm_audit", sa.Column("cache_read_tokens", sa.Integer(), nullable=True))
    op.add_column("llm_audit", sa.Column("cache_write_tokens", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("llm_audit", "cache_write_tokens")
    op.drop_column("llm_audit", "cache_read_tokens")
    op.drop_column("llm_audit", "output_tokens")
    op.drop_column("llm_audit", "input_tokens")
