"""DEF387 — a sweep must refuse to run unsupervised.

Second occurrence of DEF345's silent-exec-death class. Both times a multi-hour
sweep launched outside `_supervise_*.sh` died with no traceback, no non-zero
exit and no final log line, and sat undetected for ~2h50m. Both times the
written guard existed: `RETEST_RECIPE.md` says "Always under the supervisor" in
bold. Prose lost, twice, to a plausible-sounding rationalisation at launch time.

House rule (CLAUDE.md): a register entry without an enforcing check is not done.
This is that check.
"""

from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.backtest_sweep import SUPERVISOR_ENV, _require_supervisor


def _args(**kw) -> Namespace:
    base = {"plan_only": False, "no_supervisor": False}
    base.update(kw)
    return Namespace(**base)


def test_a_bare_launch_is_refused(monkeypatch):
    monkeypatch.delenv(SUPERVISOR_ENV, raising=False)
    with pytest.raises(SystemExit) as e:
        _require_supervisor(_args())
    assert "REFUSING" in str(e.value)


def test_the_refusal_names_the_way_out(monkeypatch):
    """A guard that blocks without saying what to run instead gets worked around."""
    monkeypatch.delenv(SUPERVISOR_ENV, raising=False)
    with pytest.raises(SystemExit) as e:
        _require_supervisor(_args())
    msg = str(e.value)
    assert "setsid" in msg
    assert SUPERVISOR_ENV in msg
    assert "--no-supervisor" in msg


def test_a_supervised_launch_is_allowed(monkeypatch):
    monkeypatch.setenv(SUPERVISOR_ENV, "1")
    _require_supervisor(_args())


def test_plan_only_is_exempt(monkeypatch):
    """No network, no hours at stake — nothing for a supervisor to supervise."""
    monkeypatch.delenv(SUPERVISOR_ENV, raising=False)
    _require_supervisor(_args(plan_only=True))


def test_the_escape_hatch_works_but_must_be_explicit(monkeypatch):
    monkeypatch.delenv(SUPERVISOR_ENV, raising=False)
    _require_supervisor(_args(no_supervisor=True))


def test_an_empty_env_value_does_not_count_as_supervised(monkeypatch):
    """`docker compose exec -e VAR` with no value sets it empty — not a supervisor."""
    monkeypatch.setenv(SUPERVISOR_ENV, "")
    with pytest.raises(SystemExit):
        _require_supervisor(_args())


def test_the_guard_runs_before_any_network_work():
    """Ordering is the whole point: refusing after the sweep has started is not a refusal."""
    import inspect

    from scripts import backtest_sweep

    src = inspect.getsource(backtest_sweep.main)
    guard_at = src.index("_require_supervisor(args)")
    for later in ("httpx.Client(", "start_backtest_run(", "parse_universe("):
        if later in src:
            assert guard_at < src.index(later), f"{later} happens before the guard"


def test_ancestry_is_not_how_this_is_detected():
    """The supervisor is on the HOST; inside the container its ancestor is init.

    DEF387's write-up first proposed a process-ancestry check, which would have
    refused every legitimate supervised run and admitted every bare one.
    """
    import inspect

    from scripts.backtest_sweep import _require_supervisor as fn

    src = inspect.getsource(fn)
    assert "getppid" not in src and "/proc" not in src


# --- the guard's two halves must ship together ------------------------------

SUPERVISOR_DIR = Path(__file__).resolve().parents[2] / "scripts" / "supervisors"


def test_the_supervisors_are_version_controlled():
    """They used to live only in melehost's rsync-excluded backtest_results/.

    The sweep refuses to run without the marker these scripts set, so a guard
    whose enabling half exists on one unversioned disk is not a guard.
    """
    assert SUPERVISOR_DIR.is_dir()
    assert list(SUPERVISOR_DIR.glob("*.sh")), "no supervisor scripts checked in"


@pytest.mark.parametrize("script", sorted(SUPERVISOR_DIR.glob("*.sh")), ids=lambda p: p.name)
def test_every_supervisor_that_launches_a_sweep_sets_the_marker(script):
    # Comment lines stripped first: `run_sequential.sh` *mentions* the sweep in
    # its header while only ever calling other supervisors, and matching prose
    # would demand a marker from a script that launches nothing.
    body = "\n".join(
        ln for ln in script.read_text().splitlines()
        if not ln.lstrip().startswith("#")
    )
    if "backtest_sweep.py" not in body:
        pytest.skip(f"{script.name} does not launch a sweep directly")
    assert SUPERVISOR_ENV in body, (
        f"{script.name} invokes backtest_sweep.py without passing "
        f"{SUPERVISOR_ENV} — the sweep will refuse and the supervisor will "
        "retry the refusal 200 times"
    )
    assert f"-e {SUPERVISOR_ENV}=1" in body, (
        f"{script.name} must pass the marker through `docker compose exec -e`; "
        "setting it in the host shell does not cross the container boundary"
    )
