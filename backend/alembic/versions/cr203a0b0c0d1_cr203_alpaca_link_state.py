"""cr203_alpaca_link_state — track WHICH users have a linked Alpaca account

Revision ID: cr203a0b0c0d1
Revises: cr202a0d0e0f1
Create Date: 2026-08-22

AT:R74 CR203 — CR202 moved the Alpaca credential to the device, which also
removed the host's only way to answer "who has linked an account?". This adds
that answer back WITHOUT adding the credential back.

`alpaca_linked_at` is a timestamp, not a secret: it records when the device
last reported a linked paper account. NULL = not linked. There is no key, no
token, and nothing here that could authenticate to Alpaca — which is why this
does not re-open DEF044/DEF181/DEF182/DEF185, all of which were consequences
of holding the *credential*.

Note the column name is one CR202's migration dropped. That is deliberate and
not a revert: the original `alpaca_linked_at` sat beside the two credential
columns and was dropped with them as a block. The credential columns stay
gone, and `test_cr202_no_host_side_credentials.py` still forbids them by name.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "cr203a0b0c0d1"
down_revision: Union[str, Sequence[str], None] = "cr202a0d0e0f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("alpaca_linked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "alpaca_linked_at")
