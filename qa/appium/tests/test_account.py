"""Account deletion and export on the device (UAT-AUTH-044, CR276).

NEVER taps DELETE ACCOUNT. The rig's account is persistent and shared by every
other journey; a confirmed deletion would sign it out and start a 30-day
countdown on the shared user. The test proves the other half of the control:
the entry points exist, the dialog says what it must, and CANCEL changes
nothing. The confirmed path is covered by the widget tests and the live API
cases (UAT-AUTH-041/043), and restoring by hand is UAT-AUTH-045.
"""

from __future__ import annotations

import time

import pytest

from conftest import snap
from helpers.journeys import scroll_until_text, scroll_up, tap_text
from helpers.locators import exists_text, exists_text_contains, wait_visible_text, wait_visible_text_contains
from pages.base_page import open_you_segment

pytestmark = [pytest.mark.phase2]


@pytest.mark.uat("UAT-AUTH-044")
def test_settings_offers_export_and_delete_and_delete_asks_first(driver, run_dir):
    open_you_segment(driver, "Settings")
    wait_visible_text_contains(driver, "MY MANDATE", timeout_s=15)

    scroll_until_text(driver, "Export my data", max_scrolls=25)
    time.sleep(0.5)
    assert exists_text(driver, "Export my data"), "Settings has no Export my data button"
    assert exists_text_contains(driver, "JSON file"), "the export button has lost its caption"

    # "Close account" replaces the label only if the server reports archive mode.
    label = "Delete account" if exists_text(driver, "Delete account") else "Close account"
    assert label == "Delete account", "Beta must say Delete account (archive mode is off until counsel approves)"
    tap_text(driver, label, timeout_s=8)

    wait_visible_text(driver, "DELETE ACCOUNT?", timeout_s=10)
    snap(driver, run_dir, "delete_account", "dialog")
    for fragment in ("restore it", "permanently deleted", "Kept:"):
        assert exists_text_contains(driver, fragment), f"the dialog no longer says '{fragment}'"
    assert exists_text(driver, "CANCEL"), "the dialog has no CANCEL"

    tap_text(driver, "CANCEL", timeout_s=8)
    time.sleep(1.0)
    assert not exists_text(driver, "DELETE ACCOUNT?", retry=False), "CANCEL left the dialog open"
    assert exists_text(driver, label), "CANCEL changed the Settings screen"
    scroll_up(driver, times=12)
