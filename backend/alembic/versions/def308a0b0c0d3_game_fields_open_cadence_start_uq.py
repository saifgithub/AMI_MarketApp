"""def308_game_fields_open_cadence_start_uq - one live open field per (cadence, starts_on)

Revision ID: def308a0b0c0d3
Revises: cr267a24bank01
Create Date: 2026-11-20

AT:B1 DEF308 (ISS001 Phase 3, last of the 9 sites). `games_service.ensure_field` read for an
open field of `(cadence, starts_on)` and inserted when absent, with no unique key behind it, so
two concurrent first touches of a period could create twin fields. Additive: one partial unique
index, `uq_game_fields_open_cadence_start (cadence, starts_on) WHERE kind='open' AND
state<>'abandoned'`. Abandoned lobbies are excluded on purpose (a rolling lobby that never filled
is replaced by a fresh one with the same calendar start); private fields (kind<>'open') are
excluded because their window is not the cadence's.

Alpha was measured read-only 2026-11-20: 0 duplicate groups, so no dedupe step is needed. The
index build would fail loudly (naming the key) if one appeared before deploy. Idempotent: skips
when the index already exists. Downgrade drops it.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "def308a0b0c0d3"
down_revision: Union[str, Sequence[str], None] = "cr267a24bank01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX = "uq_game_fields_open_cadence_start"
_WHERE = "kind = 'open' AND state <> 'abandoned'"


def _has_index(conn) -> bool:
    return any(ix["name"] == INDEX for ix in sa.inspect(conn).get_indexes("game_fields"))


def upgrade() -> None:
    conn = op.get_bind()
    if _has_index(conn):
        return
    op.create_index(
        INDEX, "game_fields", ["cadence", "starts_on"], unique=True,
        postgresql_where=sa.text(_WHERE),
        sqlite_where=sa.text(_WHERE),
    )


def downgrade() -> None:
    if _has_index(op.get_bind()):
        op.drop_index(INDEX, table_name="game_fields")
