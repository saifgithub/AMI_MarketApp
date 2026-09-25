"""Offline guards for `helpers/system_alerts.py` (DEF426).

A native `UIAlertController` sits above Flutter's semantics tree entirely, so
no locator this harness already has can see one, let alone dismiss it. These
tests pin the decision logic against a fake driver that answers
`execute_script` the way XCUITest's `mobile: getAlertText` / `mobile: alert`
commands do — no real Appium session needed, same reasoning as
`test_onboarding_containment.py`'s fakes.
"""

from __future__ import annotations

import pytest

from helpers.system_alerts import _DECLINE_BUTTON_CANDIDATES, dismiss_system_alert_if_present


class FakeIosDriver:
    """`has_alert` mimics whether `mobile: getAlertText` would raise (no
    alert) or succeed (one is up). `accepted_labels` records every
    `buttonLabel` tried against `mobile: alert`, in order — the thing this
    module actually needs to get right is trying "Not now" before anything
    riskier, not merely "an alert got dismissed somehow"."""

    def __init__(self, *, has_alert: bool, working_label: str | None = "Not Now"):
        self.capabilities = {"platformName": "iOS", "bundleId": "x"}
        self.has_alert = has_alert
        self.working_label = working_label
        self.attempted_labels: list[str] = []
        self.dismiss_called = False

    def execute_script(self, script, params=None):
        if script == "mobile: getAlertText":
            if not self.has_alert:
                raise Exception("no such alert")
            return "Notifications"
        if script == "mobile: alert":
            action = params.get("action")
            if action == "dismiss":
                self.dismiss_called = True
                self.has_alert = False
                return None
            label = params.get("buttonLabel")
            self.attempted_labels.append(label)
            if label != self.working_label:
                raise Exception(f"no button titled {label!r}")
            self.has_alert = False
            return None
        raise Exception(f"unexpected script: {script}")


class FakeAndroidDriver:
    def __init__(self):
        self.capabilities = {"platformName": "Android", "appPackage": "x"}

    def execute_script(self, script, params=None):
        raise AssertionError("system_alerts must not touch Android at all")


def test_no_alert_present_is_a_quiet_no_op():
    driver = FakeIosDriver(has_alert=False)
    assert dismiss_system_alert_if_present(driver) is False


def test_the_push_soft_asks_native_prompt_is_declined_not_accepted():
    """The exact DEF426/E5-U1 shape: "Not now" is tried, and tried BEFORE any
    button that would grant the permission — this helper must never be the
    thing that accidentally grants it on a device where it re-prompts."""
    driver = FakeIosDriver(has_alert=True, working_label="Not Now")
    assert dismiss_system_alert_if_present(driver) is True
    assert driver.attempted_labels[0] == "Not Now"
    assert "Turn on" not in driver.attempted_labels
    assert "Allow" not in driver.attempted_labels


@pytest.mark.parametrize("working_label", _DECLINE_BUTTON_CANDIDATES)
def test_every_known_decline_label_is_reachable(working_label):
    """Different alert families (location/camera/mic use `Don't Allow`, this
    app's own soft-ask copy is `Not now`) — whichever one WDA reports as the
    real button title must still resolve, not just the first guess."""
    driver = FakeIosDriver(has_alert=True, working_label=working_label)
    assert dismiss_system_alert_if_present(driver) is True


def test_an_unrecognised_alert_falls_back_to_a_bare_dismiss():
    """An alert whose buttons match none of our guesses must still get off
    screen — every later locator in the test needs the screen uncovered, not
    a helper that gave up because the label vocabulary didn't match."""
    driver = FakeIosDriver(has_alert=True, working_label="Some Other Button")
    assert dismiss_system_alert_if_present(driver) is True
    assert driver.dismiss_called is True


def test_android_is_never_touched():
    """UiAutomator2 permission dialogs are already pre-empted at install time
    by `autoGrantPermissions` (config/capabilities.py) and are, unlike iOS's,
    inside the resolvable tree regardless — this module has nothing to do
    there, and must not even attempt an iOS-only mobile: command."""
    assert dismiss_system_alert_if_present(FakeAndroidDriver()) is False
