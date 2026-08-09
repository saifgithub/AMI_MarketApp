"""Locator strategy for a plain-release Flutter app, on Android and iOS.

There is still no `enableFlutterDriverExtension()` anywhere in AMI Trade — this
harness locates elements the way any black-box native test would, against the
same release artifact users get. CR162 added two things to that:

**Identifiers.** The app now sets `Semantics(identifier: …)` on its navigation
surfaces (`mobile/lib/qa/semantics_ids.dart`). Flutter maps that to
`resource-id` on Android and `accessibilityIdentifier` on iOS. Those are
*different Appium strategies*, not one — `AppiumBy.ACCESSIBILITY_ID` means
`content-desc` on Android, so using it there would silently match nothing. Hence
`by_id()` dispatches: `UiSelector().resourceId(...)` on Android,
`ACCESSIBILITY_ID` on iOS.

**Text, still.** Kept because the locale matrix legitimately asserts on rendered
text — that IS the thing under test there. But navigation moved to identifiers,
because text locators coupled navigation to translation: `config/locales.py` had
to carry every EN/AR/MS string verbatim just to tap a tab.

Known gotcha, both platforms: the *first* hierarchy dump right after a screen
transition can come back before Flutter has finished building its semantics
tree. Every lookup here retries with a short backoff rather than failing on one
empty dump.
"""

from __future__ import annotations

import time

from appium.webdriver.common.appiumby import AppiumBy
from appium.webdriver.webdriver import WebDriver
from appium.webdriver.webelement import WebElement
from selenium.common.exceptions import NoSuchElementException

from helpers.platform import is_ios

_RETRY_DELAYS = (0.3, 0.6, 1.0, 1.5, 2.0)  # ~5.4s total, matches waitForSelectorTimeout


def _uiselector(expr: str) -> str:
    return f"new UiSelector().{expr}"


def _predicate_literal(value: str) -> str:
    """Quote a string for an NSPredicate. Backslash and double-quote both need
    escaping, and the app's own copy contains neither today — but a translated
    string one day will, and a locator that breaks on a punctuation mark is the
    kind of failure that gets blamed on the app."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _find_all_with_retry(
    driver: WebDriver, by: str, value: str, *, retry: bool = True
) -> list[WebElement]:
    """`retry=False` skips the ~5.4s backoff. Use it for probes that live inside
    a loop which is ALREADY retrying — otherwise every miss is paid twice, once
    here and once by the caller. The onboarding walk hit this hard: three
    negative probes per turn made an 11-turn interview cost ~440s on iOS, where
    each WebDriverAgent round trip is far slower than UiAutomator2's."""
    delays = (0.0, *_RETRY_DELAYS) if retry else (0.0,)
    last: list[WebElement] = []
    for delay in delays:
        if delay:
            time.sleep(delay)
        last = driver.find_elements(by, value)
        if last:
            return last
    return last


# --------------------------------------------------------------------------
# By identifier — the cross-platform strategy. Prefer this for navigation.
# --------------------------------------------------------------------------


def all_by_id(driver: WebDriver, identifier: str) -> list[WebElement]:
    if is_ios(driver):
        return _find_all_with_retry(driver, AppiumBy.ACCESSIBILITY_ID, identifier)
    # Android: Flutter calls AccessibilityNodeInfo.setViewIdResourceName() with
    # the raw identifier — no `package:id/` prefix — so match it exactly via
    # UiSelector rather than AppiumBy.ID, whose prefixing behaviour varies by
    # driver build.
    return _find_all_with_retry(
        driver, AppiumBy.ANDROID_UIAUTOMATOR, _uiselector(f'resourceId("{identifier}")')
    )


def by_id(driver: WebDriver, identifier: str) -> WebElement:
    elements = all_by_id(driver, identifier)
    if not elements:
        raise NoSuchElementException(
            f"no element with semantics identifier {identifier!r}. If NOTHING "
            f"resolves by id on this run, the build is probably missing "
            f"--dart-define=AMI_QA_SEMANTICS=1 (CR162) rather than missing this "
            f"one element — see tests/test_00_smoke_hierarchy.py."
        )
    return elements[0]


