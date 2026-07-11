"""reputation_events_dedup_index — partial unique index (DEF039)

Revision ID: d1e2f3a40015
Revises: c3d4e5f60014
Create Date: 2026-07-11

CR004 audit round-1 finding F2: reputation_service.award()'s
(user_id, event_type, ref_id) dedup was app-code-only (a SELECT-then-INSERT
race) — two concurrent award() calls for the same ref could both pass the
check and double-insert a monetized-currency grant. Adds the DB-level
backstop as a partial unique index (ref_id is nullable and award() only
dedups when a ref_id is given, so the constraint only applies where
ref_id IS NOT NULL).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d1e2f3a40015"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f60014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_reputation_event_dedup",
        "reputation_events",
        ["user_id", "event_type", "ref_id"],
        unique=True,
        postgresql_where=sa.text("ref_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_reputation_event_dedup", table_name="reputation_events")
