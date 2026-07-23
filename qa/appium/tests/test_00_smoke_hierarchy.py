"""GO/NO-GO gate — run this first, always.

AMI Trade has no enableFlutterDriverExtension() call anywhere, so this
harness's whole premise is that plain UiAutomator2 can still see Flutter's
rendered text via the Android accessibility tree once an accessibility
client (UiAutomator2's own server) interrogates the window — no special
build or driver plugin needed. That premise is reasoned-through (see CR080 /
qa/appium/README.md) but genuinely untested until a real run happens.

If this file fails, do NOT trust test_sheets_navbar.py / test_scroll_overflow.py
or anything else in this suite — the documented fallback is forcing a device
accessibility service on (`adb shell settings put secure
enabled_accessibility_services ...`) before going further, not silently
falling back to coordinate-only interaction.
"""

from __future__ import annotations

import pytest

from helpers.locators import exists_text, wait_visible_text
from pages.base_page import TAB_LABELS

pytestmark = [pytest.mark.smoke, pytest.mark.phase1]


def test_bottom_nav_text_resolves(driver, run_dir):
    """The single most basic claim this harness depends on: a visible label
    on screen is findable by exact text through UiAutomator2's accessibility
    dump. If this fails, nothing downstream can be trusted."""
    driver.get_screenshot_as_file(str(run_dir / "screenshots" / "smoke__launch.png"))
    found = {label: exists_text(driver, label) for label in TAB_LABELS}
    missing = [label for label, ok in found.items() if not ok]
    assert not missing, (
        f"bottom-nav labels not found via text locator: {missing}. "
        "Flutter's semantics tree may not be populating under UiAutomator2 — "
        "see this file's docstring for the fallback."
    )


def test_navbar_band_is_plausible(device):
    """Sanity-check the dumpsys-derived nav-bar read isn't nonsense (e.g. 0,
    or below the display) before any mechanical check relies on it."""
    width, height = device["display"]
    navbar_top_y = device["navbar_top_y"]
    assert 0 < navbar_top_y < height, (
        f"navbar_top_y={navbar_top_y} is outside the display height {height} — "
        "the dumpsys parse likely failed silently onto the fallback constant; "
        "check helpers/device.navbar_top_y's two regexes against this device's "
        "actual `dumpsys window displays`/`dumpsys window windows` output."
    )
    assert navbar_top_y > height * 0.85, (
        f"navbar_top_y={navbar_top_y} claims the nav bar occupies more than 15% "
        f"of a {height}px display — implausible, re-check the parse."
    )


def test_floor_tab_is_default_landing(driver, run_dir):
    """Confirms the app actually launched into the shell (not stuck on
    onboarding/a splash) — the precondition every other Phase 1 test assumes
    via noReset."""
    element = wait_visible_text(driver, "Floor", timeout_s=15)
    assert element is not None
    driver.get_screenshot_as_file(str(run_dir / "screenshots" / "smoke__floor_landing.png"))
