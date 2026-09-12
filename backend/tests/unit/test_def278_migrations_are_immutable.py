"""DEF278 — a committed migration is never edited.

The bug: `c109g000007a` was committed adding two columns, then EDITED in a
later commit of the same slice to add a third (`game_fields.starts_decided_at`).
The reasoning at the time was that the revision had never been applied anywhere
— Alpha's head was measured two revisions behind — so extending it beat
shipping two migrations for one slice.

That reasoning has a hole that exists only on a shared checkout: **"never
applied" is not a property you can verify once and then rely on.** Another
track promoted from `main` between the two commits. Alpha ran the two-column
version, stamped the revision, and now sits at head by Alembic's reckoning
while missing a column the file claims to create. No later `upgrade head` will
ever add it — there is no revision left to run.

**Why this check and not a schema comparison.** The obvious guard is to run the
whole chain against a throwaway database and diff the result against
`models.py`. That was written first and does not work: the chain contains
Postgres-only DDL (`gen_random_uuid()` in the device-install backfill), so it
cannot execute on the SQLite the unit suite uses, and gating it on "a real
Postgres is available" makes it skip in every local run — a check that never
executes, which is the DEF038/DEF063 shape this project has been bitten by
twice.

More importantly, a schema comparison would not have caught this one. The
column IS in the migration file; what differed was the version of that file
Alpha actually ran. The invariant that was broken is not "models and
migrations agree" but "a migration, once committed, is immutable" — and that
is exactly what git can answer.

Related: `test_def215_schema_ownership.py` guards that Alembic owns the schema
on a database that has an `alembic_version` row. This guards the other
direction that was open.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_VERSIONS = _REPO_ROOT / "backend" / "alembic" / "versions"

# Migrations edited after their introducing commit, BEFORE this guard existed.
# Baselined rather than re-litigated: two are long-shipped and their databases
# have whatever they have, and re-deriving that now would be archaeology with
# no user-visible payoff.
#
# `c109g000007a` is DEF278's own subject. It stays on this list permanently —
# the edit is a fact, and `d109h000008b` is the repair that adds the column to
# the one database which will never run that revision again. Removing it from
# here would not undo the edit, it would only make the suite red about
# something already fixed.
#
# `cr221a0b0c0d4` is the same shape and took the same treatment (2026-09-12).
# It was committed in `98e1b36f` creating `ix_edgar_8k_items_ticker_filed`, and
# edited 48 minutes later in `94fc8619` to create `ix_edgar_8k_items_cik_filed`
# instead — items are read through the scan row's CIK so GOOG sees GOOGL's
# filings, and the two share one. The rename is right; making it by editing a
# committed revision is not, and this guard is what caught it. `e221i000009c`
# is the repair: it drops the stale index and creates the CIK one, by
# inspection, so that a fresh database and a database that ran the first form
# both converge. Listed here for the same reason as `c109g000007a` — the edit
# is in git permanently, so no repair can make this assertion pass again, and
# leaving it red would be the suite complaining about something already fixed.
#
# This list is for edits that have a shipped repair or a deliberate baseline.
# It is NOT a way to quiet the guard: add a file here only together with the
# revision that reconciles the databases, and name that revision.
_PRE_GUARD_EDITS = frozenset({
    "8a4ce4f8abc3_notifications_price_alerts.py",
    "a9d1c7e80006_admin_backoffice.py",
    "c109g000007a_cr109_slice4_placement.py",
    "cr221a0b0c0d4_edgar_8k_items.py",  # repaired by e221i000009c
})


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=_REPO_ROOT, capture_output=True, text=True, check=False,
    ).stdout.strip()


def test_no_committed_migration_has_been_edited():
    edited: list[str] = []
    for path in sorted(_VERSIONS.glob("*.py")):
        rel = path.relative_to(_REPO_ROOT).as_posix()
        added = _git("log", "--diff-filter=A", "--format=%H", "--", rel)
        if not added:
            continue  # untracked / brand new in the working tree — nothing to compare
        introduced = added.splitlines()[-1]
        last_touched = _git("log", "-1", "--format=%H", "--", rel)
        if last_touched and introduced != last_touched:
            if path.name in _PRE_GUARD_EDITS:
                continue
            edited.append(f"{path.name} (added {introduced[:8]}, edited {last_touched[:8]})")

    assert not edited, (
        "these migrations were changed after they were committed:\n  "
        + "\n  ".join(edited)
        + "\n\nOn a shared checkout another track can promote from `main` at any "
        "commit, so a revision you believe has never run may already be stamped "
        "on Alpha. Editing it then produces a database that is at head and "
        "missing what the file says it creates, and no `upgrade head` will ever "
        "repair it. Add a NEW revision instead (see d109h000008b, DEF278)."
    )


def test_the_chain_reaches_a_single_head():
    # Two heads means two tracks branched off the same revision, and whichever
    # deploy runs second silently applies only its own half.
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    backend = _REPO_ROOT / "backend"
    cfg = Config(str(backend / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend / "alembic"))
    heads = ScriptDirectory.from_config(cfg).get_heads()
    assert len(heads) == 1, f"expected one head, found {heads}"


def test_the_repair_migration_is_present_and_idempotent():
    # The specific fix, asserted by name so deleting it fails with the reason.
    # Idempotency is load-bearing here rather than tidy: a fresh database runs
    # `c109g000007a` in its current three-column form and already HAS the
    # column, while Alpha ran the two-column form and does not. Both must
    # survive this migration.
    repair = _VERSIONS / "d109h000008b_starts_decided_at_repair.py"
    assert repair.exists(), "DEF278's repair migration is missing"
    src = repair.read_text()
    assert "_has_column" in src, "the repair must check before it adds"
    assert 'down_revision = "c109g000007a"' in src