def exists_id(driver: WebDriver, identifier: str) -> bool:
    return bool(all_by_id(driver, identifier))


def wait_visible_id(driver: WebDriver, identifier: str, *, timeout_s: float = 8.0) -> WebElement:
    deadline = time.monotonic() + timeout_s
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            return by_id(driver, identifier)
        except NoSuchElementException as exc:
            last_error = exc
            time.sleep(0.4)
    raise NoSuchElementException(
        f"identifier {identifier!r} never appeared within {timeout_s}s"
    ) from last_error


# --------------------------------------------------------------------------
# By rendered text — for assertions about copy, not for navigation.
# --------------------------------------------------------------------------


def _all_by_text(driver: WebDriver, text: str, *, retry: bool = True) -> list[WebElement]:
    if is_ios(driver):
        lit = _predicate_literal(text)
        return _find_all_with_retry(
            driver,
            AppiumBy.IOS_PREDICATE,
            f"label == {lit} OR name == {lit} OR value == {lit}",
            retry=retry,
        )
    return _find_all_with_retry(
        driver, AppiumBy.ANDROID_UIAUTOMATOR, _uiselector(f'text("{text}")'), retry=retry
    )


def all_by_text(driver: WebDriver, text: str) -> list[WebElement]:
    """Every element with this exact text, not just the first — needed where
    the same string can legitimately appear twice (e.g. Arabic has no case
    distinction, so a translated tab label and a screen heading can collide
    on an identical string where their English/Malay equivalents differ only
    by case). Callers disambiguate by position (see helpers/locale_switch.py
    and tests/test_locale_matrix.py)."""
    return _all_by_text(driver, text)


def by_text(driver: WebDriver, text: str) -> WebElement:
    elements = all_by_text(driver, text)
    if not elements:
        raise NoSuchElementException(f"no element with exact text {text!r}")
    return elements[0]


def by_text_contains(driver: WebDriver, fragment: str) -> WebElement:
    if is_ios(driver):
        lit = _predicate_literal(fragment)
        elements = _find_all_with_retry(
            driver,
            AppiumBy.IOS_PREDICATE,
            f"label CONTAINS {lit} OR name CONTAINS {lit} OR value CONTAINS {lit}",
        )
    else:
        elements = _find_all_with_retry(
            driver, AppiumBy.ANDROID_UIAUTOMATOR, _uiselector(f'textContains("{fragment}")')
        )
    if not elements:
        raise NoSuchElementException(f"no element containing text {fragment!r}")
    return elements[0]


def by_content_desc(driver: WebDriver, desc: str) -> WebElement:
    """Android content-desc / iOS accessibility label. Note this is NOT the
    identifier — see by_id()."""
    if is_ios(driver):
        lit = _predicate_literal(desc)
        elements = _find_all_with_retry(
            driver, AppiumBy.IOS_PREDICATE, f"label CONTAINS {lit}"
        )
    else:
        elements = _find_all_with_retry(
            driver, AppiumBy.ANDROID_UIAUTOMATOR, _uiselector(f'descriptionContains("{desc}")')
        )
    if not elements:
        raise NoSuchElementException(f"no element with content-desc containing {desc!r}")
    return elements[0]


def exists_text(driver: WebDriver, text: str, *, retry: bool = True) -> bool:
    return bool(_all_by_text(driver, text, retry=retry))


def exists_text_contains(driver: WebDriver, fragment: str, *, retry: bool = True) -> bool:
    if is_ios(driver):
        lit = _predicate_literal(fragment)
        return bool(_find_all_with_retry(
            driver,
            AppiumBy.IOS_PREDICATE,
            f"label CONTAINS {lit} OR name CONTAINS {lit} OR value CONTAINS {lit}",
            retry=retry,
        ))
    return bool(_find_all_with_retry(
        driver, AppiumBy.ANDROID_UIAUTOMATOR, _uiselector(f'textContains("{fragment}")'),
        retry=retry,
    ))


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


