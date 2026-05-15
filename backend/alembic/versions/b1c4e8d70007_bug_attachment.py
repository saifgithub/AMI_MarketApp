"""bug_reports: add attachment_path + attachment_mime for file uploads

Revision ID: b1c4e8d70007
Revises: a8e3c1b50006
Create Date: 2026-05-15

AT:R20 — in-app bug reporter can now attach a photo. The file lives on
the api-alpha host filesystem under a named docker volume mounted at
/data/bug_attachments/; the DB just carries the relative path + the
MIME type the upload presented. Both columns nullable — the existing
text-only report path is unchanged.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b1c4e8d70007"
down_revision: Union[str, None] = "a8e3c1b50006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "bug_reports",
        sa.Column("attachment_path", sa.String(), nullable=True),
    )
    op.add_column(
        "bug_reports",
        sa.Column("attachment_mime", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("bug_reports", "attachment_mime")
    op.drop_column("bug_reports", "attachment_path")
