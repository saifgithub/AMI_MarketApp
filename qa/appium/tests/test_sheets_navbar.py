"""★ Cross-cutting DEF075-class check: is any interactive element in a modal
sheet hidden under/clipped by the Android system nav bar?

Phase 1 covers the sheets reachable from a plain onboarded-guest session with
no seeded backend state:
  - Convene sheet (Floor tab -> "CONVENE THE ROOM")
  - Trade ticket sheet (Portfolio tab -> "New trade" icon button)
  - Bug report sheet (Settings tab -> long-press the app-version chip)

`merge_sheet.dart` is NOT covered here — it only renders when a federated
sign-in adopts an orphan anonymous account (`adoptedFromUserId != null`),
which needs seeded backend state. It stays on its existing widget-test guard
(`mobile/test/widgets/sheet_insets_test.dart`) for Phase 1; Phase 2 adds a
seeded-account scenario for it.
"""

from __future__ import annotations

import pytest

from conftest import snap
from helpers.gestures import (
    hide_keyboard_if_shown,
    long_press_element,
    screenshot_png,
    scroll_to_top,
    swipe_up,
)
from helpers.layout import find_navbar_overlaps
from helpers.locators import (
    by_content_desc,
    by_text_contains,
    exists_text_contains,
    wait_visible_text,
    wait_visible_text_contains,
)
from helpers.report import annotate_png
from pages.base_page import open_tab, open_you_segment, scroll_band

pytestmark = [pytest.mark.navbar, pytest.mark.phase1]

# Enough to reach the bottom of the SETTINGS pane, not enough to spin forever.
_MAX_SETTINGS_SCROLLS = 12


def _record_and_assert_soft(flags, findings, run_dir, sheet_name, driver, navbar_top_y, scale=1.0):
    """Mechanical nav-bar findings are recorded, not hard-failed — a UAT pass
    wants the complete report, not a stop at the first flagged sheet. High-
    severity findings (button center literally under the nav bar) still fail
    the test, since that's a near-certain reproduction of the DEF075 class."""
    for finding in findings:
        flags.add(finding)
    high = [f for f in findings if f["severity"] == "high"]
    if findings:
        annotate_png(
            screenshot_png(driver),
            run_dir / "screenshots" / f"{sheet_name}__navbar_overlap.png",
            navbar_top_y=navbar_top_y,
            boxes=[tuple(f["bounds"]) for f in findings],
            scale=scale,
        )
    assert not high, f"{sheet_name}: {len(high)} element(s) with center under the nav bar: {high}"


def test_convene_sheet_navbar(driver, device, run_dir, flags):
    open_tab(driver, "Floor")
    cta = wait_visible_text(driver, "CONVENE THE ROOM", timeout_s=10)
    cta.click()
    wait_visible_text(driver, "CONVENE", timeout_s=8)  # conveneCta button, confirms the sheet opened
    snap(driver, run_dir, "convene_sheet", "open")
    findings = find_navbar_overlaps(driver, device["navbar_top_y"], screen="convene_sheet")
    driver.back()  # close the sheet so later tests start clean
    _record_and_assert_soft(
        flags, findings, run_dir, "convene_sheet", driver,
        device["navbar_top_y"], device["scale"],
    )


def test_trade_ticket_sheet_navbar(driver, device, run_dir, flags):
    open_tab(driver, "Portfolio")
    trigger = by_content_desc(driver, "New trade")
    trigger.click()
    wait_visible_text(driver, "NEW TRADE", timeout_s=8)  # tradeTicketHeading
    snap(driver, run_dir, "trade_ticket_sheet", "open")
    findings = find_navbar_overlaps(driver, device["navbar_top_y"], screen="trade_ticket_sheet")
    driver.back()
    _record_and_assert_soft(
        flags, findings, run_dir, "trade_ticket_sheet", driver,
        device["navbar_top_y"], device["scale"],
    )


def test_bug_report_sheet_navbar(driver, device, run_dir, flags):
    # CR133 — Settings is a YOU segment now, not a destination. The version
    # chip lives at the bottom of the Settings pane, so wait for the pane's own
    # first section before hunting for it: the segment button carries the label
    # "SETTINGS" and is on screen before the pane has rendered anything.
    open_you_segment(driver, "Settings")
    scroll_to_top(driver, scroll_band(driver, device))
    wait_visible_text_contains(driver, "MY MANDATE", timeout_s=10)

    # The version chip is the LAST thing in a long ListView
    # (settings_screen.dart:1238, `'AMI Trade v$version'`), so it has to be
    # scrolled to — it is not on screen when the pane opens. This did not need
    # scrolling while SETTINGS was a full tab; inside YOU the pane is shorter by
    # the header and the segment bar, which is enough to push the chip under the
    # fold. Bounded rather than while-not-found: an unbounded scroll on a screen
    # that will never show the target is indistinguishable from a hang.
    version_chip = None
    for _ in range(_MAX_SETTINGS_SCROLLS):
        if exists_text_contains(driver, "AMI Trade v", retry=False):
            version_chip = by_text_contains(driver, "AMI Trade v")
            break
        if not swipe_up(driver, scroll_band(driver, device), percent=1.0):
            break  # hit the end of the list; one more look below, then fail
    if version_chip is None and exists_text_contains(driver, "AMI Trade v", retry=False):
        version_chip = by_text_contains(driver, "AMI Trade v")
    assert version_chip is not None, (
        f"the app-version chip never appeared after {_MAX_SETTINGS_SCROLLS} "
        f"scrolls of the SETTINGS pane. It is the long-press target that opens "
        f"the bug-report sheet, so without it this check cannot run at all."
    )
    long_press_element(driver, version_chip)
    snap(driver, run_dir, "bug_report_sheet", "open")
    findings = find_navbar_overlaps(driver, device["navbar_top_y"], screen="bug_report_sheet")
    hide_keyboard_if_shown(driver)
    driver.back()
    _record_and_assert_soft(
        flags, findings, run_dir, "bug_report_sheet", driver,
        device["navbar_top_y"], device["scale"],
    )
