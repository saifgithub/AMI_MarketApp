"""DEF141 guard — auditor regression pins must live where the suite collects them.

Five auditor-authored pins sat in `orchestration/audit/regression/` for months. That
directory is outside `testpaths` and outside the `pytest backend/tests/unit/ -q`
invocation this project actually runs, so none of them had executed since the hour it
was written. A test file that is never collected cannot fail, so the failure mode was
total silence while the audit trail read as though each gap was closed.

Pins are the highest-signal tests in the repo — a pin exists precisely because an
auditor found a hole the lane's own guard missed. Those were the ones not running.

The fix was to move them onto the collection path. This guard keeps them there:

  1. the quarantine directory stays empty of test files — a pin dropped there is
     invisible, so dropping one is a build failure with instructions attached;
  2. the migrated pins still exist — a "cleanup" that deletes them fails here.

Rule 2 is the non-vacuity leg. Without it rule 1 passes trivially on a tree with no
pins at all, which is the same silence in a different costume.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
QUARANTINE = REPO_ROOT / "orchestration" / "audit" / "regression"
UNIT_TESTS = REPO_ROOT / "backend" / "tests" / "unit"

MIGRATED_PINS = (
    "test_cr054_guard_capstone_floor_pin.py",
    "test_cr054_w0b_track_label_parity_pin.py",
    "test_cr077_static_head_pin.py",
    "test_def127_sse_frame_literal_pin.py",
    "test_streak_milestone_cap_pin.py",
)


def test_no_pin_is_stranded_off_the_collection_path():
    if not QUARANTINE.exists():
        return
    stranded = sorted(p.name for p in QUARANTINE.glob("test_*.py"))
    assert not stranded, (
        f"{len(stranded)} auditor pin(s) sit in {QUARANTINE.relative_to(REPO_ROOT)}, "
        f"which pytest never collects — they would protect nothing: {stranded}. "
        "Move the file into backend/tests/unit/ and add it to MIGRATED_PINS in this "
        "guard. A pin's whole value is that it runs on every suite run."
    )


def test_the_migrated_pins_still_exist():
    missing = [name for name in MIGRATED_PINS if not (UNIT_TESTS / name).is_file()]
    assert not missing, (
        f"auditor pin(s) deleted from the collection path: {missing}. Each was written "
        "because an auditor found a gap the lane's own guard missed. If one is genuinely "
        "obsolete, remove it from MIGRATED_PINS in the same commit and say why."
    )
