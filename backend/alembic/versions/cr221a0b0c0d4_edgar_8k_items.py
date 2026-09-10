"""edgar_8k_items + edgar_8k_scans — 8-K Item 5.02 text for the Room (CR221 I1)

Revision ID: cr221a0b0c0d4
Revises: cr219a0b0c0d3
Create Date: 2026-09-11

`edgar_facts.value` is `Numeric NOT NULL`, so the one filing the News Analyst
kept asking about — who the incoming CFO is, and whether the outgoing one
retired — could not ride the fact store. These two tables hold the SEC index's
Item 5.02 filings per ticker and the parsed section text, plus one scan row
per ingest pass so the sheet can say "none filed between X and Y" as a dated
claim rather than as silence (CR040).

Additive only. Read by `app/services/edgar_8k.py` at Room time; written only
by `scripts/ingest_edgar_8k.py`. An empty table yields the
`edgar_8k_not_ingested` warn and no sheet line — today's behaviour exactly.

Identity for an item is `(cik, accession_no)`: two AAPL filings share the
primary-document filename `ef20060722_8k.htm`, so the filename alone collides.
Items are read by CIK (through the ticker's scan row), so the read index is
`(cik, filed)`: GOOG and GOOGL share a CIK.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.db.base

revision: str = "cr221a0b0c0d4"
down_revision: Union[str, Sequence[str], None] = "cr219a0b0c0d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "edgar_8k_scans",
        sa.Column("id", app.db.base.Uuid(), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("cik", sa.BigInteger(), nullable=False),
        sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("covered_since", sa.Date(), nullable=False),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column("items_found", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_edgar_8k_scans_ticker_scanned", "edgar_8k_scans", ["ticker", "scanned_at"],
    )

    op.create_table(
        "edgar_8k_items",
        sa.Column("id", app.db.base.Uuid(), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("cik", sa.BigInteger(), nullable=False),
        sa.Column("accession_no", sa.String(), nullable=False),
        sa.Column("form", sa.String(), nullable=False),
        sa.Column("filed", sa.Date(), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=True),
        sa.Column("item_codes", sa.String(), nullable=False),
        sa.Column("primary_document", sa.String(), nullable=False),
        sa.Column("extract_status", sa.String(), nullable=False),
        sa.Column("section_text", sa.String(), nullable=True),
        sa.Column(
            "ingested_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cik", "accession_no", name="uq_edgar_8k_item"),
    )
    op.create_index(
        "ix_edgar_8k_items_cik_filed", "edgar_8k_items", ["cik", "filed"],
    )


def downgrade() -> None:
    op.drop_index("ix_edgar_8k_items_cik_filed", table_name="edgar_8k_items")
    op.drop_table("edgar_8k_items")
    op.drop_index("ix_edgar_8k_scans_ticker_scanned", table_name="edgar_8k_scans")
    op.drop_table("edgar_8k_scans")
