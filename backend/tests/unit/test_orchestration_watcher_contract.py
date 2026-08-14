"""Pins the two orchestration watchers' OUTSIDE contract: exit codes, and whether a
dead watcher is distinguishable from an empty queue.

Both defects these tests pin were invisible precisely because nothing asserted on the
watchers from outside. `watcher.sh state` exited 1 on every healthy board for months
(DEF132) and no caller noticed; a background watcher died and the queue stopped being
served for ~10h while every board still read healthy (DEF135). Fixing the two lines
without pinning them would leave the same silence behind.

Mac-safe: shells out to POSIX `sh`, touches only `tmp_path`, starts no backend and no DB.
"""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_WATCHER = _REPO_ROOT / "orchestration" / "audit" / "watcher.sh"
_DISPATCH = _REPO_ROOT / "orchestration" / "dispatch" / "dispatch.sh"


def _run(script: Path, *args: str, env_extra: dict[str, str] | None = None):
    env = {**os.environ, **(env_extra or {})}
    return subprocess.run(
        ["sh", str(script), *args], capture_output=True, text=True, env=env, timeout=60
    )


def _populated_audit_dir(root: Path) -> Path:
    cr = root / "cr"
    cr.mkdir(parents=True, exist_ok=True)
    (cr / "T1.architect.md").write_text("SUBMITTED: round 1\n")
    (cr / "T1.auditor.md").write_text("**VERDICT: COMPLETE (round 1)**\n")
    return cr


def _lane_dir_for(cr: Path) -> Path:
    lanes = cr.parent / "lanes"
    lanes.mkdir(parents=True, exist_ok=True)
    (lanes / "T1.assign.md").write_text(
        "ASSIGNED: coder.x round 1\nGATE: independent\nDISPATCH: ACCEPTED\n"
    )
    return lanes


# --- DEF132: a successful board read must exit 0 --------------------------------------


@pytest.mark.parametrize("populated", [True, False], ids=["populated", "empty"])
def test_watcher_state_exits_zero_on_a_successful_read(tmp_path: Path, populated: bool):
    """`print_state` used to end on a bare `[ "$n" -eq 0 ] && …`, whose status became the
    script's — so a correct table over a POPULATED board exited 1, and the only exit 0 was
    the empty board. Both directions are pinned because fixing only the populated case
    would let the inverse regress unseen."""
    cr = _populated_audit_dir(tmp_path) if populated else (tmp_path / "cr")
    cr.mkdir(parents=True, exist_ok=True)

    r = _run(_WATCHER, "state", env_extra={"HANDSHAKE_CR_DIR": str(cr)})

    assert r.returncode == 0, (
        f"watcher.sh state exited {r.returncode} on a successful read "
        f"({'populated' if populated else 'empty'} board). Its own header promises "
        f"'0 work found (or table printed)'.\nstdout:\n{r.stdout}\nstderr:\n{r.stderr}"
    )


def test_both_watchers_agree_on_a_successful_state_read(tmp_path: Path):
    """The sibling scripts must not disagree about what success means — that asymmetry is
    how DEF132 survived: dispatch.sh already returned 0, so a side-by-side run was the
    only thing that would have shown it."""
    cr = _populated_audit_dir(tmp_path)
    lanes = _lane_dir_for(cr)

    a = _run(_WATCHER, "state", env_extra={"HANDSHAKE_CR_DIR": str(cr)})
    d = _run(
        _DISPATCH,
        "state",
        env_extra={"DISPATCH_LANE_DIR": str(lanes), "DISPATCH_AUDIT_DIR": str(cr)},
    )

    assert (a.returncode, d.returncode) == (0, 0), (
        f"watcher.sh state -> {a.returncode}, dispatch.sh state -> {d.returncode}; "
        "both must be 0 on a populated board."
    )


def test_bad_usage_still_exits_two(tmp_path: Path):
    """The documented non-zero codes must survive the fix: 2 = bad usage."""
    cr = _populated_audit_dir(tmp_path)
    r = _run(_WATCHER, "not-a-mode", env_extra={"HANDSHAKE_CR_DIR": str(cr)})
    assert r.returncode == 2, f"expected exit 2 for bad usage, got {r.returncode}"


# --- DEF135: a dead watcher must be distinguishable from an empty queue ---------------


