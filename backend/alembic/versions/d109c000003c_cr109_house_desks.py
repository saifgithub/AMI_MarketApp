"""CR109 slice 3c — house strategy desks: `users.is_desk` + `users.desk_key`.

A desk is a real user row (real portfolio, real NAV series, real fills through
the same game trade path), so it needs no table of its own — only an identity
flag so every entrant-rendering surface can disclose it (design §11.2) and
every real-user metric can subtract it.

Revision ID: d109c000003c
Revises: c164a0f00001
Create Date: 2026-08-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d109c000003c"
down_revision = "c164a0f00001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_desk", sa.Boolean(), nullable=False, server_default=sa.text("false"),
        ),
    )
    op.add_column("users", sa.Column("desk_key", sa.String(), nullable=True))
    op.create_index("ix_users_is_desk", "users", ["is_desk"])
    op.create_unique_constraint("uq_users_desk_key", "users", ["desk_key"])


def downgrade() -> None:
    op.drop_constraint("uq_users_desk_key", "users", type_="unique")
    op.drop_index("ix_users_is_desk", table_name="users")
    op.drop_column("users", "desk_key")
    op.drop_column("users", "is_desk")
