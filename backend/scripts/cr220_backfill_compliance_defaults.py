"""CR220 backfill — repair the inverted `long_only` / `liquid_only` defaults.

Unlike CR129's backfill this one DOES write. The defect was in
`_parse_constraints` (`app/services/concierge_engine.py`), which returned the
two RESTRICTION flags as bare keyword hits: a user who answered "No hard
rules" got `long_only=False, liquid_only=False` stored, while `Compliance`
defaults both to `True`. An ONBOARDED user therefore came out strictly LESS
constrained than one who never onboarded and got `get_or_default()`'s schema
defaults. Fixing the parser corrects new interviews; every mandate already
stored still carries the inverted pair, so there is a real row to repair.

RULED by Saiful 2026-09-02: backfill everyone, rather than fix-forward only.
One population, one meaning — leaving two cohorts with different defaults for
the same answer is the confusion the fix exists to remove.

**This TIGHTENS a live safety control.** A short or a microcap position that
was permitted yesterday may be refused after this runs. That is the intended
outcome, but it must never be silent (CR040), so each repaired user gets a
`MANDATE_EDIT` journal entry naming exactly what changed and why, and the
change rides a real mandate version bump so it appears in history and in
`GET /v1/mandate/{id}/versions` like any other edit.

Deliberately NOT repaired: a user who explicitly asked to loosen a flag. The
parser's opt-out phrasings ("I want to short") are honoured, and this script
cannot distinguish "chose False" from "defaulted to False" for the two flags
in isolation — so `--only-untouched` restricts the run to users whose mandate
is still at the version onboarding produced (v1) and who have never edited
compliance. Use it if the blast radius is judged too wide at run time.

Usage (Mac has no DB; runs inside `ami_api_alpha`):

    scp backend/scripts/cr220_backfill_compliance_defaults.py melehost:/tmp/
    ssh melehost "docker cp /tmp/cr220_backfill_compliance_defaults.py ami_api_alpha:/tmp/"

    # dry run (default) — prints who WOULD change, writes nothing
    ssh melehost "docker exec ami_api_alpha python /tmp/cr220_backfill_compliance_defaults.py"

    # apply
    ssh melehost "docker exec ami_api_alpha python /tmp/cr220_backfill_compliance_defaults.py --apply"
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
from app.services.mandate_store import MandateStore

# The two flags `Compliance` defaults to True and the old parser stored False.
_RESTRICTION_FLAGS = ("long_only", "liquid_only")

_FLAG_LABELS = {
    "long_only": "long-only (no short positions)",
    "liquid_only": "liquid names only (no microcaps)",
}


def flags_to_repair(mandate: Mandate) -> list[str]:
    """Which restriction flags this mandate has stored as False."""
    return [f for f in _RESTRICTION_FLAGS if getattr(mandate.compliance, f) is False]


def disclosure_summary(flags: list[str]) -> str:
    """Plain English, in the user's terms — this is read in mandate history by
    someone wondering why a trade started being refused."""
    named = " and ".join(_FLAG_LABELS[f] for f in flags)
    return (
        f"Restored {named} — the onboarding interview recorded this as off for "
        f"everyone who did not name it, which left your mandate less restricted "
        f"than the default. You can change it in Settings → Compliance."
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--apply", action="store_true",
        help="write the repair (default is a dry run — prints only)",
    )
    ap.add_argument(
        "--only-untouched", action="store_true",
        help="restrict to mandates still at v1 (never edited since onboarding), "
             "so a deliberate user choice is never overwritten",
    )
    args = ap.parse_args(argv)

    session = get_sessionmaker()()
    try:
        rows = session.execute(
            select(MandateRow).where(MandateRow.is_current.is_(True))
        ).scalars().all()
        snapshots = [(r.user_id, r.snapshot) for r in rows]
    finally:
        session.close()

    mode = "APPLY" if args.apply else "DRY RUN"
    scope = "v1-only" if args.only_untouched else "all current mandates"
    print(f"CR220 compliance-default backfill — {mode} ({scope})")
    print("-" * 70)

    store = MandateStore()
    affected = 0
    skipped_edited = 0

    for user_id, snapshot in snapshots:
        mandate = Mandate.model_validate(snapshot)
        flags = flags_to_repair(mandate)
        if not flags:
            continue
        if args.only_untouched and mandate.version != 1:
            skipped_edited += 1
            continue

        affected += 1
        summary = disclosure_summary(flags)
        print(f"user {user_id} (v{mandate.version}): {', '.join(flags)}")

        if args.apply:
            updated = store.patch(user_id, {"compliance": {f: True for f in flags}})
            get_journal_store().append(JournalEntryCreate(
                user_id=user_id,
                entry_type=EntryType.MANDATE_EDIT,
                reference_id=None,
                title=f"Mandate edited → v{updated.version}",
                summary=summary,
                tags=["mandate", "cr220_backfill"],
                payload={
                    "backfill": "cr220",
                    "flags_restored": flags,
                    "mandate_version": updated.version,
                },
            ))

    print("-" * 70)
    print(f"  mandates checked   : {len(snapshots)}")
    print(f"  affected users     : {affected}")
    if args.only_untouched:
        print(f"  skipped (edited)   : {skipped_edited}")
    if not args.apply:
        print("\n  dry run — re-run with --apply to write the repair.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
