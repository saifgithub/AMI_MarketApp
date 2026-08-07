"""cr121_client_release_floors

Revision ID: 1d3f04e6d806
Revises: 4aad7942bba0
Create Date: 2026-08-07

CR121 — client version gate. New append-only table `client_release_floors`:
one row per floor raise, never mutated in place. The active floor is the
row with the highest `min_build` among `active=true` rows; a bad raise is
retracted by flipping `active` to false, not by deleting or editing the row
(so "what did we tell users when we killed build N" stays answerable).

No backfill — a brand-new table with zero rows means "no floor configured",
which the read endpoint (`GET /v1/client/release-floor`) resolves to
`action: "ok"` for every build. See
docs/forward_planning/CR121_client_version_gate/CR121_client_version_gate.md.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "1d3f04e6d806"
down_revision: Union[str, Sequence[str], None] = "4aad7942bba0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "client_release_floors",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("min_build", sa.Integer(), nullable=False, unique=True),
        sa.Column("recommended_build", sa.Integer(), nullable=True),
        sa.Column("headline", sa.String(), nullable=False),
        sa.Column("body_en", sa.String(), nullable=False),
        sa.Column("body_ar", sa.String(), nullable=True),
        sa.Column("body_ms", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column(
            "active", sa.Boolean(), nullable=False, server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_table("client_release_floors")
