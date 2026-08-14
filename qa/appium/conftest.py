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


@pytest.fixture(scope="module")
def driver(device_profile):
    drv = new_driver(device_profile)
    # Every Phase 1 test assumes a landed-on-shell session (see
    # test_00_smoke_hierarchy.py's test_floor_tab_is_default_landing docstring) —
    # a fresh install starts on the Concierge interview instead, so make that
    # precondition true rather than just assumed. Cheap no-op once onboarding
    # has completed once, thanks to noReset=True.
    ensure_onboarded(drv)
    yield drv
    drv.quit()


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
    outcome = yield
    rep = outcome.get_result()
    if rep.when == "call" and rep.failed:
        drv = item.funcargs.get("driver")
        run_dir = item.funcargs.get("run_dir")
        if drv is not None and run_dir is not None:
            safe_name = item.nodeid.replace("/", "_").replace("::", "__")
            try:
                snap(drv, run_dir, f"FAILURE_{safe_name}", "state")
                dump_page_source(drv, run_dir, f"FAILURE_{safe_name}")
            except Exception as exc:  # best-effort evidence capture, never mask the real failure
                print(f"(failure-evidence capture also failed: {exc})")
