"""Builds a connected Appium webdriver.Remote against the local Appium server."""

from __future__ import annotations

import os

from appium import webdriver

from config.capabilities import POST_CONNECT_SETTINGS, build_capabilities
from config.devices import DeviceProfile

APPIUM_SERVER_URL = os.environ.get("AMI_APPIUM_SERVER", "http://127.0.0.1:4723")


def new_driver(device: DeviceProfile, *, no_reset: bool = True) -> webdriver.Remote:
    options = build_capabilities(device, no_reset=no_reset)
    driver = webdriver.Remote(APPIUM_SERVER_URL, options=options)
    driver.update_settings(POST_CONNECT_SETTINGS)
    return driver
