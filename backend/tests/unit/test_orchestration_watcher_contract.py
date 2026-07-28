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
    to land: a clean inbox otherwise certifies a queue nobody is serving."""
    cr = _populated_audit_dir(tmp_path)
    lanes = _lane_dir_for(cr)
    env = {"DISPATCH_LANE_DIR": str(lanes), "DISPATCH_AUDIT_DIR": str(cr)}

    before = _run(_DISPATCH, "inbox", env_extra=env)
    assert before.returncode == 0, f"fixture must start with a clean inbox:\n{before.stdout}"

    _stamp(cr, "auditor", age_seconds=3600, interval=30)
    after = _run(_DISPATCH, "inbox", env_extra=env)

    assert after.returncode == 1, f"a dead watcher must fail the gate:\n{after.stdout}"
    assert "NO AUDITOR WATCHER" in after.stdout, after.stdout


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
