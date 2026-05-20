"""users: add display_name column for Apple/Google first-auth name persistence

Revision ID: b3f9d2a80007
Revises: a9d1c7e80006
Create Date: 2026-05-21

AT:R29 — Apple Sign-In Phase 3 follow-up.

Both Apple and Google OIDC providers hand us a name on first auth:
  - Apple: givenName + familyName from the iOS SDK on the first
    SignInWithApple consent screen, joined into `full_name` on the
    request body. Apple does not include name in subsequent JWTs.
  - Google: `name` claim in the ID token (with `profile` scope), present
    on every sign-in. (To land in A6b — Android slice.)

Without this column we were logging the name and throwing it away.
Now we persist it once and never overwrite — matches the same "don't
overwrite real values" rule we use for `users.email`.

Minimum-data policy (locked in AT:R29 — see project_plan.md A6/A6b):
  We ask both providers for sub, name, and email. Nothing else.
  Specifically we do NOT persist Google's `picture` or `locale` even
  though they're in the default `profile` scope.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b3f9d2a80007"
down_revision: Union[str, Sequence[str], None] = "a9d1c7e80006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("display_name", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "display_name")
