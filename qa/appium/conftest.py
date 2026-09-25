"""Session-wide fixtures. Mirrors backend/tests/conftest.py's autouse-fixture
style (fresh state per scope, no global mutable singletons) but scoped for
Appium: a session-scoped device *profile* and a module-scoped driver (one Appium
session per test file, balancing speed against isolation) that completes the
Concierge onboarding interview once per fresh install (see helpers/onboarding.py)
before yielding, so every test file starts from the same landed-on-Floor
precondition.

CR162 split the old session-scoped `device` fixture in two. Geometry on iOS can
only come from the live driver session — `element.rect` speaks points while
screenshots speak pixels, and only the running session knows the ratio — so the
profile (which the driver needs in order to exist) had to separate from the
measurements (which need the driver to exist). `device` is therefore
module-scoped now; its dict keys are unchanged, so no test needed rewriting.

Platform selection: `--platform=ios` or `AMI_PLATFORM=ios`, default `android`.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from config.devices import ANDROID, IOS, PROFILES
from config.locales import LOCALES
from helpers import device as device_helpers
from helpers.driver_factory import new_driver
from helpers.gestures import screen_scale
from helpers.onboarding import ensure_onboarded
from helpers.report import FlagCollector, write_summary_json
from helpers.shell import recover_to_shell, shell_is_up
from helpers.system_alerts import dismiss_system_alert_if_present
from tools import harness_manifest


def pytest_sessionstart(session):
    """Refuse to run an in-place-edited copy of this harness (CR162, closing
    CR080's flagged-but-unguarded second occurrence).

    Hooked at session start rather than offered as a fixture so it cannot be
    skipped by test selection — the two real incidents both produced *reports*,
    and a guard that only runs when someone remembers to request it would not
    have caught either. See tools/harness_manifest.py for the full history."""
    ok, message = harness_manifest.verify()
    if not ok:
        raise pytest.UsageError(f"HARNESS INTEGRITY: {message}")
    print(f"harness integrity: {message}")


def pytest_addoption(parser):
    parser.addoption(
        "--platform",
        action="store",
        default=os.environ.get("AMI_PLATFORM", ANDROID),
        choices=[ANDROID, IOS],
        help="which platform to drive (default android, or $AMI_PLATFORM)",
    )


def _report_dir() -> Path:
    configured = os.environ.get("AMI_REPORT_DIR")
    if configured:
        return Path(configured)
    # Fallback for ad-hoc local runs — timestamp not available (Claude-authored
    # scripts avoid datetime.now() by convention), so callers should really set
    # AMI_REPORT_DIR; this is just so a bare `pytest` doesn't hard-crash.
    return Path("./_report")


@pytest.fixture(scope="session")
def platform(pytestconfig) -> str:
    return pytestconfig.getoption("--platform")


@pytest.fixture(scope="session")
def run_dir() -> Path:
    d = _report_dir()
    (d / "screenshots").mkdir(parents=True, exist_ok=True)
    (d / "page_source").mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture(scope="session")
def device_profile(platform):
    """The static description of what we are driving. No live session needed,
    because the driver cannot be built without it."""
    profile = PROFILES[platform]
    serial = os.environ.get("AMI_SERIAL", "")

    if platform == IOS:
        if not serial:
            # A simulator UDID is machine-specific and must never be committed,
            # so it is resolved by name at run time.
            serial = device_helpers.resolve_ios_udid(
                os.environ.get("AMI_IOS_SIM_NAME", "iPhone 17")
            )
        device_helpers.boot_ios(serial)
    elif not serial:
        serial = profile.serial

    return profile.__class__(**{**profile.__dict__, "serial": serial})


@pytest.fixture(scope="session")
def flags(run_dir) -> FlagCollector:
    """Findings collector for the whole session. Written out to summary.json on
    teardown (i.e. once, after every test has run) rather than per-test, so a
    mechanical check can *record* a finding without failing the test it runs in.
    Pass/fail counts live in report.html (pytest-html) — this file's job is the
    findings list, not the tally."""
    collector = FlagCollector()
    yield collector
    write_summary_json(
        run_dir / "summary.json",
        run_id=run_dir.name,
        device_meta=collector.device_meta,
        app_version=collector.app_version,
        findings=collector.findings,
        passes=0,
        skips=0,
    )


#: DEF436 — the live driver, kept outside any fixture's return value.
#:
#: `pytest_runtest_makereport` used to read `item.funcargs.get("driver")`,
#: which is populated only once the `driver` fixture has *returned* — a
#: fixture that raises while setting itself up (exactly `ensure_onboarded`
#: timing out inside this fixture, DEF436's shape) never populates
#: `funcargs` at all, so the hook had nothing to capture evidence with and
#: silently produced none. A session-level holder, set the moment the
#: session exists rather than after setup completes, survives that case: it
#: is the same object `item.funcargs` would have held on success, just
#: written earlier. Overwritten per module (one Appium session per test
#: file), so the hook is always looking at whichever driver is actually
#: live right now, not a stale one from an earlier module.
_LIVE_DRIVER: dict[str, object] = {}


@pytest.fixture(scope="module")
def driver(device_profile):
    drv = new_driver(device_profile)
    _LIVE_DRIVER["driver"] = drv
    try:
        # Every Phase 1 test assumes a landed-on-shell session (see
        # test_00_smoke_hierarchy.py's test_floor_tab_is_default_landing
        # docstring) — a fresh install starts on the Concierge interview
        # instead, so make that precondition true rather than just assumed.
        # Cheap no-op once onboarding has completed once, thanks to
        # noReset=True.
        _require_unlocked(drv)
        # DEF426 — clear a native alert before the onboarding walk even
        # starts. noReset=True persists app state across the whole run, so a
        # permission decision (or prompt) from an earlier module's session
        # can still be sitting on screen when this module's driver attaches.
        dismiss_system_alert_if_present(drv)
        ensure_onboarded(drv)
    except Exception:
        # DEF436 — a setup-phase failure here (most often `ensure_onboarded`
        # timing out) is exactly the case `_LIVE_DRIVER` exists for: capture
        # evidence now, before `pytest_runtest_makereport` even runs, because
        # nothing else downstream will get a chance to see this screen.
        _capture_setup_failure_evidence(drv)
        raise
    yield drv
    drv.quit()
    _LIVE_DRIVER.pop("driver", None)


def _capture_setup_failure_evidence(drv) -> None:
    """Best-effort screenshot + page source for a `driver`-fixture setup
    failure, taken from inside the fixture itself.

    `pytest_runtest_makereport` cannot always do this after the fact: by the
    time it runs, the screen that caused the failure may already be gone
    (the fixture's `except` re-raises immediately, but a later retry/teardown
    elsewhere could still change what's on screen), and on the very first
    module of a run there's a moment where `_LIVE_DRIVER` is the only place
    the failing session is recorded at all. Capturing right here, at the
    moment of failure, is strictly more reliable than reconstructing it from
    hook state afterwards.
    """
    run_dir = _report_dir()
    try:
        (run_dir / "screenshots").mkdir(parents=True, exist_ok=True)
        (run_dir / "page_source").mkdir(parents=True, exist_ok=True)
        snap(drv, run_dir, "FAILURE_driver_fixture_setup", "state")
        dump_page_source(drv, run_dir, "FAILURE_driver_fixture_setup")
    except Exception as exc:  # best-effort evidence capture, never mask the real failure
        print(f"(setup-failure evidence capture also failed: {exc})")


def _require_unlocked(drv) -> None:
    """Refuse to run against a locked device, and say so in those words.

    Measured: a phone left on its lock screen absorbed a full 300s onboarding
    budget and the suite reported `onboarding did not reach Floor`. That
    sentence sends the reader to the app, which was never in the foreground —
    the same misleading shape as the dialer escape and the Convene sheet.

    Tries Appium's own unlock first, which clears a swipe-only lock. A secured
    lock needs the credential: set AMI_UNLOCK_TYPE (pin|password|pattern) and
    AMI_UNLOCK_KEY in the environment, never in git.
    """
    try:
        if not drv.is_locked():
            return
    except Exception:
        return  # driver cannot tell us; do not manufacture a failure

    try:
        drv.unlock()
    except Exception:
        pass

    if drv.is_locked():
        raise pytest.UsageError(
            "the device is LOCKED — nothing below this point is a test result. "
            "Appium could not clear it, which means a PIN/pattern/password is "
            "set. Either unlock the device by hand, disable its screen lock "
            "(it is an automation rig), or export AMI_UNLOCK_TYPE=pin and "
            "AMI_UNLOCK_KEY=<code> before running."
        )


@pytest.fixture(autouse=True)
def _shell_precondition(request):
    """Every test starts from the shell, even after an earlier one died holding
    a sheet open.

    The `driver` fixture is module-scoped, so a test that fails partway through
    — before its own `driver.back()` — leaves the Convene sheet or a trade
    ticket on top for every test after it in that module. Those then fail at
    `open_tab`, because a modal covers the bottom nav and the tab identifier
    does not resolve. One real failure became three, and the three looked like
    independent app defects.

    Worse than the noise: `ensure_onboarded` used to read that same covered nav
    as "onboarding has not finished" and set its exploratory walk loose, which
    convened the Room four times against the on-prem LLM. Restoring the
    precondition per test removes the state that misleads it.

    Announces when it fires rather than silently tidying up — a suite that
    quietly repairs itself hides the test that is not cleaning up after itself.
    """
    if "driver" not in request.fixturenames:
        yield  # offline test, no device
        return

    drv = request.getfixturevalue("driver")

    # DEF426 — a native permission dialog (e.g. iOS's "Turn on notifications?")
    # sits above the Flutter semantics tree entirely, so no locator below this
    # point can see it, let alone dismiss it. Clear it here, before the
    # shell-up check, so a covered-but-healthy app doesn't misreport as
    # "previous test left something open" and doesn't cascade into every test
    # in this module the way E5-U1 did. No-op on Android and when nothing is
    # up (see helpers/system_alerts.py).
    if dismiss_system_alert_if_present(drv):
        print(f"    [alert] {request.node.name} — dismissed a native system alert")

    floor_label = LOCALES["en"].tab_labels["Floor"]
    if not shell_is_up(drv, floor_label):
        print(
            f"    [shell] {request.node.name} did not start on the shell — a "
            f"previous test left something open. Recovering."
        )
        recover_to_shell(drv, floor_label)
    yield


@pytest.fixture(scope="module")
def device(driver, device_profile, flags):
    """Live geometry. Keys unchanged from the pre-CR162 session fixture, plus
    `scale` (device pixels per driver coordinate unit — 1.0 on Android, ~3 on a
    Retina iPhone; see helpers/layout.py on why conflating the two silently
    diffs the wrong region)."""
    profile = device_profile

    if profile.platform == IOS:
        window = driver.get_window_size()
        width, height = int(window["width"]), int(window["height"])
    else:
        width, height = device_helpers.display_size(profile)

    bottom_y, measured = device_helpers.obstructed_bottom_y(profile, display_height=height)
    if not measured:
        print(
            f"NOTE: bottom-obstruction band for {profile.name} is the platform "
            f"CONSTANT ({height - bottom_y}px/pt), not a live read. On Android "
            f"that means the dumpsys parse failed and may be stale; on iOS no "
            f"such query exists."
        )

    meta = {
        "platform": profile.platform,
        "profile": profile,
        "serial": profile.serial,
        "display": (width, height),
        "navbar_top_y": bottom_y,
        "navbar_top_y_measured": measured,
        "scale": screen_scale(driver),
        "app_version": device_helpers.app_version(profile),
    }

    # The summary is written at session teardown, after this module fixture is
    # gone — hand the collector a JSON-safe copy now rather than a dataclass it
    # cannot serialise.
    flags.device_meta = {
        "name": profile.name,
        "platform": profile.platform,
        "serial": profile.serial,
        "display": meta["display"],
        "navbar_top_y": meta["navbar_top_y"],
        "navbar_top_y_measured": measured,
        "scale": meta["scale"],
    }
    flags.app_version = meta["app_version"]
    return meta


def snap(driver, run_dir: Path, screen: str, state: str) -> Path:
    path = run_dir / "screenshots" / f"{screen}__{state}.png"
    driver.get_screenshot_as_file(str(path))
    return path


def dump_page_source(driver, run_dir: Path, screen: str) -> Path:
    path = run_dir / "page_source" / f"{screen}.xml"
    path.write_text(driver.page_source)
    return path


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Capture failure evidence for both a failing test body AND a failing
    fixture setup (DEF436).

    The original guard only fired on `rep.when == "call"` — a failure inside
    the test function itself. E5's iOS runs showed every one of 11 errors
    happening in *setup* instead: `ensure_onboarded` (called from the
    `driver` fixture) timing out before the test body ever started. `call`
    reports don't exist for those at all — pytest reports `setup` as failed
    and never generates a `call` report — so the old condition was simply
    never true for this entire failure class, and 11 errors left zero
    screenshots or page sources to diagnose from (E5-U3).

    `item.funcargs` is also unreliable exactly when it matters most: it is
    populated as each fixture *returns*, so a fixture that raises while
    setting itself up never gets added to it — `item.funcargs.get("driver")`
    is `None` in precisely the case this hook now exists to cover. Fall back
    to the module-level `_LIVE_DRIVER` holder (set the instant the driver
    exists, before any of the setup that might fail) and to `_report_dir()`
    directly (mirrors the session-scoped `run_dir` fixture's own logic, and
    needs no fixture to have completed) so neither piece of evidence depends
    on the very setup that just failed.
    """
    outcome = yield
    rep = outcome.get_result()
    if rep.when not in ("call", "setup") or not rep.failed:
        return

    drv = item.funcargs.get("driver") or _LIVE_DRIVER.get("driver")
    run_dir = item.funcargs.get("run_dir") or _report_dir()
    if drv is None or run_dir is None:
        return

    (run_dir / "screenshots").mkdir(parents=True, exist_ok=True)
    (run_dir / "page_source").mkdir(parents=True, exist_ok=True)
    safe_name = item.nodeid.replace("/", "_").replace("::", "__")
    label = f"FAILURE_{rep.when}_{safe_name}" if rep.when == "setup" else f"FAILURE_{safe_name}"
    try:
        snap(drv, run_dir, label, "state")
        dump_page_source(drv, run_dir, label)
    except Exception as exc:  # best-effort evidence capture, never mask the real failure
        print(f"(failure-evidence capture also failed: {exc})")
