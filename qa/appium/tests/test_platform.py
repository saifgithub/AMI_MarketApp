"""Platform smoke (UAT-PLAT-005): a current build cold-launches past the version
gate to the Floor (CR263).

The gate's two failure shapes are the ones a user can actually hit: the forced
"Update Required" screen on a build the backend still supports, and a launch that
never reaches the shell. Both are asserted against a real cold start.
"""

from __future__ import annotations

import time

import pytest

from conftest import snap
from config.locales import LOCALES
from config.semantics_ids import NAV_IDS
from helpers.journeys import settle
from helpers.locators import exists_id, exists_text
from helpers.onboarding import _app_id
from helpers.shell import wait_for_shell

pytestmark = [pytest.mark.phase1]


@pytest.mark.uat("UAT-PLAT-005")
def test_cold_launch_passes_the_version_gate_to_the_floor(driver, run_dir):
    app_id = _app_id(driver)
    driver.terminate_app(app_id)
    time.sleep(2.0)
    driver.activate_app(app_id)

    floor_label = LOCALES["en"].tab_labels["Floor"]
    assert wait_for_shell(driver, floor_label, timeout_s=90), (
        "a cold launch never reached the shell within 90s (the Floor's bottom bar did not appear)"
    )
    settle(driver, 2.0)
    snap(driver, run_dir, "platform", "cold_launch")
    assert not exists_text(driver, "Update Required", retry=False), (
        "the forced-update screen appeared on a current build"
    )
    for tab in ("Floor", "Portfolio", "Lessons", "You"):
        assert exists_id(driver, NAV_IDS[tab], retry=False), f"tab {tab} missing after a cold launch"
