"""Per-platform capability builders.

Every flag here earned its place from a specific, reasoned-through gotcha — the
docstrings record the "what", CR080 (Android) and CR162 (iOS) the reasoning:

Android / UiAutomator2:
- waitForIdleTimeout=100 — home_shell.dart mounts a TickerTape that animates
  continuously. Android's accessibility "wait for idle" would otherwise stall
  up to 10s on every single command, against a screen that is *never* idle.
  This is the single biggest Flutter-specific gotcha for this app.
- ignoreUnimportantViews=False — keep the full accessibility tree. Flutter's
  own "importance" flags aren't a reliable filter for a black-box test; we
  filter ourselves in helpers/layout.py instead of trusting the driver to.
- disableWindowAnimation — stability + speed, no semantic effect.
- newCommandTimeout=300 — some flows (Room, LLM streaming) have long waits
  between Appium commands; the default would kill the session mid-test.
- noReset=True by default — most Phase 1 tests want to reuse an
  already-onboarded guest session, not force a cold start. Tests that need a
  cold anonymous session call helpers.device.reset_app() explicitly first.

iOS / XCUITest:
- waitForQuiescence=False — the exact analogue of the Android idle problem, and
  for the same TickerTape. XCUITest's default is to wait for the app to stop
  animating before returning from any interaction; this app never stops, so the
  default turns every command into a ~10s timeout. Without this flag the suite
  does not merely run slowly, it fails.
- WDA ports/timeouts are left at their defaults on the Simulator, where there is
  no provisioning to go wrong. They will need attention for the real device.
"""

import os

from appium.options.android import UiAutomator2Options
from appium.options.ios import XCUITestOptions

from config.devices import IOS, DeviceProfile


def build_capabilities(device: DeviceProfile, *, no_reset: bool = True):
    """Dispatch on the profile's platform. Returns the driver options object
    the Appium client expects for that platform."""
    if device.platform == IOS:
        return _build_ios(device, no_reset=no_reset)
    return _build_android(device, no_reset=no_reset)


def _build_android(device: DeviceProfile, *, no_reset: bool) -> UiAutomator2Options:
    options = UiAutomator2Options()
    options.load_capabilities(
        {
            "platformName": "Android",
            "appium:automationName": "UiAutomator2",
            "appium:udid": device.serial,
            "appium:appPackage": device.app_package,
            "appium:appActivity": device.app_activity,
            "appium:noReset": no_reset,
            "appium:autoGrantPermissions": True,
            "appium:disableWindowAnimation": True,
            "appium:newCommandTimeout": 300,
            "appium:uiautomator2ServerLaunchTimeout": 60000,
            "appium:uiautomator2ServerInstallTimeout": 60000,
            "appium:ignoreUnimportantViews": False,
            "appium:settings[waitForIdleTimeout]": 100,
            "appium:settings[waitForSelectorTimeout]": 5000,
        }
    )
    # A locked device drives nothing, and says so in the least useful way: the
    # suite spent 300s tapping a Samsung lock screen and reported "onboarding
    # did not reach Floor" — the app was never even in front. Appium can clear
    # a swipe-only lock on its own; a PIN/pattern/password needs the credential,
    # which belongs in the environment and never in git.
    unlock_type = os.environ.get("AMI_UNLOCK_TYPE")
    unlock_key = os.environ.get("AMI_UNLOCK_KEY")
    if unlock_type and unlock_key:
        options.load_capabilities(
            {
                "appium:unlockType": unlock_type,  # pin | password | pattern | fingerprint
                "appium:unlockKey": unlock_key,
                "appium:unlockStrategy": "uiautomator",
            }
        )
    return options


def _build_ios(device: DeviceProfile, *, no_reset: bool) -> XCUITestOptions:
    options = XCUITestOptions()
    options.load_capabilities(
        {
            "platformName": "iOS",
            "appium:automationName": "XCUITest",
            "appium:udid": device.serial,
            "appium:bundleId": device.bundle_id,
            "appium:noReset": no_reset,
            "appium:autoAcceptAlerts": True,
            "appium:newCommandTimeout": 300,
            "appium:wdaLaunchTimeout": 180000,
            "appium:wdaConnectionTimeout": 180000,
            # See the module docstring — this is the TickerTape flag, and the
            # single most important line in this function.
            "appium:waitForQuiescence": False,
            "appium:settings[snapshotMaxDepth]": 62,
        }
    )
    return options


# Belt-and-suspenders: also push these via driver.update_settings() right
# after connect, since not every driver build honours the capability form of
# every setting equally reliably.
POST_CONNECT_SETTINGS = {
    "android": {
        "waitForIdleTimeout": 100,
        "allowInvisibleElements": True,
    },
    "ios": {
        # XCUITest's own name for "do not wait for animations to settle".
        "waitForQuiescence": False,
        # Flutter's semantics tree is flat and wide rather than deep; the
        # default snapshot depth truncates long screens, which reads as
        # "the element is not there" — a false negative that looks like an
        # app bug. Raised deliberately.
        "snapshotMaxDepth": 62,
    },
}
