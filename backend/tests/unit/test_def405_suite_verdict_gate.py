"""DEF405 — a gate's exit code does not survive the wrapper that ran it.

Third instance of the DEF326 shape. The suite gate ends in one VERDICT line and
one exit code (DEF326 made it so). On 2026-09-11 the gate was run as
`preflight_suite.sh | tail -25` inside a background task; the task reported
tail's exit 0, the operator read "completed (exit code 0)", and
alpha-2026-09-11-1 shipped on a suite that had printed `VERDICT: FAIL`.

The fix is a record the wrapper cannot swallow: the gate writes its verdict,
the commit it measured (captured before the run, because HEAD moved during
this one), and the target it ran, to `.deliveryos/suite_verdict.json`; and
`postflight.py` — whose exit code the operator did read — fails the promotion
when that record is missing, stale, partial, for another commit, or not PASS.

Two halves, both pinned here: the shell script records at every exit, and the
postflight check refuses every non-green state.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_POSTFLIGHT = _ROOT / "scripts" / "promotion" / "postflight.py"
_GATE = _ROOT / "scripts" / "promotion" / "preflight_suite.sh"


@pytest.fixture(scope="module")
def postflight():
    spec = importlib.util.spec_from_file_location("postflight_def405", _POSTFLIGHT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_SHA = "445f6a438218322806ff4da15f8c399047cb6ccb"
_NOW = datetime(2026, 9, 11, 1, 0, tzinfo=timezone.utc)


def _record(tmp_path: Path, **over) -> Path:
    rec = {"sha": _SHA, "verdict": "PASS", "target": "backend/tests/unit/",
           "at": _NOW.isoformat().replace("+00:00", "Z"), "passed": 6456, "failed": 0, "errors": 0}
    rec.update(over)
    path = tmp_path / "suite_verdict.json"
    path.write_text(json.dumps(rec))
    return path


def _check(postflight, path: Path, sha: str = _SHA) -> list[str]:
    return postflight.check_suite_verdict(path, sha, now=_NOW.timestamp() + 600)


# ── the postflight half ─────────────────────────────────────────────────────


def test_a_fresh_full_pass_on_the_promoted_commit_is_clean(postflight, tmp_path) -> None:
    assert _check(postflight, _record(tmp_path)) == []
    assert _check(postflight, _record(tmp_path), sha=_SHA[:12]) == []


def test_the_night_it_happened_fails_twice_over(postflight, tmp_path) -> None:
    """The gate said FAIL on 0aa2ac03; 445f6a43 was promoted."""
    path = _record(tmp_path, sha="0aa2ac03" + "0" * 32, verdict="FAIL", failed=1, passed=6455)
    problems = _check(postflight, path)
    assert any("recorded FAIL" in p and "failed=1" in p for p in problems)
    assert any("ran on 0aa2ac030000" in p and "445f6a438218" in p for p in problems)


def test_a_missing_record_is_a_failure_not_an_unknown(postflight, tmp_path) -> None:
    problems = postflight.check_suite_verdict(tmp_path / "absent.json", _SHA)
    assert len(problems) == 1 and "did not run" in problems[0]


@pytest.mark.parametrize("over,needle", [
    ({"verdict": "COULD_NOT_RUN"}, "recorded COULD_NOT_RUN"),
    ({"verdict": ""}, "recorded nothing"),
    ({"target": "backend/tests/unit/test_p30_registers_name_things_that_exist.py"}, "partial run"),
    ({"sha": "deadbeef" + "0" * 32}, "not the shipped tree"),
    ({"at": "2026-09-10T18:00:00Z"}, "old"),
    ({"at": "not-a-date"}, "old"),
])
def test_every_non_green_state_is_named(postflight, tmp_path, over, needle) -> None:
    assert any(needle in p for p in _check(postflight, _record(tmp_path, **over)))


def test_a_malformed_record_is_treated_as_no_gate(postflight, tmp_path) -> None:
    path = tmp_path / "suite_verdict.json"
    path.write_text("{not json")
    problems = postflight.check_suite_verdict(path, _SHA)
    assert len(problems) == 1 and "unreadable" in problems[0]


def test_the_suite_check_runs_first_in_the_driver(postflight) -> None:
    src = _POSTFLIGHT.read_text()
    order = [m.group(1) for m in re.finditer(r'\("(suite|identity|tree|readiness|config|market)", lambda', src)]
    assert order[0] == "suite" and len(order) == 6, order
    assert "--suite-verdict" in src


# ── the shell half ──────────────────────────────────────────────────────────


def test_the_gate_records_a_verdict_before_every_exit() -> None:
    lines = _GATE.read_text().splitlines()
    fn = next(i for i, line in enumerate(lines) if line.startswith("record_verdict()"))
    exits = [i for i, line in enumerate(lines[fn:], fn) if re.match(r"\s*exit \d", line)]
    assert len(exits) >= 5, exits
    for i in exits:
        window = "\n".join(lines[max(fn, i - 6):i])
        assert re.search(r"record_verdict (PASS|FAIL|COULD_NOT_RUN)", window), (
            f"line {i + 1}: `{lines[i].strip()}` exits without recording a verdict — "
            "a wrapper that swallows this exit code leaves no trace (DEF405)")
    assert sum("record_verdict PASS" in line for line in lines) == 1


def test_the_gate_captures_the_commit_before_the_suite_runs() -> None:
    src = _GATE.read_text()
    sha_at = src.index('GATE_SHA="$(git')
    run_at = src.index('"${PYTEST[@]}" "$TARGET"')
    assert sha_at < run_at, "HEAD can move during the run; the record must name what was tested"
    assert '"$GATE_SHA" "$1" "$TARGET"' in src


def test_the_record_lives_where_git_ignores_it() -> None:
    """Asked of git, not read from its ignore file: naming that file here would make the
    CR216 selector attribute every same-named file in the repo to this test (audit
    CR221-SLOT4 MAJOR-2 — it did, for `mobile/ios/`)."""
    rc = subprocess.run(["git", "check-ignore", "-q", ".deliveryos/suite_verdict.json"],
                        cwd=_ROOT, check=False).returncode
    assert rc == 0, "the verdict record must be ignored by git, or the gate dirties the tree it measures"
    assert '.deliveryos/suite_verdict.json' in _GATE.read_text()
