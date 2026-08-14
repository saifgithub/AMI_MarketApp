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

import re
import time

from appium.webdriver.common.appiumby import AppiumBy
from appium.webdriver.webdriver import WebDriver
from appium.webdriver.webelement import WebElement
from selenium.common.exceptions import NoSuchElementException, WebDriverException

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
    return _find_any_with_retry(driver, ((by, value),), retry=retry)


def _find_any_with_retry(
    driver: WebDriver, queries: tuple[tuple[str, str], ...], *, retry: bool = True
) -> list[WebElement]:
    """First non-empty result across several equivalent queries, sharing ONE
    backoff ladder between them.

    The sharing is the point. Android needs two selectors to answer "is this
    string on screen?" (see `_all_by_text`), and running them as two separate
    `_find_all_with_retry` calls would pay the ~5.4s ladder twice on every
    miss — turning a fix for one slow path into a slower one."""
    delays = (0.0, *_RETRY_DELAYS) if retry else (0.0,)
    for delay in delays:
        if delay:
            time.sleep(delay)
        for by, value in queries:
            found = driver.find_elements(by, value)
            if found:
                return found
    return []


def _uiselector_literal(value: str) -> str:
    """Escape a string for embedding in a UiSelector Java-source expression.

    The Android counterpart of `_predicate_literal`, and absent for the same
    reason it was nearly absent there: none of the app's current copy contains
    a quote or backslash. A translated string eventually will, and an
    unescaped one does not raise — it produces a malformed selector that finds
    nothing, which reads as a missing element."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


# --------------------------------------------------------------------------
# By identifier — the cross-platform strategy. Prefer this for navigation.
# --------------------------------------------------------------------------


def all_by_id(driver: WebDriver, identifier: str, *, retry: bool = True) -> list[WebElement]:
    if is_ios(driver):
        return _find_all_with_retry(
            driver, AppiumBy.ACCESSIBILITY_ID, identifier, retry=retry
        )
    # Android: Flutter calls AccessibilityNodeInfo.setViewIdResourceName() with
    # the raw identifier — no `package:id/` prefix — so match it exactly via
    # UiSelector rather than AppiumBy.ID, whose prefixing behaviour varies by
    # driver build.
    return _find_all_with_retry(
        driver,
        AppiumBy.ANDROID_UIAUTOMATOR,
        _uiselector(f'resourceId("{_uiselector_literal(identifier)}")'),
        retry=retry,
    )


def by_id(driver: WebDriver, identifier: str, *, retry: bool = True) -> WebElement:
    elements = all_by_id(driver, identifier, retry=retry)
    if not elements:
        raise NoSuchElementException(
            f"no element with semantics identifier {identifier!r}. If NOTHING "
            f"resolves by id on this run, the build is probably missing "
            f"--dart-define=AMI_QA_SEMANTICS=1 (CR162) rather than missing this "
            f"one element — see tests/test_00_smoke_hierarchy.py."
        )
    return elements[0]


def exists_id(driver: WebDriver, identifier: str, *, retry: bool = True) -> bool:
    """`retry=False` for callers that own their own polling loop — same reason
    as `exists_text`'s: a nested backoff turns their timeout into a floor."""
    return bool(all_by_id(driver, identifier, retry=retry))


def wait_visible_id(driver: WebDriver, identifier: str, *, timeout_s: float = 8.0) -> WebElement:
    """Poll until `identifier` resolves or `timeout_s` elapses. `retry=False`
    on the inner lookup for the same reason as `wait_visible_text` — this loop
    owns the deadline, and a nested backoff makes the timeout a floor."""
    deadline = time.monotonic() + timeout_s
    while True:
        elements = all_by_id(driver, identifier, retry=False)
        if elements:
            return elements[0]
        if time.monotonic() >= deadline:
            raise NoSuchElementException(
                f"identifier {identifier!r} never appeared within {timeout_s}s"
            )
        time.sleep(0.4)


# --------------------------------------------------------------------------
# By rendered text — for assertions about copy, not for navigation.
# --------------------------------------------------------------------------


