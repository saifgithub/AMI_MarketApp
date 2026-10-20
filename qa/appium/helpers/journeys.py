"""Shared steps for the CR263 user-journey tests (tests/test_journey_*.py and the
journey files named after an area).

Why this exists: every journey taps the same handful of things — a button by its
label, a text field by its label, a sheet's scrim, the keyboard's Done key — and
each of those has an iOS/Android difference that the Phase 1 tests never had to
cross (they only read). Putting the difference here, once, keeps the journeys
reading as what the USER does.

Verified on the iOS Simulator (iPhone 17). The Android branches follow the same
locator rules `helpers/locators.py` documents (content-desc / text, UiSelector)
but have not been run on the rig in this change.

Hard-won facts, so they are not re-learnt:
- Flutter sheets are not dismissed by `driver.back()` on iOS (a silent no-op).
  The sheet's `Scrim` node is tappable and closes it; on Android back works.
- A text field's keyboard has a `Done` key on iOS; the numeric/decimal pads do
  not. Tapping SUBMIT / Create while the decimal pad is up still lands (the
  button's node is on screen), so numeric fields are filled last.
- A swipe that STARTS on a text field focuses it instead of scrolling, so drags
  start from the middle band and are expressed as fractions of the window.
- iOS accessibility tree can drop to an empty skeleton (see shell.tree_is_dark);
  `settle()` relaunches rather than letting every locator miss.
"""

from __future__ import annotations

import re
import time

from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import NoSuchElementException, WebDriverException

from config.locales import LOCALES
from config.semantics_ids import NAV_BACK, NAV_IDS, TRADE_TICKET_CANCEL  # noqa: F401
from helpers.gestures import hide_keyboard_if_shown
from helpers.locators import (
    _all_by_text,
    _all_by_text_contains,
    all_by_id,
    by_text,
    element_description,
    exists_id,
    exists_text,
    exists_text_contains,
    wait_visible_id,
    wait_visible_text,
    wait_visible_text_contains,
)
from helpers.onboarding import _app_id
from helpers.platform import is_ios
from helpers.shell import relaunch_if_dark, shell_is_up

_MONEY = re.compile(r"^⁦?\$?(-?[\d,]+(?:\.\d+)?)⁩?$")


# --------------------------------------------------------------------- waits


def settle(driver, seconds: float = 1.0) -> None:
    """Pause, then make sure the accessibility tree is not the dark skeleton."""
    time.sleep(seconds)
    app_id = _app_id(driver)
    if app_id:
        relaunch_if_dark(driver, app_id, why="journey step")


def wait_any_text(driver, texts, *, timeout_s: float, contains: bool = False) -> str:
    """Poll until any of `texts` is on screen; return which one. Raises
    NoSuchElementException naming all of them on timeout."""
    deadline = time.monotonic() + timeout_s
    while True:
        for text in texts:
            found = (
                exists_text_contains(driver, text, retry=False)
                if contains
                else exists_text(driver, text, retry=False)
            )
            if found:
                return text
        if time.monotonic() >= deadline:
            raise NoSuchElementException(f"none of {list(texts)} appeared within {timeout_s}s")
        time.sleep(0.5)


def wait_gone_text(driver, text: str, *, timeout_s: float, contains: bool = False) -> None:
    deadline = time.monotonic() + timeout_s
    probe = exists_text_contains if contains else exists_text
    while probe(driver, text, retry=False):
        if time.monotonic() >= deadline:
            raise AssertionError(f"{text!r} was still on screen after {timeout_s}s")
        time.sleep(0.5)


# --------------------------------------------------------------------- taps


def tap_text(driver, text: str, *, timeout_s: float = 10.0) -> None:
    wait_visible_text(driver, text, timeout_s=timeout_s).click()


def tap_contains(driver, fragment: str, *, timeout_s: float = 10.0) -> None:
    wait_visible_text_contains(driver, fragment, timeout_s=timeout_s).click()


def tap_id(driver, identifier: str, *, timeout_s: float = 10.0) -> None:
    wait_visible_id(driver, identifier, timeout_s=timeout_s).click()


