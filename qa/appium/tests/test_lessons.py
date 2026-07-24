"""Lessons tab — Phase 1 smoke coverage. See test_scroll_overflow.py /
test_sheets_navbar.py for the cross-cutting mechanical checks.

Track/category names (e.g. "Risk", "Fundamentals") are NOT static ARB
strings — the honeycomb is built from backend lesson-catalogue content
(CR020's full_context_index, 342+ lessons and growing, e.g. CR058's M25
Islamic-finance track added mid-project). Hardcoding a specific category
list here would be fragile against exactly the kind of content change this
project makes routinely — so instead of asserting names, this checks that
the honeycomb actually rendered *something* clickable (a structural richness
signal: an empty grid is itself a real bug, but which categories exist
isn't this test's job to pin down).
"""

from __future__ import annotations

import pytest

from conftest import snap
from helpers.locators import interactive_elements, wait_visible_text
from pages.base_page import open_tab

pytestmark = [pytest.mark.phase1]


def test_lessons_renders_heading(driver, run_dir):
    open_tab(driver, "Lessons")
    wait_visible_text(driver, "LESSONS", timeout_s=10)
    clickable_count = len(interactive_elements(driver))
    print(f"    [lessons] {clickable_count} clickable element(s) on the honeycomb landing screen")
    assert clickable_count > 3, (
        f"only {clickable_count} clickable elements found on Lessons — honeycomb may be empty "
        "(bottom-nav tabs alone account for several, so a near-zero count is suspicious)"
    )
    snap(driver, run_dir, "lessons", "default")
