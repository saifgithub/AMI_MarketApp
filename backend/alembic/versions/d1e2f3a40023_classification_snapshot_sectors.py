"""classification_universe_snapshots — add per-ticker GICS sector map (CR026)

Revision ID: d1e2f3a40023
Revises: c9f0a1b20022
Create Date: 2026-07-26

CR026: sector-concentration enforcement + the Portfolio-screen allocation feed. The
mandate's "no sector > 40%" rule was advertised (lifecycle.md) but never enforced by
the deterministic safety floor, and there was no per-ticker sector datum to resolve
from off the request path. This adds a `sectors` JSON map (ticker → raw GICS sector
string, e.g. "Technology") onto the DEF061 classification snapshot — populated in the
SAME daily `_classification_universe_refresh()` pass from the `info["sector"]` field
the fossil/sin classifier already reads. The request path resolves ticker → sector
from this stored map (no yfinance socket, per CR075/DEF089); a ticker absent from it
resolves to "Other" (disclosed, never blocking — the DEF059 inversion guard).

Back-fills existing rows to an empty map (`{}`), so a row written before CR026 simply
carries no sector tags until the next refresh appends a fresh row with them.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.db.base import JsonB


revision: str = "d1e2f3a40023"
down_revision: Union[str, Sequence[str], None] = "c9f0a1b20022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "classification_universe_snapshots",
        sa.Column(
            "sectors", JsonB(), nullable=True, server_default=sa.text("'{}'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("classification_universe_snapshots", "sectors")
