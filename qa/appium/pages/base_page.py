"""Shared navigation + layout helpers. home_shell.dart's bottom nav is an
IndexedStack switched by local setState (not routed) — tabs are just taps on
visible text, there's no deep link to assert against."""

from __future__ import annotations

from helpers.gestures import Band, tap_element
from helpers.locators import exists_text, exists_text_contains, wait_visible_text

TAB_LABELS = ("Floor", "Portfolio", "Journal", "Lessons", "Settings")

# home_shell.dart mounts an always-animating TickerTape strip under the top
# app bar on every tab. Excluding a fixed top/bottom margin from any swipe/diff
# band keeps that animation from reading as false "the screen moved" —
# see helpers/layout.py's swipe_moved docstring.
TOP_CHROME_PX = 220
BOTTOM_NAV_PX = 160


def open_tab(driver, tab_label: str) -> None:
    assert tab_label in TAB_LABELS, f"{tab_label!r} is not a known bottom-nav tab: {TAB_LABELS}"
    element = wait_visible_text(driver, tab_label)
    tap_element(driver, element)


def content_band(device: dict, *, top_px: int = TOP_CHROME_PX, bottom_px: int = BOTTOM_NAV_PX) -> Band:
    """A swipe/diff region that excludes the animated top chrome and the
    bottom nav bar, scaled to the live device's own display size + nav-bar
    read rather than a hardcoded resolution."""
    width, height = device["display"]
    top = top_px
    bottom = min(device["navbar_top_y"], height - bottom_px)
    return (0, top, width, max(bottom - top, 0))


def probe_content(driver, screen: str, *, exact: tuple[str, ...] = (), contains: tuple[str, ...] = ()) -> dict[str, bool]:
    """Check a batch of real in-app strings and print one line per result.

    This is depth, not a pass/fail gate on its own: some of these strings
    only appear once specific data exists (a drawdown once a trade has
    happened, an empty-state title only with zero entries) or need a scroll
    to reach (a long Settings screen). The caller decides which results are
    safe to hard-assert (content that's structurally guaranteed at the top
    of the screen, no scroll/data needed) versus which are just logged for a
    human reviewing the report — see each tests/test_*.py call site for
    which is which and why.
    """
    results: dict[str, bool] = {}
    for label in exact:
        found = exists_text(driver, label)
        results[label] = found
        print(f"    [{screen}] {'✓' if found else '·'} {label!r}")
    for label in contains:
        found = exists_text_contains(driver, label)
        results[label] = found
        print(f"    [{screen}] {'✓' if found else '·'} contains {label!r}")
    return results
