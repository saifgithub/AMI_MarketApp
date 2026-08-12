"""CR109 slice 8 — §8.5 eligibility, and the champion it passes down to.

`users.title_ineligible` is §8.5's one principle as one column: *"Anything
operated by, employed by, or affiliated with AMI Trading may rank, but may
not hold a title, a champion reward, or permanent flair."* One boolean rather
than a column per category (staff, family, UAT, seed, demo, contractor)
because a LIST has to be reopened for every case nobody has thought of yet.
House desks are ineligible from `users.is_desk`, which already exists — see
`games_eligibility.ineligibility_reason` for why that is derived rather than
stored twice.

`game_fields.champion_entry_id` / `champion_rank` record who actually holds
the field's title and where they placed. Those differ whenever the board
leader is ineligible, which at alpha field sizes is the LIKELY case rather
than the exotic one: slice 3c's desks fill every field to
`GAMES_DESK_TARGET_FIELD_SIZE`, so most of the field is the house.

All three default false/NULL with no backfill. Fields that closed before this
slice have no recorded champion — an honest gap, not a title awarded
retroactively by a migration.

Revision ID: f109j000010d
Revises: e109i000009c
Create Date: 2026-08-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f109j000010d"
down_revision = "e109i000009c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "title_ineligible", sa.Boolean(),
            nullable=False, server_default="false",
        ),
    )
    op.add_column("game_fields", sa.Column("champion_entry_id", sa.Uuid(), nullable=True))
    op.add_column("game_fields", sa.Column("champion_rank", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("game_fields", "champion_rank")
    op.drop_column("game_fields", "champion_entry_id")
    op.drop_column("users", "title_ineligible")
