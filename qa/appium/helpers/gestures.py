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


def swipe_up(driver: WebDriver, band: Band, *, percent: float = 0.75) -> None:
    if is_ios(driver):
        _drag_within_band(driver, band, percent=percent, upward=True)
        return
    left, top, width, height = band
    driver.execute_script(
        "mobile: swipeGesture",
        {"left": left, "top": top, "width": width, "height": height, "direction": "up", "percent": percent},
    )


def swipe_down(driver: WebDriver, band: Band, *, percent: float = 0.75) -> None:
    if is_ios(driver):
        _drag_within_band(driver, band, percent=percent, upward=False)
        return
    left, top, width, height = band
    driver.execute_script(
        "mobile: swipeGesture",
        {"left": left, "top": top, "width": width, "height": height, "direction": "down", "percent": percent},
    )


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
