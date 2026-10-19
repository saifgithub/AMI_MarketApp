"""In-app language switch (A11, mobile/lib/i18n/locale_provider.dart) — taps
Settings -> Language, the same control a real user has. This changes
app-level locale state persisted via SharedPreferences, NOT the device/OS
locale — no device locale pinning, no app relaunch: Riverpod's
localeNotifierProvider drives MaterialApp directly, so the whole tree
re-renders in the new language immediately.

Deliberately does not assume which locale the app is currently rendering in:
a locale-parametrized test suite has no guaranteed run order between test
functions, so the Settings tab must be locatable regardless of prior state.
"""

from __future__ import annotations

import time

from selenium.common.exceptions import NoSuchElementException

from config.locales import LOCALES
from helpers.gestures import Band, swipe_down, swipe_up, tap_element
from helpers.locators import exists_text, exists_text_contains, wait_visible_text
from helpers.shell import tree_is_dark
from pages.base_page import open_you_segment

_MAX_SCROLLS = 25


def open_settings_any_locale(driver) -> None:
    """YOU tab -> SETTINGS segment, by semantics identifier — locale-independent.

    CR133 moved Settings off the bottom nav into a segment of YOU; the old
    per-locale `tab_labels["Settings"]` text probe raised KeyError and, even if
    it had resolved, matched nothing."""
    open_you_segment(driver, "Settings")


def _pane_band(driver) -> Band:
    size = driver.get_window_size()
    width, height = size["width"], size["height"]
    return (0, int(height * 0.25), width, int(height * 0.5))


def _scroll_until(driver, band: Band, found, *, steps: int, up: bool) -> bool:
    """Small drags, checking after each — a big one flings past a section whose
    row only exists in the tree while it is on screen."""
    for i in range(steps):
        if found():
            return True
        if tree_is_dark(driver):
            raise RuntimeError(
                "the iOS accessibility tree went empty while scrolling the "
                "Settings pane (reproduced when the PROFILE section — Display "
                "name field — scrolls into view; it stays empty until the app "
                "is relaunched). App-side defect, not a missing Language row."
            )
        (swipe_up if up else swipe_down)(driver, band, percent=0.3)
        time.sleep(0.5)
    return found()


def switch_locale(driver, target_code: str) -> None:
    target = LOCALES[target_code]
    open_settings_any_locale(driver)
    band = _pane_band(driver)
    row_visible = lambda: exists_text(driver, target.switcher_native_name, retry=False)
    # The Language row is mid-pane in a lazily built list, so it is only in the
    # tree while on screen, and `noReset=True` keeps the list offset alive across
    # sessions — it may start above or below the section. Search both ways.
    if not (
        _scroll_until(driver, band, row_visible, steps=_MAX_SCROLLS, up=False)
        or _scroll_until(driver, band, row_visible, steps=_MAX_SCROLLS, up=True)
    ):
        raise NoSuchElementException(
            f"Language row {target.switcher_native_name!r} not found in Settings"
        )
    tap_element(driver, wait_visible_text(driver, target.switcher_native_name, timeout_s=8))
    # Back to the pane's start: MY MANDATE is its first section, and the list
    # offset survives the locale switch. CONTAINS, not exact — Flutter merges the
    # section into one semantics node. This also confirms the switch landed: the
    # segment is embedded in YOU, so there is no SETTINGS heading, and the
    # segment label is on screen before the switch; the MANDATE section is what
    # re-renders in the new language.
    mandate = target.strings["settings_mandate"]
    if not _scroll_until(
        driver, band, lambda: exists_text_contains(driver, mandate, retry=False),
        steps=_MAX_SCROLLS, up=False,
    ):
        raise NoSuchElementException(f"{mandate!r} not found after switching to {target_code!r}")
