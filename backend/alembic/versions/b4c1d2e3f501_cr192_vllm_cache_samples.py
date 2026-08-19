"""CR192 — vllm_cache_samples: raw prefix-cache counter readings.

The counters are stored as they came off `/metrics`, lifetime-cumulative and
un-normalised. A rate column would have been smaller and is exactly wrong: the
counters reset when the vLLM process restarts (measured 2026-08-19, 1,064,911
against 59,681,175 three days earlier), and only the raw pair makes that
detectable at read time. A stored rate would have hidden a restart as a cache
collapse.

BigInteger, not Integer: the 2026-08-16 reading was already 5.9e7.

Revision ID: b4c1d2e3f501
Revises: a309a000001c
"""

from alembic import op
import sqlalchemy as sa

revision = "b4c1d2e3f501"
down_revision = "a309a000001c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vllm_cache_samples",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("sampled_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("base_url", sa.String(), nullable=False),
        sa.Column("model_name", sa.String(), nullable=True),
        sa.Column("queries_total", sa.BigInteger(), nullable=False),
        sa.Column("hits_total", sa.BigInteger(), nullable=False),
    )
    op.create_index(
        "ix_vllm_cache_samples_sampled_at", "vllm_cache_samples", ["sampled_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_vllm_cache_samples_sampled_at", table_name="vllm_cache_samples")
    op.drop_table("vllm_cache_samples")
