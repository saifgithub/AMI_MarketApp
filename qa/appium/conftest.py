"""Session-wide fixtures. Mirrors backend/tests/conftest.py's autouse-fixture
style (fresh state per scope, no global mutable singletons) but scoped for
Appium: a session-scoped device profile (the nav-bar read is one dumpsys call,
do it once) and a module-scoped driver (one Appium session per test file,
balancing speed against isolation)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from config.devices import DEFAULT_DEVICE
from helpers import device as device_helpers
from helpers.driver_factory import new_driver
from helpers.report import FlagCollector, write_summary_json


def _report_dir() -> Path:
    configured = os.environ.get("AMI_REPORT_DIR")
    if configured:
        return Path(configured)
    # Fallback for ad-hoc local runs — timestamp not available (Claude-authored
    # scripts avoid datetime.now() by convention), so callers should really set
    # AMI_REPORT_DIR; this is just so a bare `pytest` doesn't hard-crash.
    return Path("./_report")


@pytest.fixture(scope="session")
def run_dir() -> Path:
    d = _report_dir()
    (d / "screenshots").mkdir(parents=True, exist_ok=True)
    (d / "page_source").mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture(scope="session")
def device():
    serial = os.environ.get("AMI_SERIAL", DEFAULT_DEVICE.serial)
    profile = DEFAULT_DEVICE if serial == DEFAULT_DEVICE.serial else DEFAULT_DEVICE.__class__(
        name=serial, serial=serial
    )
    width, height = device_helpers.display_size(serial)
    navbar_y = device_helpers.navbar_top_y(serial, fallback_px=profile.navbar_height_px_fallback)
    if navbar_y == height - profile.navbar_height_px_fallback:
        print(f"NOTE: nav-bar band read via fallback constant for {serial} — dumpsys parse may be stale.")
    version = device_helpers.app_version(serial, profile.app_package)
    return {
        "profile": profile,
        "serial": serial,
        "display": (width, height),
        "navbar_top_y": navbar_y,
        "app_version": version,
    }


@pytest.fixture(scope="session")
def flags(run_dir, device) -> FlagCollector:
    """Findings collector for the whole session. Written out to
    summary.json on teardown (i.e. once, after every test has run) rather
    than per-test, so a mechanical check can *record* a finding without
    failing the test it runs in. Pass/fail counts live in report.html
    (pytest-html) — this file's job is the findings list, not the tally."""
    collector = FlagCollector()
    yield collector
    write_summary_json(
        run_dir / "summary.json",
        run_id=run_dir.name,
        device_meta={
            "name": device["profile"].name,
            "serial": device["serial"],
            "display": device["display"],
            "navbar_top_y": device["navbar_top_y"],
        },
        app_version=device["app_version"],
        findings=collector.findings,
        passes=0,
        skips=0,
    )


@pytest.fixture(scope="module")
def driver(device):
    drv = new_driver(device["profile"])
    yield drv
    drv.quit()


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
