"""CR235 — `scripts/promotion/ci_status.py` names GitHub Actions' verdict for the exact
commit being promoted, as a WARNING line `/promote-to-alpha` prints and never blocks on.

Lives in `backend/tests/unit/` on purpose, following `test_cr175_postflight.py`'s own
reasoning: `scripts/` code has no test suite of its own that promotion actually runs, and a
test outside the suite promotion runs at step 1 is a test nobody runs (DEF271).

Every test here feeds canned `gh` JSON via monkeypatching `_run_gh` — no real `gh` call, no
network. `ci_status.py` was also run against the live repo for the real HEAD during CR235's
own verification; these tests pin the parsing/formatting logic so that behaviour doesn't
regress silently.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_SCRIPT = (Path(__file__).resolve().parents[3]
           / "scripts" / "promotion" / "ci_status.py")


def _load():
    spec = importlib.util.spec_from_file_location("ci_status_cr235", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cs = _load()

_SHA = "17e5b967352707dbe1b6ce34ac14aee0eb438279"
_URL = "https://github.com/saifgithub/AMI_MarketApp/actions/runs/36101336499"


def _run(status: str, conclusion: str | None, sha: str = _SHA, run_id: int = 36101336499) -> dict:
    return {
        "status": status,
        "conclusion": conclusion or "",
        "headSha": sha,
        "databaseId": run_id,
        "url": _URL,
        "createdAt": "2026-09-25T10:00:00Z",
    }


def _patch_gh(monkeypatch: pytest.MonkeyPatch, run_list_json: str, jobs_json: str = "") -> list[list[str]]:
    """Stub `_run_gh`: first call (run list) returns `run_list_json`, any later call
    (jobs lookup) returns `jobs_json`. Records every args list it was called with."""
    calls: list[list[str]] = []

    def _fake(args: list[str]) -> str:
        calls.append(args)
        if args[0] == "run":
            return run_list_json
        if args[0] == "api":
            return jobs_json
        raise AssertionError(f"unexpected gh args: {args}")

    monkeypatch.setattr(cs, "_run_gh", _fake)
    return calls


# ── GREEN ────────────────────────────────────────────────────────────────────

def test_green_all_jobs_passed(monkeypatch: pytest.MonkeyPatch) -> None:
    runs = [_run("completed", "success")]
    _patch_gh(monkeypatch, json.dumps(runs))
    line = cs.format_line(_SHA)
    assert line == f"CI: GREEN — all jobs passed ({_URL})"


# ── RED — the state that must be impossible to misread ──────────────────────

def test_red_names_the_failing_jobs_in_capitals(monkeypatch: pytest.MonkeyPatch) -> None:
    runs = [_run("completed", "failure")]
    jobs = "\n".join(json.dumps(j) for j in [
        {"name": "Flutter (analyze + test)", "conclusion": "success"},
        {"name": "Backend unit tests", "conclusion": "failure"},
        {"name": "UAT harness (offline guards)", "conclusion": "cancelled"},
    ])
    _patch_gh(monkeypatch, json.dumps(runs), jobs)
    line = cs.format_line(_SHA)
    assert line.startswith("CI: RED")
    assert "Backend unit tests" in line
    assert "UAT harness (offline guards)" in line
    assert "Flutter (analyze + test)" not in line
    assert _URL in line


def test_red_falls_back_to_conclusion_when_jobs_lookup_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runs = [_run("completed", "failure")]
    calls: list[list[str]] = []

    def _fake(args: list[str]) -> str:
        calls.append(args)
        if args[0] == "run":
            return json.dumps(runs)
        raise cs.CIUnavailable("simulated jobs-api failure")

    monkeypatch.setattr(cs, "_run_gh", _fake)
    line = cs.format_line(_SHA)
    assert line.startswith("CI: RED")
    assert "failure" in line


# ── PENDING ──────────────────────────────────────────────────────────────────

def test_pending_while_a_job_is_still_running(monkeypatch: pytest.MonkeyPatch) -> None:
    runs = [_run("in_progress", None)]
    _patch_gh(monkeypatch, json.dumps(runs))
    line = cs.format_line(_SHA)
    assert line == f"CI: PENDING — still running ({_URL})"


# ── CANCELLED ────────────────────────────────────────────────────────────────

def test_cancelled_superseded_by_a_later_push(monkeypatch: pytest.MonkeyPatch) -> None:
    runs = [_run("completed", "cancelled")]
    _patch_gh(monkeypatch, json.dumps(runs))
    line = cs.format_line(_SHA)
    assert line == f"CI: CANCELLED — superseded by a later push ({_URL})"


# ── NOT RUN ──────────────────────────────────────────────────────────────────

def test_not_run_when_no_run_matches_this_sha(monkeypatch: pytest.MonkeyPatch) -> None:
    other_sha = "0" * 40
    runs = [_run("completed", "success", sha=other_sha)]
    _patch_gh(monkeypatch, json.dumps(runs))
    line = cs.format_line(_SHA)
    assert line.startswith("CI: NOT RUN")
    assert _SHA[:12] in line


def test_not_run_on_an_empty_run_list(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_gh(monkeypatch, json.dumps([]))
    line = cs.format_line(_SHA)
    assert line.startswith("CI: NOT RUN")


# ── UNAVAILABLE ──────────────────────────────────────────────────────────────

def test_unavailable_when_gh_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(args: list[str]) -> str:
        raise cs.CIUnavailable("gh CLI not found on PATH")

    monkeypatch.setattr(cs, "_run_gh", _raise)
    line = cs.format_line(_SHA)
    assert line == "CI: UNAVAILABLE — gh CLI not found on PATH"


def test_unavailable_on_malformed_json(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_gh(monkeypatch, "not json")
    line = cs.format_line(_SHA)
    assert line.startswith("CI: UNAVAILABLE")


# ── picks the newest of several runs for the same sha (re-runs) ─────────────

def test_picks_the_newest_run_when_several_match_the_sha(monkeypatch: pytest.MonkeyPatch) -> None:
    older = _run("completed", "failure", run_id=1)
    older["createdAt"] = "2026-09-25T08:00:00Z"
    newer = _run("completed", "success", run_id=2)
    newer["createdAt"] = "2026-09-25T09:00:00Z"
    _patch_gh(monkeypatch, json.dumps([older, newer]))
    line = cs.format_line(_SHA)
    assert line.startswith("CI: GREEN")


# ── the caller-facing contract: main() always exits 0 on a successful lookup ─

def test_main_exits_zero_even_on_red(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    runs = [_run("completed", "failure")]
    jobs = json.dumps({"name": "Backend unit tests", "conclusion": "failure"})
    _patch_gh(monkeypatch, json.dumps(runs), jobs)
    monkeypatch.setattr("sys.argv", ["ci_status.py", "--sha", _SHA])
    rc = cs.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert out.startswith("CI: RED")


def test_run_list_is_filtered_to_the_tests_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch_gh(monkeypatch, json.dumps([_run("completed", "success")]))
    cs.format_line(_SHA)
    run_list_call = calls[0]
    assert "--workflow" in run_list_call
    assert run_list_call[run_list_call.index("--workflow") + 1] == "tests.yml"
    assert "--commit" in run_list_call
    assert run_list_call[run_list_call.index("--commit") + 1] == _SHA