# --------------------------------------------------------------------------
# Structural queries, used by the two mechanical checks in helpers/layout.py
# --------------------------------------------------------------------------

_IOS_INTERACTIVE_TYPES = (
    "XCUIElementTypeButton",
    "XCUIElementTypeLink",
    "XCUIElementTypeTextField",
    "XCUIElementTypeSecureTextField",
    "XCUIElementTypeSwitch",
)


def interactive_elements(driver: WebDriver, *, labelled_only: bool = False) -> list[WebElement]:
    """Every tappable node in the current hierarchy — the pool the nav-bar /
    bottom-inset and scroll-overflow checks scan for offending bounds.

    Android has a single `clickable` flag. iOS has no equivalent, so this
    approximates it by element type: Flutter semantics nodes carrying
    `button: true` surface as XCUIElementTypeButton, text fields as
    XCUIElementTypeTextField, and so on.

    `labelled_only` filters to elements that carry a label. On iOS that happens
    inside the predicate — one round trip instead of one per candidate, which
    matters because WebDriverAgent attribute reads dominate the onboarding
    walk's runtime."""
    if is_ios(driver):
        types = " OR ".join(f'type == "{t}"' for t in _IOS_INTERACTIVE_TYPES)
        predicate = f"({types}) AND visible == 1"
        if labelled_only:
            predicate += ' AND label != "" AND label != nil'
        return _find_all_with_retry(driver, AppiumBy.IOS_PREDICATE, predicate)
    selector = "clickable(true)"
    return _find_all_with_retry(
        driver, AppiumBy.ANDROID_UIAUTOMATOR, _uiselector(selector)
    )


def element_description(driver: WebDriver, element: WebElement) -> str:
    """A human-readable handle for an element, for report output.

    The attribute names are NOT shared: asking XCUITest for `content-desc`
    returns HTTP 500 from WebDriverAgent (it validates against a fixed
    attribute list) rather than an empty string, so this cannot be one call
    with a fallback — it has to dispatch."""
    text = (element.text or "").strip()
    if text:
        return text
    attribute = "label" if is_ios(driver) else "content-desc"
    return (element.get_attribute(attribute) or "").strip() or "<unlabeled>"


def is_text_input(driver: WebDriver, element: WebElement) -> bool:
    """Same story as element_description: `class` is an Android attribute,
    `type` is the iOS one."""
    if is_ios(driver):
        kind = element.get_attribute("type") or ""
        return kind in ("XCUIElementTypeTextField", "XCUIElementTypeSecureTextField")
    return "EditText" in (element.get_attribute("class") or "")


def scrollable_exists(driver: WebDriver) -> bool | None:
    """Does a scrollable container exist in the current hierarchy?

    Returns True/False on Android, where `UiSelector().scrollable(true)` is
    authoritative.

    On iOS returns True or **None** — never False. `None` means *undetermined*,
    and helpers/layout.py records that in the finding rather than treating it as
    a negative. A False here would manufacture scroll-overflow findings on
    screens that scroll perfectly well, which is exactly the kind of confident
    wrong answer this project's degrade-loudly rule exists to prevent.

    **Evidence so far (2026-08-10, first live Simulator run):** Flutter *does*
    emit `XCUIElementTypeScrollView` — the Concierge interview screen showed 4
    of them, for its transcript list and horizontal chip row. So the positive
    signal is real and `True` is trustworthy.

    What is still unproven is the negative: one screen showing scroll views does
    not establish that *every* scrollable surfaces as one, and that is the claim
    a `False` would rest on. Tighten this only after a run across several known-
    scrolling screens shows the mapping holds — with evidence, not by assuming.
    """
    if is_ios(driver):
        found = _find_all_with_retry(
            driver, AppiumBy.IOS_PREDICATE, 'type == "XCUIElementTypeScrollView"'
        )
        return True if found else None
    return bool(
        _find_all_with_retry(
            driver, AppiumBy.ANDROID_UIAUTOMATOR, _uiselector("scrollable(true)")
        )
    )
