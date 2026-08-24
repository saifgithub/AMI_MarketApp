"""DEF366 — is the app under test in front? Three answers, never two.

Deliberately imports NOTHING. The walk's own modules pull in selenium, the
Appium client and the locale config, which is why the previous version of this
logic could only be exercised with a simulator attached — and its failure mode
was precisely that it could not be observed from outside. A guard for that
cannot itself need a device.

The bug this replaces: `_is_app_foreground` was

    try:    return driver.query_app_state(app_id) == 4
    except: return True

so "cannot tell" and "we are fine" were the same value. DEF362 then spent two
rounds of diagnosis and ~9 minutes a round on a walk that sat at the iOS home
screen for its full 480-second budget while the detector reported fine, and
reported "onboarding did not reach Floor" — which reads as the app failing to
start. Two point fixes (DEF347, DEF348) were aimed at that misreading.
"""

from __future__ import annotations

# Appium's application state enum.
FOREGROUND_STATE = 4

FOREGROUND = "foreground"
NOT_FOREGROUND = "not_foreground"
UNKNOWN = "unknown"


def resolve(query) -> str:
    """`query` is a zero-argument callable returning Appium's app-state int.

    Passing the query rather than the driver is what keeps this file free of
    the Appium import chain, and is what makes every branch testable with a
    lambda instead of a simulator.
    """
    try:
        state = query()
    except Exception:
        return UNKNOWN
    if state is None:
        # A driver that answers "I don't know" in-band. Not foreground, and
        # not a measurement either — the same third state.
        return UNKNOWN
    return FOREGROUND if state == FOREGROUND_STATE else NOT_FOREGROUND
