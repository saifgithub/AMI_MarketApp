"""users: add device_model, os_version, last_app_version (BL1)

Revision ID: c4e8f1a90008
Revises: b3f9d2a80007
Create Date: 2026-05-22

AT:R33 — BL1. Mobile sends `device_model` (e.g. "iPhone15,2"),
`os_version` (e.g. "iOS 18.2"), and `app_version` (e.g. "0.1.0+26")
on every `POST /v1/auth/anon` call. We persist the latest values onto
the `users` row so the admin back-office can answer "what build is
this anonymous tester on?" without a round-trip through the bug-report
form. All three columns are nullable — old clients omit them, the call
still succeeds.

Single-device-per-user is the locked alpha assumption — multi-device
tracking is BL2.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c4e8f1a90008"
down_revision: Union[str, Sequence[str], None] = "b3f9d2a80007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("device_model", sa.String(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("os_version", sa.String(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("last_app_version", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "last_app_version")
    op.drop_column("users", "os_version")
    op.drop_column("users", "device_model")