def tap_button(driver, label: str, *, timeout_s: float = 10.0, topmost: bool = False) -> None:
    """Tap the BUTTON carrying `label`. A label can also be a heading elsewhere
    on screen (CONVENE THE ROOM, SELL, STOP), so prefer the clickable one.
    `topmost=True` takes the LAST match in tree order, i.e. the one on the
    overlay when a dialog repeats a label the page behind it also has (ADD)."""
    deadline = time.monotonic() + timeout_s
    while True:
        matches = [el for el in _all_by_text(driver, label, retry=False) if _is_button(driver, el)]
        if matches:
            (matches[-1] if topmost else matches[0]).click()
            return
        if time.monotonic() >= deadline:
            raise NoSuchElementException(f"no button labelled {label!r} within {timeout_s}s")
        time.sleep(0.5)


def _is_button(driver, element) -> bool:
    try:
        if is_ios(driver):
            return (element.get_attribute("type") or "") == "XCUIElementTypeButton"
        return element.get_attribute("clickable") == "true"
    except WebDriverException:
        return False


def close_sheet(driver) -> None:
    """Dismiss the topmost modal sheet."""
    if is_ios(driver):
        scrims = _all_by_text(driver, "Scrim", retry=False)
        if scrims:
            scrims[0].click()
            time.sleep(0.8)
            return
    driver.back()
    time.sleep(0.8)


def go_back(driver) -> None:
    """Pop the topmost pushed page (the AmiScreenHeader chevron)."""
    if exists_id(driver, NAV_BACK, retry=False):
        all_by_id(driver, NAV_BACK, retry=False)[0].click()
    else:
        driver.back()
    time.sleep(0.8)


# ------------------------------------------------------------------ keyboard


def dismiss_keyboard(driver) -> None:
    if is_ios(driver):
        for key in ("Done", "Return", "Search", "Go"):
            hit = [
                el
                for el in _all_by_text(driver, key, retry=False)
                if (el.get_attribute("type") or "") == "XCUIElementTypeButton"
            ]
            if hit:
                hit[0].click()
                time.sleep(0.5)
                return
    hide_keyboard_if_shown(driver)


def clear_keyboard(driver) -> bool:
    """Make sure no keyboard is up: dismiss it, and if one survives (an omnibox
    focused by a stray tap has no Done key) relaunch the app. True if it acted."""
    try:
        if not driver.is_keyboard_shown():
            return False
    except Exception:
        return False
    dismiss_keyboard(driver)
    time.sleep(0.8)
    try:
        still = driver.is_keyboard_shown()
    except Exception:
        still = False
    if still:
        app_id = _app_id(driver)
        print("    [journey] a keyboard is stuck up - relaunching the app")
        driver.terminate_app(app_id)
        time.sleep(1.0)
        driver.activate_app(app_id)
        time.sleep(7.0)
    return True


def fill_field(driver, label: str, value: str) -> None:
    """Replace the content of the text field whose label contains `label`."""
    if is_ios(driver):
        field = driver.find_element(
            AppiumBy.IOS_PREDICATE,
            f'type == "XCUIElementTypeTextField" AND label CONTAINS "{label}"',
        )
    else:
        field = driver.find_element(
            AppiumBy.ANDROID_UIAUTOMATOR,
            'new UiSelector().className("android.widget.EditText").'
            f'descriptionContains("{label}")',
        )
    field.click()
    time.sleep(0.4)
    try:
        field.clear()
    except WebDriverException:
        pass
    field.send_keys(value)


# ------------------------------------------------------------------- scrolling


def drag(driver, x: float, y_from: float, y_to: float, *, seconds: float = 0.5) -> None:
    """Drag vertically; coordinates are fractions of the window."""
    size = driver.get_window_size()
    w, h = size["width"], size["height"]
    sx, sy, ey = int(w * x), int(h * y_from), int(h * y_to)
    if is_ios(driver):
        driver.execute_script(
            "mobile: dragFromToForDuration",
            {"fromX": sx, "fromY": sy, "toX": sx, "toY": ey, "duration": seconds},
        )
    else:
        driver.execute_script(
            "mobile: dragGesture",
            {"startX": sx, "startY": sy, "endX": sx, "endY": ey, "speed": 1200},
        )
    time.sleep(0.4)


