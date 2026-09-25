"""Dismiss native OS alerts the Flutter accessibility tree cannot see (DEF426).

Every locator in this harness reads Flutter's *semantics* tree — `by_id()`,
`exists_text()`, all of it. A native `UIAlertController` (iOS's own permission
prompt chrome) is not part of that tree at all; it is a system window drawn
above the app. `autoAcceptAlerts` (already set in `config/capabilities.py`)
only catches an alert if XCUITest's own polling happens to observe it between
commands, and "accept" taps whatever XCUITest considers the affirmative button
— for a permission prompt that is "Turn on", the exact opposite of what a QA
rig driving a simulator (no real push token, no notification entitlement to
exercise) should choose. E5-U1 (2026-09-25, iOS Simulator phase1 gate) hit
this directly: the OS "Turn on notifications?" dialog covered the Floor screen
mid-suite and every later text/id wait timed out against a fully healthy app.

Two-layer fix:

1. `helpers/onboarding.py`'s `_NEVER_TAP` deny-list now also refuses the
   in-app Flutter soft-ask's "Turn on" button (`pushSoftAskAccept`,
   `push_notification_listener.dart`) — that dialog IS in the semantics tree
   and IS what the exploratory walk was tapping; only tapping it fires the
   real `service.requestPermission()` call that raises the native one this
   module exists to handle. Refusing it at the source means the native dialog
   should not appear at all during onboarding.
2. This module is the backstop for every other case noReset=True state
   already has the OS permission decided-but-re-prompted, a future flow asks
   again outside onboarding, or a real device's OS is more eager than the
   Simulator's. Called once per test via the `_shell_precondition` autouse
   fixture in `conftest.py`, the same place `recover_to_shell` already runs —
   before any locator in the test body gets a chance to time out against a
   covered screen.

Android has no analogous gap: UiAutomator2's permission dialogs are
AOSP-themed views with resolvable resource-ids, already inside the tree
`autoGrantPermissions` (`config/capabilities.py`) pre-empties by granting at
install time. This module is therefore iOS-only and a no-op on Android.
"""

from __future__ import annotations

from helpers.platform import is_ios

# XCUITest's own alert-button vocabulary — not this app's copy, so no ARB
# lookup belongs here. "Don't Allow" covers the location/camera/etc. family
# other iOS system prompts use; "Not Now" (Apple's own casing) and "Not now"
# (this app's exact `pushSoftAskDecline` string, in case a future iOS build
# ever routes the app-level string through as the native prompt's own,
# which would be unusual but cheap to also match) both decline non-destructively.
_DECLINE_BUTTON_CANDIDATES = ("Not Now", "Not now", "Don't Allow", "Cancel")


def dismiss_system_alert_if_present(driver, *, timeout_s: float = 1.0) -> bool:
    """Best-effort: is a native alert up, and if so, decline it. Returns
    whether one was found and handled.

    `mobile: alert` is XCUITest's own command — it queries WDA directly, not
    the Flutter semantics tree, which is exactly why this can see what
    `exists_text`/`by_id` cannot. Errors (no alert present, WDA does not
    recognise the command, a stale session) are swallowed: this is a
    precondition helper that runs before every test, and a probe that can
    itself fail the test it is trying to protect would be worse than the gap
    it closes. Silence on failure is safe here specifically because the
    caller (`conftest.py::_shell_precondition`) still runs its own
    `shell_is_up` check afterwards and fails loudly, with the real
    diagnostic, if the screen is still covered.
    """
    if not is_ios(driver):
        return False

    try:
        driver.execute_script("mobile: getAlertText")
    except Exception:
        return False  # no alert up, or the query itself isn't supported here

    for label in _DECLINE_BUTTON_CANDIDATES:
        try:
            driver.execute_script("mobile: alert", {"action": "accept", "buttonLabel": label})
            return True
        except Exception:
            continue

    # A button label we didn't anticipate — still get the alert off screen
    # rather than leave every later wait to time out against it.
    try:
        driver.execute_script("mobile: alert", {"action": "dismiss"})
        return True
    except Exception:
        return False