def _all_by_text(driver: WebDriver, text: str, *, retry: bool = True) -> list[WebElement]:
    """Elements whose *user-perceivable* string equals `text`.

    On Android that means BOTH `text` and `content-desc`, and getting this
    wrong is invisible rather than loud. Flutter's Android engine maps a
    `Semantics(label:)` onto `AccessibilityNodeInfo.setContentDescription()`,
    NOT `setText()` — so in an app that paints to a canvas, essentially every
    string a user reads lives in `content-desc` and a `text()`-only selector
    matches nothing. Measured on the rig device with the app sitting on Floor:
    the tree contained `content-desc='FLOOR'`, and `exists_text('FLOOR')`
    returned False.

    That is what made the smoke gate's `test_bottom_nav_text_resolves` and
    `ensure_onboarded`'s early-return probe unsatisfiable on Android: the
    string was on screen, in the tree, and unfindable. Both selectors share one
    backoff ladder via `_find_any_with_retry`, so a miss costs what it did
    before rather than double."""
    if is_ios(driver):
        lit = _predicate_literal(text)
        return _find_all_with_retry(
            driver,
            AppiumBy.IOS_PREDICATE,
            f"label == {lit} OR name == {lit} OR value == {lit}",
            retry=retry,
        )
    lit = _uiselector_literal(text)
    return _find_any_with_retry(
        driver,
        (
            # description first: in a Flutter app it is the overwhelmingly
            # common case, so the hit path is one round trip.
            (AppiumBy.ANDROID_UIAUTOMATOR, _uiselector(f'description("{lit}")')),
            (AppiumBy.ANDROID_UIAUTOMATOR, _uiselector(f'text("{lit}")')),
        ),
        retry=retry,
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


def _all_by_text_contains(
    driver: WebDriver, fragment: str, *, retry: bool = True
) -> list[WebElement]:
    """Substring form of `_all_by_text`, and it searches `content-desc` on
    Android for exactly the same reason — see that function."""
    if is_ios(driver):
        lit = _predicate_literal(fragment)
        return _find_all_with_retry(
            driver,
            AppiumBy.IOS_PREDICATE,
            f"label CONTAINS {lit} OR name CONTAINS {lit} OR value CONTAINS {lit}",
            retry=retry,
        )
    lit = _uiselector_literal(fragment)
    return _find_any_with_retry(
        driver,
        (
            (AppiumBy.ANDROID_UIAUTOMATOR, _uiselector(f'descriptionContains("{lit}")')),
            (AppiumBy.ANDROID_UIAUTOMATOR, _uiselector(f'textContains("{lit}")')),
        ),
        retry=retry,
    )


def by_text_contains(driver: WebDriver, fragment: str) -> WebElement:
    elements = _all_by_text_contains(driver, fragment)
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
    return bool(_all_by_text_contains(driver, fragment, retry=retry))


def wait_visible_text(driver: WebDriver, text: str, *, timeout_s: float = 8.0) -> WebElement:
    """Poll until `text` appears or `timeout_s` elapses.

    `retry=False` on the inner lookup is load-bearing, not a micro-optimisation.
    This function OWNS the deadline; letting the lookup run its own ~5.4s
    backoff as well means one "attempt" outlives the whole budget, so the
    caller's timeout becomes a floor instead of a ceiling. Measured on the rig
    device: a miss took 7.65s against `timeout_s=2` (0.37s with retry off), and
    the onboarding walk paid that on every negative probe of every turn."""
    deadline = time.monotonic() + timeout_s
    while True:
        elements = _all_by_text(driver, text, retry=False)
        if elements:
            return elements[0]
        if time.monotonic() >= deadline:
            raise NoSuchElementException(
                f"text {text!r} never appeared within {timeout_s}s"
            )
        time.sleep(0.4)


def scrollable_bounds(driver: WebDriver) -> tuple[int, int, int, int] | None:
    """The on-screen box of the first scrollable container, or None.

    Scroll gestures need to be aimed at the thing that scrolls. `content_band`
    is a *diff* region — it deliberately spans from under the top chrome to
    above the system nav, which on this app includes the bottom nav bar and the
    horizontally-scrolling TickerTape. Aiming a scroll there can drive the
    wrong scrollable or nothing at all.

    Measured on the rig: the SETTINGS pane reports `[0,286][720,1277]`, while
    `content_band` yields y 220..1400 — 123px of which is other widgets.

    Android only; None on iOS, where callers fall back to the band.
    """
    if is_ios(driver):
        return None
    match = re.search(
        r'scrollable="true"[^>]*?bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
        driver.page_source,
    )
    if not match:
        return None
    x1, y1, x2, y2 = (int(g) for g in match.groups())
    return (x1, y1, x2 - x1, y2 - y1)


def wait_visible_text_contains(
    driver: WebDriver, fragment: str, *, timeout_s: float = 8.0
) -> WebElement:
    """Poll until some node's label CONTAINS `fragment`.

    This is the right wait for a section heading, and exact-match is the wrong
    one — which is not obvious and cost a debugging round. Flutter merges a
    section's descendants into one semantics node, so the heading is a
    *substring* of a label, never a label. Measured on the rig, SETTINGS' first
    section comes back as one node reading:

        'MY MANDATE\\nRisk score\\n3 / 5\\nBalanced. Standard 3-5% positions.…'

    so `wait_visible_text(driver, "MY MANDATE")` can never match however
    correctly the screen renders. Same shape on Portfolio
    ('SIM PORTFOLIO\\n$10,000\\n…') and on the ticker tape.

    Use exact-match for things that are their own node — a button label, a nav
    tab, a chip. Use this for anything a section wraps.
    """
    deadline = time.monotonic() + timeout_s
    while True:
        elements = _all_by_text_contains(driver, fragment, retry=False)
        if elements:
            return elements[0]
        if time.monotonic() >= deadline:
            raise NoSuchElementException(
                f"no element's text contained {fragment!r} within {timeout_s}s"
            )
        time.sleep(0.4)


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

    `labelled_only` filters to elements that carry a label. It is honoured on
    BOTH platforms, but by different mechanisms, and that asymmetry is the
    whole point of this docstring:

    - **iOS** filters server-side, inside the predicate — one round trip
      instead of one per candidate, which matters because WebDriverAgent
      attribute reads dominate the onboarding walk's runtime.
    - **Android** filters client-side. UiSelector has no "carries any label"
      predicate (`descriptionMatches` would miss nodes labelled via `text`
      instead of `content-desc`, and Flutter emits both depending on the
      widget), and UiAutomator2 attribute reads are cheap enough that the
      per-candidate cost which forced the iOS design does not apply here.

    This was added iOS-only and shipped that way (82a54433, CR162). On Android
    the keyword argument was accepted and silently ignored, so the function
    returned every clickable node while its caller believed it had received
    only labelled ones. `helpers/onboarding.py::_live_chip` picks the
    bottom-most candidate and documents *by name* that the unlabelled
    send-arrow beside the text field is excluded by this filter — on Android it
    was not, the arrow sits below the chip row, and the Concierge walk spent
    its entire 120s budget tapping send on an empty field. Measured on the rig
    device: 5 candidates returned for both `labelled_only=True` and `False`.

    A silently-ignored keyword argument is worse than an unsupported one — the
    caller's guard reads as present in the source and is absent at runtime. If
    a future platform cannot support this, raise rather than degrade."""
    if is_ios(driver):
        types = " OR ".join(f'type == "{t}"' for t in _IOS_INTERACTIVE_TYPES)
        predicate = f"({types}) AND visible == 1"
        if labelled_only:
            predicate += ' AND label != "" AND label != nil'
        return _find_all_with_retry(driver, AppiumBy.IOS_PREDICATE, predicate)
    elements = _find_all_with_retry(
        driver, AppiumBy.ANDROID_UIAUTOMATOR, _uiselector("clickable(true)")
    )
    if not labelled_only:
        return elements
    return [element for element in elements if _android_label(element)]


def _android_label(element: WebElement) -> str:
    """Whatever text a user would perceive on this node, or "".

    Flutter's Android engine puts a `Semantics(label:)` into `content-desc`,
    but a plain `Text` inside a tappable renders as the node's `text` instead —
    so both have to be read, and reading only one is how a labelled chip gets
    classified as unlabelled chrome."""
    try:
        return (element.get_attribute("content-desc") or element.text or "").strip()
    except WebDriverException:
        # The node went stale between the query and this read — a transient
        # mid-animation race, and treating it as unlabelled just drops it from
        # this pass rather than failing the caller.
        return ""


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
