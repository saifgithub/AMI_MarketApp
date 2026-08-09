"""Which OS is the live driver talking to?

CR162 made this harness two-platform. Rather than thread a `platform` argument
through every helper signature (and every call site in `tests/`), each helper
asks the driver it was already given. The Appium session's own
`platformName` capability is the authority — it cannot drift from the session
that is actually running, which a passed-in constant can.

Deliberately not an enum: these values are compared against Appium's own
capability strings, and a bare lowercase string keeps the comparison obvious at
every call site.
"""

from __future__ import annotations

from appium.webdriver.webdriver import WebDriver

ANDROID = "android"
IOS = "ios"


def platform_of(driver: WebDriver) -> str:
    """`"android"` or `"ios"`. Raises rather than guessing — a helper that
    silently picked the wrong locator strategy would fail later, somewhere
    less obvious, with a NoSuchElement that looks like an app bug."""
    caps = driver.capabilities or {}
    name = str(caps.get("platformName", "")).strip().lower()
    if name in (ANDROID, IOS):
        return name
    raise RuntimeError(
        f"driver reports platformName={name!r}; this harness supports "
        f"{ANDROID!r} and {IOS!r} only"
    )


def is_ios(driver: WebDriver) -> bool:
    return platform_of(driver) == IOS
