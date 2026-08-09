"""CR158 — llm_audit.prompt_version

Revision ID: b7c31f9d4e05
Revises: 8c5b1a70f4d2
Create Date: 2026-08-09

Nothing recorded which prompt generation produced a stored turn. `llm_audit`
kept `system_prompt` verbatim across 19 columns and said nothing about the
prompt's provenance; `room_runs` has no prompt field at all. So every epoch
boundary in the CR143 audit was reconstructed by hand from git SHAs, with
nothing checking the reconstruction — and it produced a wrong published
figure (an 18.4% PM-reformatter rate pooled across a prompt change; 0/18 on
the epoch it was actually measuring).

This column is where `app/services/prompt_version.py`'s hash lands: a short
digest of the fully assembled prompt for a fixed reference mandate, so it
changes when an assembly layer changes and not when a user's mandate does.

Nullable, NO server_default, NO backfill — deliberately, and permanently.
Every pre-CR158 row is NULL, which correctly reads as "unversioned", not
"version zero"; the same CR040 distinction the four CR141 `*_tokens` columns
above draw, and for the same reason. A NULL is also what a row gets when the
reference assembly fails or when the flow has no agent at all (Concierge, the
reformatter): an honest unknown, never a fabricated generation. The whole
point of the column is that a measurement can trust which prompt it is
measuring, so a placeholder here would defeat it.

DEF215 applies: Alembic owns this table. `init_schema` must not `create_all`
it — see `test_def215_schema_ownership.py`.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b7c31f9d4e05"
down_revision: Union[str, Sequence[str], None] = "8c5b1a70f4d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("llm_audit", sa.Column("prompt_version", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("llm_audit", "prompt_version")
