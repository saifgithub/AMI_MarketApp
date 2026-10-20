"""Paywall (UAT-BILL-012): the upgrade sheet shows the plans, or the documented
no-offering fallback with Restore purchases — never an empty sheet. Nothing is
purchased (CR263).

Entry is the Floor Pass ad banner ("See Trader plans"), not Settings >
Membership: on iOS the Settings pane below PROFILE darkens the accessibility
tree (DEF466), so Membership cannot be reached by a black-box driver there. The
sheet itself is the same widget.
"""

from __future__ import annotations

import time

import pytest

from conftest import snap
from helpers.journeys import close_sheet, wait_any_text
from helpers.locators import _all_by_text_contains, exists_text, exists_text_contains, wait_visible_text_contains
from pages.base_page import open_tab

pytestmark = [pytest.mark.phase2]


@pytest.mark.uat("UAT-BILL-012")
def test_upgrade_sheet_shows_plans_or_the_documented_fallback(driver, run_dir):
    open_tab(driver, "Floor")
    time.sleep(2.0)
    banner = _all_by_text_contains(driver, "See Trader plans", retry=True)
    assert banner, (
        "no upgrade banner on the Floor: the test account is not on Floor Pass, "
        "so the paywall entry point this test uses is absent"
    )
    banner[0].click()
    wait_visible_text_contains(driver, "Upgrade your desk", timeout_s=15)
    time.sleep(1.5)
    snap(driver, run_dir, "paywall", "sheet")
    which = wait_any_text(
        driver,
        ["Floor Manager", "Upgrades aren't available yet", "Upgrades aren’t available yet"],
        timeout_s=12,
        contains=True,
    )
    print(f"    [paywall] sheet content: {which!r}")
    fallback = which.startswith("Upgrades aren")
    if fallback:
        assert exists_text(driver, "Restore purchases"), (
            "the no-offering fallback card must offer Restore purchases"
        )
    else:
        assert exists_text_contains(driver, "$", retry=False), "plans are listed without any price"
    close_sheet(driver)
