"""Offline guards for DEF436's capture-gap fix.

E5's iOS runs errored 11 test modules in a row with zero screenshots or page
sources to show for it (E5-U3): `pytest_runtest_makereport` only fired on
`rep.when == "call"`, but every one of those 11 errors happened while the
`driver` fixture itself was still setting up (`ensure_onboarded` timing out
inside it) — pytest reports that as `setup`, never `call`, so the old
condition could never be true for this failure class. Worse, even a hook that
checked `setup` too would have found `item.funcargs.get("driver")` empty,
because `funcargs` is only populated once a fixture *returns* successfully.

These tests pin the fix's two moving parts without a real Appium session:

- `_LIVE_DRIVER`, a module-level holder set the instant the driver exists
  (before any of the setup that might fail), which the hook falls back to
  when `item.funcargs` has nothing.
- `pytest_runtest_makereport` firing on both `"call"` and `"setup"`, and
  actually writing evidence via the fallback path.

`conftest.py` is imported directly as a module (same trick this suite already
uses to reach `helpers.*` without a live device) rather than run through
pytest's own plugin machinery, so `pytest_runtest_makereport`'s hookwrapper
generator is driven by hand: advance it to its `yield`, then `.send()` a fake
pluggy result carrying the `TestReport`-shaped object under test.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import conftest  # noqa: E402


class FakeDriver:
    def __init__(self):
        self.screenshots: list[str] = []
        self.page_source = "<AppiumAUT/>"

    def get_screenshot_as_file(self, path):
        self.screenshots.append(path)
        return True


class FakeReport:
    def __init__(self, when: str, failed: bool):
        self.when = when
        self.failed = failed


class FakeOutcome:
    """Mimics pluggy's `_Result` well enough for `.get_result()`."""

    def __init__(self, report):
        self._report = report

    def get_result(self):
        return self._report


def _drive_hook(item, when: str, failed: bool):
    """Advance the hookwrapper generator through its single yield point,
    handing it a fake outcome, and let it run to completion."""
    call = SimpleNamespace(when=when)
    gen = conftest.pytest_runtest_makereport(item, call)
    next(gen)  # run up to `outcome = yield`
    try:
        gen.send(FakeOutcome(FakeReport(when, failed)))
    except StopIteration:
        pass


@pytest.fixture(autouse=True)
def _clear_live_driver():
    conftest._LIVE_DRIVER.clear()
    yield
    conftest._LIVE_DRIVER.clear()


def test_a_call_phase_failure_still_captures_from_funcargs(tmp_path):
    """The pre-DEF436 path must keep working: a failure inside the test body
    itself, where `item.funcargs` already has both `driver` and `run_dir`."""
    drv = FakeDriver()
    item = SimpleNamespace(
        funcargs={"driver": drv, "run_dir": tmp_path},
        nodeid="tests/test_x.py::test_y",
    )
    _drive_hook(item, when="call", failed=True)
    assert drv.screenshots, "call-phase failure produced no screenshot"
    assert (tmp_path / "page_source" / "FAILURE_tests_test_x.py__test_y.xml").exists()


def test_a_setup_phase_failure_is_now_captured_via_the_live_driver_holder(tmp_path, monkeypatch):
    """The DEF436 shape exactly: the `driver` fixture raised while setting
    itself up (e.g. `ensure_onboarded` timing out), so `item.funcargs` never
    got populated — pytest never adds a fixture to `funcargs` until it
    returns. Only `_LIVE_DRIVER`, set at the top of the `driver` fixture
    before anything that can fail, has the session at all."""
    monkeypatch.setattr(conftest, "_report_dir", lambda: tmp_path)
    drv = FakeDriver()
    conftest._LIVE_DRIVER["driver"] = drv

    item = SimpleNamespace(funcargs={}, nodeid="tests/test_lessons.py::test_lessons_renders_heading")
    _drive_hook(item, when="setup", failed=True)

    assert drv.screenshots, "setup-phase failure with no funcargs still produced no evidence"
    matches = list((tmp_path / "page_source").glob("FAILURE_setup_*.xml"))
    assert matches, "expected a FAILURE_setup_* page source, found none"


def test_a_setup_failure_with_no_driver_anywhere_is_a_quiet_no_op():
    """Before the very first module's driver exists, or after teardown has
    cleared it, there is genuinely nothing to capture from. This must not
    raise — a capture helper that fails the test it is protecting is worse
    than the gap it closes (same principle `system_alerts.py` documents)."""
    item = SimpleNamespace(funcargs={}, nodeid="tests/test_x.py::test_y")
    _drive_hook(item, when="setup", failed=True)  # must not raise


def test_a_passing_setup_is_not_touched():
    """Only failed reports trigger capture — a passing `setup` for every one
    of hundreds of tests must not spend a screenshot it doesn't need."""
    drv = FakeDriver()
    conftest._LIVE_DRIVER["driver"] = drv
    item = SimpleNamespace(funcargs={}, nodeid="tests/test_x.py::test_y")
    _drive_hook(item, when="setup", failed=False)
    assert drv.screenshots == []


def test_teardown_phase_reports_are_ignored():
    """`rep.when` also takes the value `"teardown"` — a failure there (e.g.
    `drv.quit()` raising) is not evidence of what the test itself saw, and
    capturing then would attribute the wrong screen to the wrong failure."""
    drv = FakeDriver()
    conftest._LIVE_DRIVER["driver"] = drv
    item = SimpleNamespace(funcargs={}, nodeid="tests/test_x.py::test_y")
    _drive_hook(item, when="teardown", failed=True)
    assert drv.screenshots == []


def test_the_live_driver_holder_is_overwritten_per_module_not_accumulated():
    """One Appium session per test file (module-scoped `driver`): the holder
    must reflect whichever session is live right now, not grow into a stale
    list an old module's driver lingers in."""
    first, second = FakeDriver(), FakeDriver()
    conftest._LIVE_DRIVER["driver"] = first
    conftest._LIVE_DRIVER["driver"] = second
    assert conftest._LIVE_DRIVER["driver"] is second
    assert len(conftest._LIVE_DRIVER) == 1
