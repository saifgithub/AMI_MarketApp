"""CR192's vllm_cache_samples table, re-minted after DEF337.

This REPLACES `b4c1d2e3f501`, which was deleted rather than edited — and here
is why that was safe when DEF278 says editing never is: that revision declared
`sampled_at` with `index=True` inside `op.create_table` AND then ran an
explicit `op.create_index` with the identical canonical name, so its own
second statement collides with its first on every engine that runs it. It
failed on live Alpha at promote time (alpha-2026-08-20-1 preflight,
DuplicateTable inside transactional DDL, fully rolled back — DB verified still
at a309a000001c with no table remnant) and it fails the same way on a fresh
sqlite. A migration that cannot complete anywhere can never have been stamped
anywhere: "never applied" is, uniquely for a self-colliding file, a property
of the file itself rather than of any database's history. DEF278's hole —
another track promoting the old version between your commits — needs a
version that RUNS.

The table itself is unchanged from CR192's design — raw lifetime counters,
BigInteger, reset-detectable at read time. See VllmCacheSampleRow in
app/db/models.py for the full reasoning.

Revision ID: c192f000001d
Revises: a309a000001c
"""

from alembic import op
import sqlalchemy as sa

revision = "c192f000001d"
down_revision = "a309a000001c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # index=True is the ONLY index creation here. The auto-generated name is
    # ix_vllm_cache_samples_sampled_at; a second explicit create_index with
    # that name is exactly DEF337.
    op.create_table(
        "vllm_cache_samples",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "sampled_at", sa.DateTime(timezone=True), nullable=False, index=True
        ),
        sa.Column("base_url", sa.String(), nullable=False),
        sa.Column("model_name", sa.String(), nullable=True),
        sa.Column("queries_total", sa.BigInteger(), nullable=False),
        sa.Column("hits_total", sa.BigInteger(), nullable=False),
    )


def downgrade() -> None:
    # drop_table drops the table's indexes with it.
    op.drop_table("vllm_cache_samples")