def hdrag(driver, y_px: int, x_from: float, x_to: float, *, seconds: float = 0.4) -> None:
    """Horizontal drag at pixel/point row `y_px`; x as fractions of the window."""
    w = driver.get_window_size()["width"]
    sx, ex = int(w * x_from), int(w * x_to)
    if is_ios(driver):
        driver.execute_script(
            "mobile: dragFromToForDuration",
            {"fromX": sx, "fromY": y_px, "toX": ex, "toY": y_px, "duration": seconds},
        )
    else:
        driver.execute_script(
            "mobile: dragGesture", {"startX": sx, "startY": y_px, "endX": ex, "endY": y_px, "speed": 1200}
        )
    time.sleep(0.6)


#: Scroll drags run down the right-hand margin: a drag that STARTS on a text field
#: focuses it and raises the keyboard instead of scrolling (the Floor's omnibox and
#: feedback box sit exactly where a mid-screen upward swipe begins).
_SCROLL_X = 0.975


def scroll_down(driver, *, times: int = 1) -> None:
    for _ in range(times):
        drag(driver, _SCROLL_X, 0.75, 0.25)


def scroll_up(driver, *, times: int = 1) -> None:
    for _ in range(times):
        drag(driver, _SCROLL_X, 0.25, 0.75)


def on_screen(driver, text: str, *, contains: bool = False) -> bool:
    """`text` is ON SCREEN: some matching node has a real rect inside the pane.

    Flutter keeps nodes just outside the viewport in the hierarchy with a zero-sized
    rect, so "it exists" is not "the user can see it" - and a tap on one of those
    lands nowhere (or on whatever scrolled under the finger)."""
    height = driver.get_window_size()["height"]
    finder = _all_by_text_contains if contains else _all_by_text
    for el in finder(driver, text, retry=False):
        try:
            r = el.rect
        except WebDriverException:
            continue
        if r["height"] > 0 and height * 0.12 < r["y"] < height * 0.80:
            return True
    return False


def scroll_until_text(driver, text: str, *, contains: bool = False, max_scrolls: int = 8) -> None:
    for _ in range(max_scrolls):
        if on_screen(driver, text, contains=contains):
            time.sleep(0.8)  # let the fling settle before anyone taps
            return
        scroll_down(driver)
        time.sleep(0.6)
    if not on_screen(driver, text, contains=contains):
        raise NoSuchElementException(f"{text!r} not on screen after {max_scrolls} scrolls")


# ----------------------------------------------------------------- shell + data


def on_floor(driver) -> bool:
    return shell_is_up(driver, LOCALES["en"].tab_labels["Floor"])


def money_near(driver, label: str) -> float:
    """The `$x` amount rendered on the same row as `label` (e.g. CASH)."""
    anchor = by_text(driver, label)
    ay = anchor.rect["y"]
    ax = anchor.rect["x"]
    best = None
    for el in _all_by_text_contains(driver, "$", retry=False):
        try:  # the ticker tape scrolls: its nodes can vanish between query and read
            text = element_description(driver, el)
            m = _MONEY.match(text.strip())
            if not m:
                continue
            r = el.rect
        except WebDriverException:
            continue
        if abs(r["y"] - ay) <= 12 and r["x"] > ax:
            if best is None or r["x"] < best[0]:
                best = (r["x"], float(m.group(1).replace(",", "")))
    if best is None:
        raise NoSuchElementException(f"no $ amount on the same row as {label!r}")
    return best[1]


def holding_quantity(driver, ticker: str) -> float:
    """Shares of `ticker` on the Portfolio positions list (0 when not held)."""
    pattern = re.compile(rf"^{re.escape(ticker)}\s+([\d.]+) sh")
    for el in _all_by_text_contains(driver, " sh · ", retry=False):
        try:
            text = element_description(driver, el)
        except WebDriverException:
            continue
        m = pattern.match(text.replace("\n", " ").strip())
        if m:
            return float(m.group(1))
    return 0.0
