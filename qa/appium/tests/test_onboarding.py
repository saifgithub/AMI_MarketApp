"""First-run journey (UAT-ONB-043): a fresh install walks the Concierge interview
to a mandate readback and lands on the Floor (CR263).

This is the one test that destroys state on purpose. It deletes the app (iOS) or
clears its data (Android), so the device gets a NEW anonymous account — new Room
credits, an empty book, no lessons, no journal. `conftest.pytest_collection_
modifyitems` therefore runs this module right after the smoke gate, so every
journey that follows starts from the same fresh account instead of whatever the
previous run left behind (a spent daily trade cap and spent Room credits are
real examples that cost a development day).
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

from conftest import snap
from config.semantics_ids import NAV_IDS, ONBOARDING_ANSWER_CHIP
from helpers import device as device_helpers
from helpers import onboarding
from helpers.journeys import settle
from helpers.locators import exists_id, wait_visible_id, wait_visible_text_contains
from helpers.platform import is_ios
from pages.base_page import open_you_segment

pytestmark = [pytest.mark.phase2]


def _fresh_install(driver, profile) -> None:
    """Remove the app's data so the next launch is a first run."""
    if is_ios(driver):
        udid, bundle = profile.serial, profile.bundle_id
        container = subprocess.run(
            ["xcrun", "simctl", "get_app_container", udid, bundle, "app"],
            capture_output=True, text=True, timeout=60, check=True,
        ).stdout.strip()
        keep = Path(tempfile.mkdtemp(prefix="ami_app_")) / Path(container).name
        shutil.copytree(container, keep)
        device_helpers.reset_app(profile)
        device_helpers.install_app(profile, str(keep))
    else:
        device_helpers.reset_app(profile)
    driver.activate_app(profile.app_id)


@pytest.mark.uat("UAT-ONB-043")
def test_fresh_install_walks_the_interview_to_a_readback_and_lands_on_the_floor(driver, device_profile, run_dir):
    _fresh_install(driver, device_profile)
    time.sleep(5.0)

    # the interview must open with answer chips - not an error, not a blank screen
    wait_visible_id(driver, ONBOARDING_ANSWER_CHIP, timeout_s=120)
    snap(driver, run_dir, "onboarding", "first_question")
    assert not exists_id(driver, NAV_IDS["Floor"], retry=False), "the shell was already up on a fresh install"

    onboarding.ensure_onboarded(driver)
    print(f"    [onboarding] milestones: {onboarding.walk_milestones}")
    for milestone in ("chips", "readback", "floor"):
        assert milestone in onboarding.walk_milestones, (
            f"the walk never passed through {milestone!r}: {onboarding.walk_milestones}"
        )
    settle(driver, 2.0)
    snap(driver, run_dir, "onboarding", "landed_on_floor")
    for tab in ("Floor", "Portfolio", "Lessons", "You"):
        assert exists_id(driver, NAV_IDS[tab], retry=False), f"tab {tab} missing after onboarding"

    # the interview's mandate is the user's, not a blank one
    open_you_segment(driver, "Settings")
    wait_visible_text_contains(driver, "MY MANDATE", timeout_s=15)
    wait_visible_text_contains(driver, "Risk score", timeout_s=5)
    snap(driver, run_dir, "onboarding", "mandate_in_settings")
