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

**On `--only-untouched`, and what it cannot do (CR220 MAJOR-1 of round 1).**
The flag originally claimed to protect "a user who explicitly asked to loosen a
flag", using `version == 1` as the proxy. That is precisely backwards: an
interview opt-out ("I want to short") is written BY onboarding, so it lands at
**v1** and the predicate included exactly the cohort the sentence promised to
skip — while skipping the Settings-editors it never mentioned.

The promise is not merely mis-implemented, it is **unachievable from the stored
data**: Q7's raw text is never persisted (`concierge_engine.py:284` stores only
the parsed dict), so nothing in a mandate distinguishes "chose False" from
"defaulted to False". No predicate over `mandates` can recover that.

So the flag now claims only what it can prove, and its name says which cohort it
skips: `--skip-edited` restricts the run to mandates still at v1, i.e. it skips
users who have edited their mandate SINCE onboarding — a Settings edit is
positive evidence of a deliberate choice, a v1 value is not. An interview
opt-out is therefore still repaired by both modes, and `disclosure_summary`
no longer tells that cohort something false.

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
    # CR220 MAJOR-2: the old wording asserted WHY the flag was off — "the
    # interview recorded this as off for everyone who did not name it" — which
    # is false for anyone who DID name it and asked to short. The script cannot
    # tell the two apart (Q7's raw text is never stored), so the disclosure now
    # states only what is true for every recipient: what changed, and how to
    # change it back. A disclosure that guesses at the user's own history is
    # worse than one that does not mention it.
    return (
        f"Restored {named}. This is the default for every mandate, and yours "
        f"was set the other way. If that was deliberate, you can turn it back "
        f"off in Settings → Compliance."
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--apply", action="store_true",
        help="write the repair (default is a dry run — prints only)",
    )
    ap.add_argument(
        "--skip-edited", action="store_true",
        help="restrict to mandates still at v1, i.e. SKIP users who have edited "
             "their mandate since onboarding. Does NOT protect an interview "
             "opt-out — that is unachievable from stored data; see the module "
             "docstring.",
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
    scope = "v1 only (skipping edited)" if args.skip_edited else "all current mandates"
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
        if args.skip_edited and mandate.version != 1:
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
    if args.skip_edited:
        print(f"  skipped (edited)   : {skipped_edited}")
    if not args.apply:
        print("\n  dry run — re-run with --apply to write the repair.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
