"""Support journey (UAT-SUPP-012): the bug-report sheet opens from Settings and
refuses an empty submission (CR263).

NEVER submits a report — a submission lands in the real triage queue. The only
thing sent is a tap on "Send report" with the required title empty, which the
form validates client-side and sends nowhere; if that validation were ever
removed this test would file one empty report, which is the cost of testing the
validation at all.

iOS note: DEF466 says scrolling Settings past MY MANDATE darkens the iOS accessibility
tree. Scrolling down the right-hand margin (journeys.scroll_down) to HELP did NOT
darken it on the iPhone 17 Simulator, so this journey runs un-xfailed; whether
DEF466 is specific to a mid-screen drag is worth a look.
"""

from __future__ import annotations

import time

import pytest

from conftest import snap
from helpers.journeys import close_sheet, scroll_until_text, scroll_up, tap_button, tap_text
from helpers.locators import exists_text, wait_visible_text, wait_visible_text_contains
from pages.base_page import open_you_segment

pytestmark = [pytest.mark.phase2]


@pytest.mark.uat("UAT-SUPP-012")
def test_bug_report_sheet_opens_and_refuses_an_empty_submission(driver, run_dir):
    open_you_segment(driver, "Settings")
    wait_visible_text_contains(driver, "MY MANDATE", timeout_s=15)
    scroll_until_text(driver, "Report a problem", max_scrolls=25)
    time.sleep(0.8)
    tap_text(driver, "Report a problem", timeout_s=8)
    wait_visible_text(driver, "Report a bug", timeout_s=10)
    snap(driver, run_dir, "bug_report", "sheet")
    assert exists_text(driver, "Send report"), "the sheet has no Send report button"

    tap_button(driver, "Send report", timeout_s=8)
    wait_visible_text(driver, "Required", timeout_s=6)
    snap(driver, run_dir, "bug_report", "validation")
    assert exists_text(driver, "Report a bug", retry=False), "the sheet closed instead of validating"
    close_sheet(driver)
    scroll_up(driver, times=12)
