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
import re
import time

from helpers import lesson_steps
from helpers.journeys import go_back, settle, tap_button, tap_contains
from helpers.locators import exists_text, exists_text_contains, interactive_elements, wait_visible_text, wait_visible_text_contains
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


_PROGRESS = re.compile(r"(\d+)\s*/\s*(\d+)\s*lessons")
_TRACK = re.compile(r"^([A-Z][A-Z &]+)\n(\d+)/(\d+)$")


def _completed_count(driver) -> int:
    for n in lesson_steps.nodes(driver):
        m = _PROGRESS.search(n.label)
        if m:
            return int(m.group(1))
    raise AssertionError("the Lessons landing shows no 'N / M lessons' progress counter")


def _smallest_open_track(driver) -> str:
    """The track with the fewest lessons left (the cheapest to open) that still has
    one. Track names are catalogue content, so none is hard-coded."""
    best = None
    for n in lesson_steps.nodes(driver):
        m = _TRACK.match(n.label)
        if m and int(m.group(2)) < int(m.group(3)):
            left = int(m.group(3)) - int(m.group(2))
            if best is None or left < best[0]:
                best = (left, m.group(1))
    assert best, "every lesson in every track is already complete - nothing left to open"
    return best[1]


@pytest.mark.uat("UAT-LESS-010")
def test_read_a_lesson_and_pass_its_quiz_and_progress_rises(driver, run_dir):
    open_tab(driver, "Lessons")
    wait_visible_text(driver, "YOUR PROGRESS", timeout_s=15)
    settle(driver, 1.5)
    before = _completed_count(driver)
    track = _smallest_open_track(driver)
    print(f"    [lessons] {before} complete; opening {track}")

    tap_contains(driver, track)
    time.sleep(2.0)
    # the first READ button is the first lesson not yet passed (completed lessons drop out of the list)
    tap_button(driver, "READ", timeout_s=15)
    time.sleep(3.0)

    scrolls = lesson_steps.read_to_end(driver)
    assert scrolls >= 1, "the lesson was not long enough to scroll - is the body empty?"
    snap(driver, run_dir, "lesson", "end_of_body")
    submits = lesson_steps.pass_quiz(driver)
    print(f"    [lessons] passed after {submits} submit(s)")
    scroll_to_verdict = 0
    while not exists_text_contains(driver, "PASSED", retry=False) and scroll_to_verdict < 6:
        lesson_steps.scroll_down(driver)
        scroll_to_verdict += 1
    assert exists_text_contains(driver, "PASSED", retry=False), "the reader never showed PASSED"
    snap(driver, run_dir, "lesson", "passed")

    # leave the reader, then the track page, and read the counter on the landing
    if exists_text_contains(driver, "BACK TO LESSONS", retry=False):
        tap_button(driver, "BACK TO LESSONS", timeout_s=5)
    else:
        go_back(driver)
    time.sleep(1.5)
    open_tab(driver, "Lessons")
    deadline = time.monotonic() + 20
    after = before
    while time.monotonic() < deadline:
        time.sleep(1.5)
        try:
            after = _completed_count(driver)
        except AssertionError:
            go_back(driver)
            continue
        if after > before:
            break
    snap(driver, run_dir, "lesson", "progress")
    assert after == before + 1, f"progress should rise by one lesson: {before} -> {after}"
