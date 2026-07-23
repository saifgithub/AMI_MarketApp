"""UiAutomator2 capability builder.

Every flag here earned its place from a specific, reasoned-through gotcha —
see CR080 for the reasoning, this docstring only records the "what":

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
  cold anonymous session call helpers.device.pm_clear() explicitly first.
"""

from appium.options.android import UiAutomator2Options

from config.devices import DeviceProfile


def build_capabilities(device: DeviceProfile, *, no_reset: bool = True) -> UiAutomator2Options:
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
    return options


# Belt-and-suspenders: also push these via driver.update_settings() right
# after connect, since not every UiAutomator2 build honours the capability
# form of every setting equally reliably.
POST_CONNECT_SETTINGS = {
    "waitForIdleTimeout": 100,
    "allowInvisibleElements": True,
}
