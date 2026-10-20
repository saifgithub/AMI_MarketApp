"""Floor > YOUR FIRM navigation shared by the FLOOR and BRIEF journeys (CR263)."""

from __future__ import annotations

import time

from helpers.journeys import scroll_down, scroll_up
from helpers.locators import _all_by_text_contains, wait_visible_text, wait_visible_text_contains
from pages.base_page import open_tab


def open_your_firm(driver) -> None:
    open_tab(driver, "Floor")
    scroll_up(driver, times=3)  # the Floor keeps its scroll offset between visits
    time.sleep(0.8)
    wait_visible_text(driver, "CONVENE THE ROOM", timeout_s=15)
    # The row's node exists (zero-sized) before it is on screen, so "found" is not
    # "visible": scroll until it has a real rect, then wait for it to stop moving
    # (a tap during the fling lands on whatever scrolled under the finger).
    last = None
    els = []
    for _ in range(24):
        time.sleep(0.7)
        els = [e for e in _all_by_text_contains(driver, "YOUR FIRM", retry=False) if e.rect["height"] > 0]
        y = els[0].rect["y"] if els else None
        if y is None:
            scroll_down(driver)
        elif y == last:
            break
        last = y
    assert els, "the YOUR FIRM row never came on screen"
    els[0].click()
    wait_visible_text_contains(driver, "unlocked. Tap a locked hex", timeout_s=15)
