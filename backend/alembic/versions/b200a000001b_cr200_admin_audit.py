"""CR200 — admin_audit: attributed audit trail for admin back-office writes.

One row per admin write action, naming the operator (CF Access email /
service-token common_name / "static_bearer"). Written best-effort by
`services/admin_audit.py`. Index created here explicitly, not via
`index=True` in `create_table` (DEF337 class: one index creation path only).
No retention sweep — excluded from `trim_audit_tables()` by design (tiny,
human-scale volume; permanent forensic value).

Revision ID: b200a000001b
Revises: a181a000002a
"""

from alembic import op
import sqlalchemy as sa

from app.db.base import JsonB

revision = "b200a000001b"
down_revision = "a181a000002a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_audit",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("operator", sa.String(), nullable=False),
        sa.Column("auth_kind", sa.String(16), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("target", sa.String(), nullable=True),
        sa.Column("payload", JsonB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )
    op.create_index("ix_admin_audit_created_at", "admin_audit", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_admin_audit_created_at", table_name="admin_audit")
    op.drop_table("admin_audit")
