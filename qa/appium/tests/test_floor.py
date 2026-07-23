"""Floor tab — Phase 1 smoke coverage. Mechanical scroll/navbar checks live
in test_scroll_overflow.py / test_sheets_navbar.py (cross-cutting); this file
just confirms the tab's own key elements render."""

from __future__ import annotations

import pytest

from conftest import snap
from helpers.locators import wait_visible_text
from pages.base_page import open_tab

pytestmark = [pytest.mark.phase1]


def test_floor_renders_convene_cta(driver, run_dir):
    open_tab(driver, "Floor")
    wait_visible_text(driver, "CONVENE THE ROOM", timeout_s=10)
    snap(driver, run_dir, "floor", "default")
