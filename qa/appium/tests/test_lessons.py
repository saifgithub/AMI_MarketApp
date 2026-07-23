"""Lessons tab — Phase 1 smoke coverage. See test_scroll_overflow.py /
test_sheets_navbar.py for the cross-cutting mechanical checks."""

from __future__ import annotations

import pytest

from conftest import snap
from helpers.locators import wait_visible_text
from pages.base_page import open_tab

pytestmark = [pytest.mark.phase1]


def test_lessons_renders_heading(driver, run_dir):
    open_tab(driver, "Lessons")
    wait_visible_text(driver, "LESSONS", timeout_s=10)
    snap(driver, run_dir, "lessons", "default")
