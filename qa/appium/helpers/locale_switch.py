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

from selenium.common.exceptions import NoSuchElementException

from config.locales import LOCALES
from helpers.gestures import tap_element
from helpers.locators import wait_visible_text


def open_settings_any_locale(driver, *, timeout_s: float = 3.0) -> None:
    last_error: Exception | None = None
    for profile in LOCALES.values():
        try:
            element = wait_visible_text(driver, profile.tab_labels["Settings"], timeout_s=timeout_s)
            tap_element(driver, element)
            return
        except NoSuchElementException as exc:
            last_error = exc
    tried = [p.tab_labels["Settings"] for p in LOCALES.values()]
    raise NoSuchElementException(f"Settings tab not found under any known locale label: {tried}") from last_error


def switch_locale(driver, target_code: str) -> None:
    target = LOCALES[target_code]
    open_settings_any_locale(driver)
    row = wait_visible_text(driver, target.switcher_native_name, timeout_s=8)
    tap_element(driver, row)
    # Confirms the switch actually landed before any caller starts asserting
    # translated content — same screen, so the heading itself re-renders.
    wait_visible_text(driver, target.strings["settings_heading"], timeout_s=8)