def _stamp(cr: Path, mode: str, age_seconds: int, interval: int = 30) -> Path:
    hb = cr / f".watch-{mode}.hb"
    hb.write_text(f"{int(time.time()) - age_seconds} {interval}\n")
    return hb


def test_no_heartbeat_is_not_an_alarm(tmp_path: Path):
    """Absence must stay silent. An auditor spawned per item is told NOT to watch, so
    no-heartbeat is the normal state under that model; alarming on it would keep this
    permanently red and desensitise the one signal it carries."""
    cr = _populated_audit_dir(tmp_path)
    r = _run(_WATCHER, "state", env_extra={"HANDSHAKE_CR_DIR": str(cr)})
    # Subject is the alarm, not the exit code — the exit code is pinned above, and asserting it
    # here too would make a DEF132 regression fail a DEF135 test and mis-attribute the cause.
    assert "NO AUDITOR WATCHER" not in r.stdout, r.stdout


def test_fresh_heartbeat_is_not_an_alarm(tmp_path: Path):
    cr = _populated_audit_dir(tmp_path)
    _stamp(cr, "auditor", age_seconds=5, interval=30)
    r = _run(_WATCHER, "state", env_extra={"HANDSHAKE_CR_DIR": str(cr)})
    assert "NO AUDITOR WATCHER" not in r.stdout, r.stdout


def test_stale_heartbeat_is_loud_on_the_board(tmp_path: Path):
    """The failure DEF135 records: the watcher stopped, the table stayed correct, and
    nothing anywhere said the queue was unserved."""
    cr = _populated_audit_dir(tmp_path)
    _stamp(cr, "auditor", age_seconds=3600, interval=30)

    r = _run(_WATCHER, "state", env_extra={"HANDSHAKE_CR_DIR": str(cr)})

    assert "NO AUDITOR WATCHER" in r.stdout, (
        "a watcher that died left a stale heartbeat and the board said nothing — "
        f"'nobody is looking' is again indistinguishable from 'nothing is waiting'.\n{r.stdout}"
    )
    assert "T1" in r.stdout, "the lane table must still print; liveness is additive"
    assert r.returncode == 0, "state is a report — the loud line must not invert its exit code"


def test_stale_heartbeat_turns_the_architect_inbox_red(tmp_path: Path):
    """`inbox` is the Architect's per-work-unit gate, so this is where a dead watcher has
    to land: a clean inbox otherwise certifies a queue nobody is serving.

    **It lands as exit 2, not exit 1 (DEF277).** Both are non-zero, so every
    `if ! dispatch.sh inbox` caller — the Architect's own gate included — still
    refuses, and the certification this test exists to prevent is still
    prevented. What changed is that a caller which cares *why* can now tell the
    difference: `/promote-to-alpha` aborts on 1 (a verdict may already have
    flagged your code) and warns on 2 (nobody is serving the queue, which says
    nothing about the code being shipped). `test_a_returned_verdict_outranks_a_
    dead_watcher` below pins the precedence that keeps the AT:R66 guarantee.
    """
    cr = _populated_audit_dir(tmp_path)
    lanes = _lane_dir_for(cr)
    env = {"DISPATCH_LANE_DIR": str(lanes), "DISPATCH_AUDIT_DIR": str(cr)}

    before = _run(_DISPATCH, "inbox", env_extra=env)
    assert before.returncode == 0, f"fixture must start with a clean inbox:\n{before.stdout}"

    _stamp(cr, "auditor", age_seconds=3600, interval=30)
    after = _run(_DISPATCH, "inbox", env_extra=env)

    # DEF277 split the non-zero codes: 1 = a verdict awaits integration or a
    # submission of yours never reached the auditor; 2 = no watcher is serving
    # the queue. The claim this test makes — "a dead watcher must fail the
    # Architect's per-work-unit gate" — is unchanged and still enforced, since
    # every `if ! dispatch.sh inbox` caller refuses on both. Only the promotion
    # gate distinguishes, because an idle audit fleet says nothing about the
    # code being shipped.
    #
    # Asserted as the SPECIFIC code rather than relaxed to `!= 0`: loosening a
    # guard to accommodate a change is the DEF243 mistake, and pinning 2 here
    # makes this test encode the split instead of tolerating it.
    assert after.returncode == 2, (
        f"a dead watcher must fail the gate, with the code that means "
        f"'nobody is serving the queue':\n{after.stdout}")
    assert "NO AUDITOR WATCHER" in after.stdout, after.stdout


