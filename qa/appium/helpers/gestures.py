"""Gesture + screenshot helpers, using UiAutomator2's `mobile:` gesture
commands rather than the deprecated TouchAction API."""

from __future__ import annotations

from appium.webdriver.webdriver import WebDriver

Band = tuple[int, int, int, int]  # left, top, width, height


def swipe_up(driver: WebDriver, band: Band, *, percent: float = 0.75) -> None:
    left, top, width, height = band
    driver.execute_script(
        "mobile: swipeGesture",
        {"left": left, "top": top, "width": width, "height": height, "direction": "up", "percent": percent},
    )


def swipe_down(driver: WebDriver, band: Band, *, percent: float = 0.75) -> None:
    left, top, width, height = band
    driver.execute_script(
        "mobile: swipeGesture",
        {"left": left, "top": top, "width": width, "height": height, "direction": "down", "percent": percent},
    )


def tap_xy(driver: WebDriver, x: int, y: int) -> None:
    driver.execute_script("mobile: clickGesture", {"x": x, "y": y})


def long_press_xy(driver: WebDriver, x: int, y: int, *, duration_ms: int = 800) -> None:
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
