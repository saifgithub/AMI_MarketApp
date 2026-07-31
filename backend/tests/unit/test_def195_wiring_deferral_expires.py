"""DEF195 — the signed deferral for the release-time parity gate, as an
EXPIRING structural control rather than a note somebody has to remember.

Context. `scripts/check_release_schema_parity.py` must run at client-release
time against the DEPLOYED backend; only that closes the `0.1.0+61`
deployment-order near-miss (a client in parity with `main` can still be ahead
of what is promoted). Its call sites are `scripts/build_testflight.sh`,
`scripts/build_playstore.sh` and `scripts/publish_playstore.sh` — all three
held by another track's uncommitted CR084-ALPHA edits, which this repo's
governance forbids sweeping into an unrelated commit.

The R65-BATCH1 round-1 audit graded the unwired gate **MAJOR M1** and offered
two exits: wire it, or "a documented deferral Saiful signs". **Saiful signed
off on shipping (2026-07-31).**

So this is that deferral — written as a test, because the auditor's sharpest
observation on the batch was that two unwired deliverables in one round meant
"the class is forming a habit", and a deferral recorded only in prose is how
the habit continues. A signed exception that cannot expire is indistinguishable
from the DEF038/DEF063 "dark for months" failures this project has already been
bitten by twice.

Behaviour:
  - gate wired               → PASS (deferral satisfied; delete this file)
  - not wired, before expiry → PASS (deferral active, as signed)
  - not wired, after expiry  → FAIL (the decision must be revisited, not drift)

Clearing this is not "make the test pass" — it is wiring the gate, at which
point the first branch passes on its own and this file should be deleted.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]

#: Signed by Saiful 2026-07-31 in response to the R65-BATCH1 round-1 audit.
_DEFERRAL_SIGNED = date(2026, 7, 31)

#: One month. Long enough for CR084-ALPHA to land and the wiring to follow it,
#: short enough that an unwired release gate cannot quietly outlive the reason
#: it was deferred. Moving this date is a fresh stakeholder decision, not
#: maintenance — record it beside the original sign-off if it moves.
_DEFERRAL_EXPIRES = date(2026, 8, 31)

_RELEASE_SCRIPTS = (
    "scripts/build_testflight.sh",
    "scripts/build_playstore.sh",
    "scripts/publish_playstore.sh",
)

_GATE = "check_release_schema_parity"


def _scripts_calling_the_gate() -> list[str]:
    hits = []
    for rel in _RELEASE_SCRIPTS:
        p = _REPO_ROOT / rel
        if p.is_file() and _GATE in p.read_text(encoding="utf-8"):
            hits.append(rel)
    return hits


def test_the_release_parity_gate_is_wired_or_its_deferral_is_still_valid():
    wired = _scripts_calling_the_gate()
    if wired:
        # The deferral is satisfied. Nothing to defend any more.
        return

    today = date.today()
    assert today < _DEFERRAL_EXPIRES, (
        "DEF195's signed deferral has EXPIRED.\n"
        "\n"
        f"  Signed:  {_DEFERRAL_SIGNED} (Saiful, answering R65-BATCH1 audit MAJOR M1)\n"
        f"  Expired: {_DEFERRAL_EXPIRES}\n"
        f"  Today:   {today}\n"
        "\n"
        "The release-time schema-parity gate is STILL not called by any of:\n"
        + "".join(f"    {s}\n" for s in _RELEASE_SCRIPTS)
        + "\n"
        "So a client build can still ship ahead of the backend that must serve\n"
        "it — the 0.1.0+61 near-miss, where a settings screen PATCHed seven\n"
        "fields the deployed Mandate schema did not have, every write returned\n"
        "200, and pydantic's extra='ignore' dropped all of them.\n"
        "\n"
        "This is not a test to silence. Do ONE of:\n"
        "  1. Wire the gate (the fix):\n"
        "       scripts/check_release_schema_parity.py --base-url <deployed host>\n"
        "     as a blocking preflight in each script above. This test then\n"
        "     passes on its own and this FILE SHOULD BE DELETED.\n"
        "  2. Get a fresh signed extension and move _DEFERRAL_EXPIRES, recording\n"
        "     the new decision beside the original on the DEF195 row.\n"
        "\n"
        "If CR084-ALPHA's hold on those scripts has cleared, option 1 is now\n"
        "unblocked and is the only correct answer."
    )


def test_the_deferral_window_is_bounded_and_not_retroactively_widened():
    """A deferral whose expiry can drift forward silently is not a deferral.
    Pins the window at the length that was signed, so moving it is a visible,
    deliberate edit to this assertion rather than a one-character change."""
    assert _DEFERRAL_EXPIRES > _DEFERRAL_SIGNED
    assert (_DEFERRAL_EXPIRES - _DEFERRAL_SIGNED).days <= 31, (
        "the signed deferral was one month; a longer window needs a fresh "
        "stakeholder decision, not an edit to this constant"
    )