def test_a_returned_verdict_outranks_a_dead_watcher(tmp_path: Path):
    """DEF277's load-bearing case. The split exists to stop an idle fleet
    blocking a promotion — never to let a real verdict through. With BOTH
    conditions true, `hot` must win and the gate must return 1, because that is
    the code `/promote-to-alpha` aborts on."""
    cr = _populated_audit_dir(tmp_path)
    lanes = _lane_dir_for(cr)
    env = {"DISPATCH_LANE_DIR": str(lanes), "DISPATCH_AUDIT_DIR": str(cr)}

    (cr / "T9.architect.md").write_text("SUBMITTED: round 1\n")
    (cr / "T9.auditor.md").write_text("VERDICT: AWAITING_FIXES (round 1)\n")
    _stamp(cr, "auditor", age_seconds=3600, interval=30)

    r = _run(_DISPATCH, "inbox", env_extra=env)
    assert r.returncode == 1, (
        "a verdict awaiting integration must outrank a dead watcher — otherwise "
        f"the AT:R66 guarantee is weakened by DEF277's split:\n{r.stdout}")


def test_killed_watcher_leaves_the_stamp_that_makes_it_visible(tmp_path: Path):
    """The whole point, end to end: START a real watcher, KILL it the way a process
    teardown would, and assert the board can tell. A watcher that cleaned up on SIGTERM
    would erase exactly the evidence this exists to preserve, which is why TERM is not
    trapped."""
    cr = tmp_path / "cr"
    cr.mkdir(parents=True, exist_ok=True)  # empty: the watcher must block, not find work
    hb = cr / ".watch-auditor.hb"

    proc = subprocess.Popen(
        ["sh", str(_WATCHER), "auditor", "-i", "1", "-t", "120"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env={**os.environ, "HANDSHAKE_CR_DIR": str(cr)},
    )
    try:
        deadline = time.time() + 15
        while time.time() < deadline and not hb.exists():
            time.sleep(0.2)
        assert hb.exists(), "a blocking watcher must stamp a heartbeat while it polls"

        proc.send_signal(signal.SIGKILL)
        proc.wait(timeout=10)
    finally:
        if proc.poll() is None:  # pragma: no cover - only on an unexpected survival
            proc.kill()
            proc.wait(timeout=10)

    assert hb.exists(), (
        "the killed watcher's heartbeat is gone, so its death is now indistinguishable "
        "from a watcher that exited cleanly — the DEF135 silence, restored."
    )

    # Age the surviving stamp rather than sleeping past the staleness limit.
    ts, interval = hb.read_text().split()
    hb.write_text(f"{int(ts) - 3600} {interval}\n")

    r = _run(_WATCHER, "state", env_extra={"HANDSHAKE_CR_DIR": str(cr)})
    assert "NO AUDITOR WATCHER" in r.stdout, (
        f"a killed watcher produced no signal on the board:\n{r.stdout}"
    )


# --- DEF300: a lane with nothing submitted is not work -------------------------------


def test_an_unsubmitted_lane_is_draft_not_awaiting_audit(tmp_path: Path):
    """The DEF300 case, reproduced exactly: an architect file authored ahead of its
    evidence, with no `SUBMITTED:` line, and no auditor file yet.

    `R69-FE1.architect.md` was written this way on purpose — its own header said creating
    that line before the measurement was real *"is the one thing this lane must not do"* —
    and the watcher called it AWAITING_AUDIT anyway.
    """
    cr = tmp_path / "cr"
    cr.mkdir(parents=True, exist_ok=True)
    (cr / "T3.architect.md").write_text(
        "# lane notes, measurement still running — deliberately no SUBMITTED line\n"
    )

    r = _run(_WATCHER, "state", env_extra={"HANDSHAKE_CR_DIR": str(cr)})

    row = [ln for ln in r.stdout.splitlines() if ln.startswith("T3")]
    assert row, f"the lane must still appear on the board:\n{r.stdout}"
    assert "AWAITING_AUDIT" not in row[0], (
        "a lane with zero submissions was called AWAITING_AUDIT, so an architect file "
        f"authored ahead of its evidence wakes the auditor for nothing:\n{row[0]}"
    )
    assert "DRAFT" in row[0], (
        f"the state must NAME the real situation, not merely stop lying about it:\n{row[0]}"
    )


def test_an_unsubmitted_lane_with_an_opened_auditor_file_is_also_draft(tmp_path: Path):
    """The second door into the same state, and the one the false signal actually
    manufactures: the auditor is woken, opens a file, finds nothing committed, and writes
    no verdict. Guarding only the no-auditor-file arm would leave the lane re-reporting
    itself as work forever — which is the loop the R69-FE1 auditor had to babysit."""
    cr = tmp_path / "cr"
    cr.mkdir(parents=True, exist_ok=True)
    (cr / "T4.architect.md").write_text("notes, no SUBMITTED line\n")
    (cr / "T4.auditor.md").write_text("opened, nothing to audit — no VERDICT line\n")

    r = _run(_WATCHER, "state", env_extra={"HANDSHAKE_CR_DIR": str(cr)})

    row = [ln for ln in r.stdout.splitlines() if ln.startswith("T4")]
    assert row, f"the lane must still appear on the board:\n{r.stdout}"
    assert "AWAITING_AUDIT" not in row[0] and "DRAFT" in row[0], row[0]


def test_the_auditor_watcher_does_not_wake_for_an_unsubmitted_lane(tmp_path: Path):
    """The behavioural half — the state string is only interesting because `count_state`
    reads it. A watcher told to block until there is work must still be blocking, so this
    asserts the timeout exit (3, no work found) rather than the table's contents."""
    cr = tmp_path / "cr"
    cr.mkdir(parents=True, exist_ok=True)
    (cr / "T5.architect.md").write_text("authored, not submitted\n")

    r = _run(_WATCHER, "auditor", "-i", "1", "-t", "3", env_extra={"HANDSHAKE_CR_DIR": str(cr)})

    assert r.returncode == 3, (
        "the auditor watcher woke for a lane that has submitted nothing — exit 0 means it "
        f"found work:\n{r.stdout}"
    )


def test_a_real_submission_still_wakes_the_auditor(tmp_path: Path):
    """Non-vacuity, and the regression that matters most: the guard must not have bought
    quiet by breaking the signal. Same fixture as above plus the one line that makes it a
    submission."""
    cr = tmp_path / "cr"
    cr.mkdir(parents=True, exist_ok=True)
    (cr / "T6.architect.md").write_text("SUBMITTED: round 1\n")

    r = _run(_WATCHER, "auditor", "-i", "1", "-t", "10", env_extra={"HANDSHAKE_CR_DIR": str(cr)})

    assert r.returncode == 0, (
        f"a genuinely submitted lane no longer wakes the auditor:\n{r.stdout}"
    )
    assert "AWAITING_AUDIT" in r.stdout, r.stdout


def test_clean_exit_clears_the_stamp(tmp_path: Path):
    """A watcher that finds work and exits 0 must NOT leave a stamp behind — otherwise the
    normal path manufactures false alarms and the signal dies of noise within a day."""
    cr = _populated_audit_dir(tmp_path)
    (cr / "T2.architect.md").write_text("SUBMITTED: round 1\n")  # AWAITING_AUDIT: found work

    r = _run(_WATCHER, "auditor", "-i", "1", "-t", "10", env_extra={"HANDSHAKE_CR_DIR": str(cr)})

    assert r.returncode == 0, f"expected the watcher to find work and exit 0:\n{r.stdout}"
    assert not (cr / ".watch-auditor.hb").exists(), (
        "a clean exit left its heartbeat behind; every later board read would cry wolf."
    )


def test_timeout_exit_clears_the_stamp(tmp_path: Path):
    """Same for the other clean exit: -t giving up (exit 3) is a deliberate stop."""
    cr = tmp_path / "cr"
    cr.mkdir(parents=True, exist_ok=True)

    r = _run(_WATCHER, "auditor", "-i", "1", "-t", "2", env_extra={"HANDSHAKE_CR_DIR": str(cr)})

    assert r.returncode == 3, f"expected exit 3 (timed out with no work), got {r.returncode}"
    assert not (cr / ".watch-auditor.hb").exists(), (
        "a -t timeout left its heartbeat behind; a bounded watcher would alarm every time."
    )
