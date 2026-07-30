"""CR129 backfill journal — one-time loud disclosure for existing mandates.

Structural backfill, not a data migration: every mandate with an unset
`single_name_cap_pct` / `post_loss_cooldown_hours` / `max_open_positions` /
`max_trades_per_day` / `max_trades_per_week` / `max_open_risk_pct` already
resolves to CR129's risk-tier preset the instant the code deploys (see
`app.services.risk_limit_backfill`) — there is no row to UPDATE. This script
writes ONLY a `MANDATE_EDIT` journal entry per affected user (CR040 — a loud,
one-time "here's what changed and why"), never a new mandate version.

Idempotent: re-running finds the same affected users and appends another
disclosure entry. Safe (the journal is additive history, not state), but
pointless to run twice — check the previous run's output first.

Usage — see `scripts/def110_backfill.py` for the container copy/exec pattern
this mirrors (Mac has no DB; runs inside `ami_api_alpha`):

    scp backend/scripts/cr129_backfill_journal.py melehost:/tmp/
    ssh melehost "docker cp /tmp/cr129_backfill_journal.py ami_api_alpha:/tmp/"

    # dry run (default) — prints who WOULD be journalled, writes nothing
    ssh melehost "docker exec ami_api_alpha python /tmp/cr129_backfill_journal.py"

    # apply
    ssh melehost "docker exec ami_api_alpha python /tmp/cr129_backfill_journal.py --apply"
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from app.db.models import MandateRow
from app.db.session import get_sessionmaker
from app.schemas import Mandate
from app.schemas.journal import EntryType, JournalEntryCreate
from app.services.journal_store import get_journal_store
from app.services.risk_limit_backfill import backfill_disclosure_summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--apply", action="store_true",
        help="write the journal entries (default is a dry run — prints only)",
    )
    args = ap.parse_args(argv)

    session = get_sessionmaker()()
    try:
        rows = session.execute(
            select(MandateRow).where(MandateRow.is_current.is_(True))
        ).scalars().all()
    finally:
        session.close()

    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"CR129 backfill journal — {mode}")
    print("-" * 60)

    affected = 0
    for row in rows:
        mandate = Mandate.model_validate(row.snapshot)
        summary = backfill_disclosure_summary(mandate)
        if summary is None:
            continue
        affected += 1
        print(f"user {row.user_id}: {summary}")
        if args.apply:
            get_journal_store().append(JournalEntryCreate(
                user_id=row.user_id,
                entry_type=EntryType.MANDATE_EDIT,
                reference_id=None,
                title=f"Mandate edited → v{mandate.version}",
                summary=summary,
                tags=["mandate", "cr129_backfill"],
                payload={"backfill": "cr129", "mandate_version": mandate.version},
            ))

    print("-" * 60)
    print(f"  mandates checked  : {len(rows)}")
    print(f"  affected users    : {affected}")
    if not args.apply:
        print("\n  dry run — re-run with --apply to write the journal entries.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
