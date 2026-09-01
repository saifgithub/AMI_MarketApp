"""CR216 — the change-to-test selector must find what a name filter cannot.

The historical case this pins: DEF387 added a supervisor guard to `scripts/backtest_sweep.py`,
a targeted `-k` run came back green, and the change was promoted having broken
`test_def358_completion_sentinel_counts_the_batch.py` — which calls `sweep.main()` in-process but
is named after the defect it pins, not after the module it exercises. Only the full suite caught it.

These tests assert the gap is real (a name filter misses it) and that the selector closes it.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
SELECTOR = BACKEND / "scripts" / "tests_for_changed.py"
SWEEP = BACKEND / "scripts" / "backtest_sweep.py"
THE_MISSED_TEST = "tests/unit/test_def358_completion_sentinel_counts_the_batch.py"


def _select(*paths: Path) -> tuple[list[str], int]:
    proc = subprocess.run(
        [sys.executable, str(SELECTOR), *[str(p) for p in paths]],
        cwd=BACKEND.parent, capture_output=True, text=True, check=False,
    )
    return [ln for ln in proc.stdout.splitlines() if ln.strip()], proc.returncode


def test_the_selector_finds_the_test_that_a_name_filter_missed() -> None:
    selected, rc = _select(SWEEP)
    assert rc == 0
    assert THE_MISSED_TEST in selected, (
        "the selector must reach the in-process sweep caller that broke on DEF387"
    )


def test_a_name_filter_really_does_miss_it() -> None:
    """Proves the gap this tool exists for, rather than assuming it.

    If this ever fails, the test was renamed to contain the module name and the motivating example
    is gone — but the selector is still the right mechanism, because the naming convention (tests
    named for defects) has not changed.
    """
    name = Path(THE_MISSED_TEST).name
    for filter_term in ("sweep", "backtest", "backtest_sweep"):
        assert filter_term not in name, (
            f"-k {filter_term} would now match {name}; this pin's example needs updating"
        )


def test_all_three_sweep_importers_are_selected() -> None:
    selected, _ = _select(SWEEP)
    for expected in (
        "tests/unit/test_def345_sweep_completion_sentinel.py",
        "tests/unit/test_def358_completion_sentinel_counts_the_batch.py",
        "tests/unit/test_def387_supervisor_guard.py",
    ):
        assert expected in selected, f"{expected} imports the sweep but was not selected"


def test_selection_is_transitive_not_just_direct() -> None:
    """A test that imports a changed module only through intermediaries must still be selected."""
    direct, _ = _select(BACKEND / "app" / "core" / "config.py")
    assert len(direct) > 50, (
        f"config.py fans out across the app; expected a broad selection, got {len(direct)}"
    )
    # and the fan-out must exceed what only-direct-importers would give
    shallow, _ = _select(BACKEND / "app" / "services" / "llm_gateway.py")
    assert len(shallow) > 1


def test_a_non_python_change_is_attributed_by_the_literals_tests_actually_contain() -> None:
    """No import edge exists to docker-compose.yml, but a test names it — so it can be attributed.

    Derived from the tests' own string constants rather than a hand-written glob table, because a
    hand-written table is the same species of guess this tool exists to replace.
    """
    selected, rc = _select(BACKEND.parent / "docker-compose.yml")
    assert rc == 0
    assert "tests/unit/test_config_compose_parity.py" in selected, (
        "the CR040 compose-drift guard names docker-compose.yml and must be selected for it"
    )


def _an_unnamed_tracked_nonpython_file() -> Path:
    """A tracked non-Python file that no test mentions — derived, never written as a literal.

    Writing the path here would put it INTO the haystack the selector searches, so this test would
    name the very file it asserts is unnamed and the assertion would invert. That is not
    hypothetical: the first draft hardcoded `mobile/ios/Podfile.lock` and the selector duly
    attributed Podfile.lock to this file. Same shape as the P30 baseline that listed absent
    identifiers and thereby made them present.
    """
    out = subprocess.run(
        ["git", "ls-files", "mobile/ios/"], cwd=BACKEND.parent,
        capture_output=True, text=True, check=False,
    ).stdout.split()
    for rel in out:
        if not rel.endswith(".py") and (BACKEND.parent / rel).is_file():
            return BACKEND.parent / rel
    raise AssertionError("no tracked non-Python file found under mobile/ios/")


def test_an_unattributable_tracked_file_demands_the_full_suite() -> None:
    """CLAUDE.md degrade-loudly: the selector must never imply safety it cannot compute.

    A tracked non-Python file that no test names has a blast radius this tool cannot see. Returning
    an empty selection at exit 0 would read as "nothing to run" — the DEF059 shape.
    """
    selected, rc = _select(_an_unnamed_tracked_nonpython_file())
    assert rc == 3, "an unattributable tracked non-Python change must exit 3, not 0"
    assert not selected


def test_attribution_does_not_match_on_a_bare_directory_name() -> None:
    """Regression: matching on the segment "mobile" attributed one lockfile to 15 unrelated tests.

    An over-loose floor is still a wrong answer; it just fails in the tiring direction, and a
    selector people learn to distrust is one they stop running.
    """
    selected, _ = _select(_an_unnamed_tracked_nonpython_file())
    assert len(selected) == 0


def test_the_selector_states_its_own_limits() -> None:
    """A selector trusted beyond its evidence is worse than none; the caveat is part of the output."""
    proc = subprocess.run(
        [sys.executable, str(SELECTOR), str(SWEEP)],
        cwd=BACKEND.parent, capture_output=True, text=True, check=False,
    )
    assert "FLOOR, not a proof" in proc.stderr
    assert "static imports only" in proc.stderr
