"""Shared navigation + layout helpers. home_shell.dart's bottom nav is an
IndexedStack switched by local setState (not routed) — tabs are just taps on
visible destinations, there's no deep link to assert against.

CR162: navigation goes through `Semantics(identifier:)` now, not rendered text.
The old text path is kept as a loud fallback, not as an equal option — see
`open_tab`.
"""

from __future__ import annotations

from config.locales import LOCALES
from config.semantics_ids import NAV_IDS
from helpers.gestures import Band, tap_element
from helpers.locators import (
    exists_text,
    exists_text_contains,
    wait_visible_id,
    wait_visible_text,
)
from helpers.platform import IOS
from selenium.common.exceptions import NoSuchElementException

TAB_LABELS = ("Floor", "Portfolio", "Lessons", "You")  # CR133 — Journal and Settings are segments of You now

# home_shell.dart mounts an always-animating TickerTape strip under the top
# app bar on every tab. Excluding a fixed top/bottom margin from any swipe/diff
# band keeps that animation from reading as false "the screen moved" —
# see helpers/layout.py's swipe_moved docstring.
#
# Android: pixels, measured against the Galaxy A17 under CR080. Unchanged.
TOP_CHROME_PX = 220
BOTTOM_NAV_PX = 160

# iOS: POINTS, and PROVISIONAL until a live run measures them (CR162). Chosen
# deliberately generous rather than tight: if the band accidentally *includes*
# the TickerTape, every screen reads as "it moved" and every real scroll-overflow
# finding is silently suppressed. Over-excluding only narrows the probe, which
# fails loudly as a missed region; under-excluding fails silently as a clean
# report. Bias toward the loud failure.
TOP_CHROME_PT = 150
BOTTOM_NAV_PT = 100


def open_tab(driver, tab_label: str, *, locale: str = "en") -> None:
    """`tab_label` is always one of the English TAB_LABELS keys — a locale-
    independent semantic identifier, not literal on-screen text.

    Resolves by `Semantics(identifier:)` first, which is locale-independent on
    both platforms. `locale` only matters for the fallback path, which exists
    for one reason: an APK/IPA built before CR162 has no identifiers, and the
    melehost rig has shipped stale builds before (DEF224). Falling back
    silently would hide exactly that, so it announces itself.
    """
    assert tab_label in TAB_LABELS, f"{tab_label!r} is not a known bottom-nav tab: {TAB_LABELS}"
    try:
        tap_element(driver, wait_visible_id(driver, NAV_IDS[tab_label], timeout_s=4.0))
        return
    except NoSuchElementException:
        pass

    print(
        f"WARNING: nav tab {tab_label!r} did not resolve by semantics identifier "
        f"({NAV_IDS[tab_label]}) — falling back to text. The build under test is "
        f"probably older than CR162, or was built without "
        f"--dart-define=AMI_QA_SEMANTICS=1. Check the build before trusting this run."
    )
    display_text = LOCALES[locale].tab_labels[tab_label]
    tap_element(driver, wait_visible_text(driver, display_text))


def content_band(device: dict, *, top_px: int | None = None, bottom_px: int | None = None) -> Band:
    """A swipe/diff region that excludes the animated top chrome and the
    bottom nav bar, scaled to the live device's own display size + bottom-inset
    read rather than a hardcoded resolution.

    Units follow the driver's coordinate space: pixels on Android, points on
    iOS."""
    width, height = device["display"]
    is_ios = device.get("platform") == IOS
    top = top_px if top_px is not None else (TOP_CHROME_PT if is_ios else TOP_CHROME_PX)
    bottom_margin = bottom_px if bottom_px is not None else (BOTTOM_NAV_PT if is_ios else BOTTOM_NAV_PX)
    bottom = min(device["navbar_top_y"], height - bottom_margin)
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
