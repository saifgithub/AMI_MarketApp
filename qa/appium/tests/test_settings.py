"""Settings tab — Phase 1 smoke coverage. See test_scroll_overflow.py /
test_sheets_navbar.py for the cross-cutting mechanical checks.

Content-depth strings verified against mobile/lib/l10n/app_en.arb:
  settingsSectionMandate = "MY MANDATE"  — the screen's primary section,
    hard-asserted (settings_screen.dart is 1119 lines across several
    sections; this one is guaranteed, the rest below aren't without knowing
    exact scroll position).
  settingsRiskScore = "Risk score", settingsSignIn = "SIGN IN" — logged only
    after one swipe-down-the-page attempt, since their exact position on a
    long settings screen isn't something this test should assume.

Sign-in and Alpaca-connect flows are Phase 2 — they need real credentials
Saiful must supply (see test_data/README.md), never fabricated here.
"""

from __future__ import annotations

import pytest

from conftest import snap
from helpers.gestures import swipe_up
from helpers.locators import wait_visible_text
from pages.base_page import content_band, open_you_segment, probe_content

pytestmark = [pytest.mark.phase1]


def test_settings_renders_heading(driver, device, run_dir):
    # CR133 moved SETTINGS off the bottom nav into a YOU segment. This test kept
    # calling `open_tab(driver, "Settings")` for months afterwards, which now
    # asserts out before it touches the device.
    #
    # The old `wait_visible_text(driver, "SETTINGS")` cannot come back either,
    # and it is worth being explicit about why, because it looks like it should
    # still work: an *embedded* SettingsScreen drops its own AmiScreenHeader
    # (YOU owns the header), so `settingsHeading` is not rendered at all. The
    # only "SETTINGS" on screen is the segment button — which is present the
    # instant YOU paints, so waiting on it asserts nothing about the pane and
    # races the pane's first frame. `MY MANDATE` is the section at the top of
    # the pane's own ListView, so it is both the readiness signal and the
    # assertion.
    open_you_segment(driver, "Settings")
    wait_visible_text(driver, "MY MANDATE", timeout_s=10)
    signals = probe_content(driver, "settings", exact=("MY MANDATE",))
    assert signals["MY MANDATE"], "Settings should always show the MY MANDATE section"
    swipe_up(driver, content_band(device), percent=0.5)
    probe_content(driver, "settings (after scroll)", contains=("Risk score", "SIGN IN"))
    snap(driver, run_dir, "settings", "default")


@pytest.mark.phase2
@pytest.mark.skip(reason="needs a test-email inbox for the sign-in email-code path — see test_data/README.md")
def test_sign_in_email_code_flow():
    ...


@pytest.mark.phase2
@pytest.mark.skip(reason="needs a real Alpaca paper-trading API key/secret — see test_data/README.md")
def test_alpaca_connect_flow():
    ...
