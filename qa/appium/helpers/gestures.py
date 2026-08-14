"""Gesture + screenshot helpers.

Android uses UiAutomator2's `mobile:` gesture commands rather than the
deprecated TouchAction API. CR162 added the XCUITest equivalents, which are a
different vocabulary rather than the same commands under another driver:
`mobile: swipe` on iOS takes a direction over an element or the whole screen and
has no band/percent concept, so a band-scoped swipe is expressed as
`mobile: dragFromToForDuration` between two computed points.

All coordinates here are in the driver's own space — points on iOS, pixels on
Android. See helpers/layout.py's docstring on why that distinction matters.
"""

from __future__ import annotations

from appium.webdriver.webdriver import WebDriver

from helpers.platform import is_ios

Band = tuple[int, int, int, int]  # left, top, width, height

# A drag slower than a flick: a fast drag on iOS is interpreted as a fling and
# lands with momentum, so a "did the screen move?" probe would measure the
# fling's overshoot rather than whether the content scrolls at all.
_IOS_DRAG_SECONDS = 0.6

# Android drag tuning. The inset keeps the touch-down off the very edge of the
# band, where a parent (the bottom nav, the ticker) can claim the gesture; the
# speed is a drag rather than a fling, so the pane lands where it was put
# instead of coasting past the content a probe is about to look for.
_DRAG_EDGE_INSET = 8
_DRAG_SPEED = 1200


def _drag_within_band(driver: WebDriver, band: Band, *, percent: float, upward: bool) -> None:
    left, top, width, height = band
    x = left + width // 2
    travel = int(height * percent)
    if upward:
        start_y, end_y = top + height - 1, top + height - 1 - travel
    else:
        start_y, end_y = top + 1, top + 1 + travel
    driver.execute_script(
        "mobile: dragFromToForDuration",
        {
            "fromX": x,
            "fromY": max(start_y, top),
            "toX": x,
            "toY": max(min(end_y, top + height), top),
            "duration": _IOS_DRAG_SECONDS,
        },
    )


# `dragGesture` — a real touch-drag. NOT `swipeGesture`, and NOT `scrollGesture`.
#
# Measured on the rig against the SETTINGS pane, from a known top position:
#
#   swipeGesture   ~14 attempts over three bands  — content never changed
#   scrollGesture  10 attempts over the pane's own bounds — content never
#                  changed, and it returned `canScrollMore=False` on the FIRST
#                  call while the pane was still on its first screen
#   dragGesture    6 attempts — MY MANDATE → COMPLIANCE → plan → language →
#                  HELP → WALKTHROUGH, moving every time
#
# The likely reason: the first two ask UiAutomator to scroll, which drives the
# accessibility node's scroll actions. Flutter advertises a scrollable node but
# does not service those actions the way a native ViewGroup does. A drag sends
# actual touch events, which Flutter's gesture arena handles like a finger.
#
# `scrollGesture`'s `canScrollMore` is worse than useless here: it returned
# False — "you have reached the end" — on a pane sitting at its top with six
# more screens below. Trusting it made a scroll loop exit immediately and
# report the target missing.
#
# Why this matters beyond any one test: `helpers/layout.py::swipe_moved` decides
# "did the screen actually scroll" by diffing pixels either side of this call,
# and that is the primary signal of the DEF075-class scroll-overflow check. A
# gesture that never moves anything pins that signal to false, and the check
# then falls through to "is a scrollable widget present" — a question about the
# widget tree, not about whether a user can reach the content. It answers "fine"
# on precisely the screen whose content cannot be scrolled to.
def _scroll(driver: WebDriver, band: Band, *, percent: float, upward: bool) -> bool:
    """Drag within `band`. True if the screen actually changed.

    The return value is measured, not assumed — a signature of the hierarchy
    before and after. Callers need a trustworthy "is there more?" and the
    driver's own answer was wrong (see above); this one is derived from what
    the screen actually did.
    """
    left, top, width, height = band
    x = left + width // 2
    travel = int(height * percent)
    if upward:  # finger up = reveal content below
        start_y = top + height - _DRAG_EDGE_INSET
        end_y = max(top + _DRAG_EDGE_INSET, start_y - travel)
    else:
        start_y = top + _DRAG_EDGE_INSET
        end_y = min(top + height - _DRAG_EDGE_INSET, start_y + travel)

    before = driver.page_source
    driver.execute_script(
        "mobile: dragGesture",
        {"startX": x, "startY": start_y, "endX": x, "endY": end_y, "speed": _DRAG_SPEED},
    )
    return driver.page_source != before


