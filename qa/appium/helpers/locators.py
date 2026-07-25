"""Locator strategy for a plain-release Flutter app under UiAutomator2.

No enableFlutterDriverExtension() anywhere in AMI Trade — there is no
semantics/driver-extension build to lean on, so this harness locates elements
the same way any black-box native-Android test would: by their rendered
text first (Flutter exposes Text/RichText content to the Android
accessibility tree once an accessibility client interrogates the window —
UiAutomator2's own server is such a client), then content-desc, then
"some clickable thing in this region" as a last resort.

Known gotcha: the *first* hierarchy dump right after a screen transition can
come back before Flutter has finished building its semantics tree. Every
lookup here retries with a short backoff rather than failing on one empty
dump.
"""

from __future__ import annotations

import time

from appium.webdriver.common.appiumby import AppiumBy
from appium.webdriver.webdriver import WebDriver
from appium.webdriver.webelement import WebElement
from selenium.common.exceptions import NoSuchElementException

_RETRY_DELAYS = (0.3, 0.6, 1.0, 1.5, 2.0)  # ~5.4s total, matches waitForSelectorTimeout


def _uiselector(expr: str) -> str:
    return f"new UiSelector().{expr}"


def _find_all_with_retry(driver: WebDriver, expr: str) -> list[WebElement]:
    last: list[WebElement] = []
    for delay in (0.0, *_RETRY_DELAYS):
        if delay:
            time.sleep(delay)
        last = driver.find_elements(AppiumBy.ANDROID_UIAUTOMATOR, _uiselector(expr))
        if last:
            return last
    return last


def by_text(driver: WebDriver, text: str) -> WebElement:
    elements = _find_all_with_retry(driver, f'text("{text}")')
    if not elements:
        raise NoSuchElementException(f"no element with exact text {text!r}")
    return elements[0]


def by_text_contains(driver: WebDriver, fragment: str) -> WebElement:
    elements = _find_all_with_retry(driver, f'textContains("{fragment}")')
    if not elements:
        raise NoSuchElementException(f"no element containing text {fragment!r}")
    return elements[0]


def by_content_desc(driver: WebDriver, desc: str) -> WebElement:
    elements = _find_all_with_retry(driver, f'descriptionContains("{desc}")')
    if not elements:
        raise NoSuchElementException(f"no element with content-desc containing {desc!r}")
    return elements[0]


def all_by_text(driver: WebDriver, text: str) -> list[WebElement]:
    """Every element with this exact text, not just the first — needed where
    the same string can legitimately appear twice (e.g. Arabic has no case
    distinction, so a translated tab label and a screen heading can collide
    on an identical string where their English/Malay equivalents differ only
    by case). Callers disambiguate by position (see helpers/locale_switch.py
    and tests/test_locale_matrix.py)."""
    return _find_all_with_retry(driver, f'text("{text}")')


def exists_text(driver: WebDriver, text: str) -> bool:
    try:
        by_text(driver, text)
        return True
    except NoSuchElementException:
        return False


def exists_text_contains(driver: WebDriver, fragment: str) -> bool:
    try:
        by_text_contains(driver, fragment)
        return True
    except NoSuchElementException:
        return False


def wait_visible_text(driver: WebDriver, text: str, *, timeout_s: float = 8.0) -> WebElement:
    deadline = time.monotonic() + timeout_s
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            return by_text(driver, text)
        except NoSuchElementException as exc:
            last_error = exc
            time.sleep(0.4)
    raise NoSuchElementException(f"text {text!r} never appeared within {timeout_s}s") from last_error


def interactive_elements(driver: WebDriver) -> list[WebElement]:
    """Every clickable node in the current hierarchy — the pool nav-bar-overlap
    and scroll-overflow checks scan for offending bounds."""
    return _find_all_with_retry(driver, "clickable(true)")


def scrollable_exists(driver: WebDriver) -> bool:
    return bool(_find_all_with_retry(driver, "scrollable(true)"))