def swipe_up(driver: WebDriver, band: Band, *, percent: float = 0.75) -> bool:
    """Reveal content BELOW the current view. Returns whether more remains
    (Android only; always True on iOS, which cannot report it)."""
    if is_ios(driver):
        _drag_within_band(driver, band, percent=percent, upward=True)
        return True
    # A finger swiping up scrolls the viewport DOWN through the content.
    return _scroll(driver, band, percent=percent, upward=True)


def swipe_down(driver: WebDriver, band: Band, *, percent: float = 0.75) -> bool:
    """Reveal content ABOVE the current view."""
    if is_ios(driver):
        _drag_within_band(driver, band, percent=percent, upward=False)
        return True
    return _scroll(driver, band, percent=percent, upward=False)


def tap_xy(driver: WebDriver, x: int, y: int) -> None:
    if is_ios(driver):
        driver.execute_script("mobile: tap", {"x": x, "y": y})
        return
    driver.execute_script("mobile: clickGesture", {"x": x, "y": y})


def long_press_xy(driver: WebDriver, x: int, y: int, *, duration_ms: int = 800) -> None:
    if is_ios(driver):
        driver.execute_script(
            "mobile: touchAndHold", {"x": x, "y": y, "duration": duration_ms / 1000.0}
        )
        return
    driver.execute_script("mobile: longClickGesture", {"x": x, "y": y, "duration": duration_ms})


def long_press_element(driver: WebDriver, element, *, duration_ms: int = 800) -> None:
    rect = element.rect
    x = rect["x"] + rect["width"] // 2
    y = rect["y"] + rect["height"] // 2
    long_press_xy(driver, x, y, duration_ms=duration_ms)


def tap_element(driver: WebDriver, element) -> None:
    element.click()


def hide_keyboard_if_shown(driver: WebDriver) -> None:
    try:
        if driver.is_keyboard_shown():
            driver.hide_keyboard()
    except Exception:
        pass  # not every driver build supports the keyboard-shown query; best-effort only


def screenshot_png(driver: WebDriver) -> bytes:
    return driver.get_screenshot_as_png()


def screen_scale(driver: WebDriver) -> float:
    """Device pixels per driver coordinate unit.

    1.0 on Android. ~3.0 on a Retina iPhone, where `element.rect` speaks points
    and `get_screenshot_as_png` speaks pixels. Measured from the live session
    rather than hardcoded per model — a wrong constant here silently crops the
    wrong region, and a silently-wrong pixel diff is indistinguishable from
    "the screen didn't scroll"."""
    if not is_ios(driver):
        return 1.0
    from io import BytesIO

    from PIL import Image

    window = driver.get_window_size()
    png_width = Image.open(BytesIO(screenshot_png(driver))).size[0]
    if not window.get("width"):
        return 1.0
    return png_width / float(window["width"])


def scroll_to_top(driver: WebDriver, band: Band, *, max_scrolls: int = 10) -> None:
    """Put a scrollable back at its start.

    A test asserting on a pane's FIRST section has to own the pane's scroll
    position rather than inherit it. `noReset=True` keeps the app process alive
    between Appium sessions, so a Flutter scroll offset survives not just the
    previous test but the previous *run* — `test_settings_renders_heading`
    failed on `MY MANDATE` in complete isolation because an earlier diagnostic
    had left the pane at the bottom, and nothing in between put it back.

    Stops as soon as the scrollable reports it cannot go further, so the common
    case (already at the top) costs one call.
    """
    for _ in range(max_scrolls):
        if not swipe_down(driver, band, percent=1.0):
            return
