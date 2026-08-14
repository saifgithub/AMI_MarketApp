"""Offline guards for `helpers/onboarding.py`'s "am I still in the app" check.

The Concierge walk is the one part of this harness that taps things it has not
identified: it reads the accessibility tree, picks the bottom-most labelled
candidate, taps, repeats. That is the correct design for an interview whose
questions are generated and whose chips are therefore not known in advance —
but the tree it reads belongs to whatever app is in *front*, not to the app
under test.

Measured on the Android rig: a run left AMI Trade and spent its entire 300s
budget tapping the Samsung dialer's keypad, then failed with "onboarding did
not reach Floor". Every word of that message was true and all of it pointed at
the wrong thing — the app was healthy and sitting in the background the whole
time. A test that fails for a fake reason is worse than no test (see this
suite's other guards); a test that fails for a fake reason *while describing a
real one* is worse still.

These run with no device: the escape detection is pure decision logic, and the
part worth pinning is what it does when the answer is unknown.
"""

from __future__ import annotations

import pytest

from helpers import onboarding


class FakeDriver:
    def __init__(self, *, state=onboarding._FOREGROUND, caps=None, package="com.x"):
        self.capabilities = caps if caps is not None else {"appPackage": "ai.agenticmarketintel.ami_trade"}
        self._state = state
        self.current_package = package

    def query_app_state(self, app_id):
        if isinstance(self._state, Exception):
            raise self._state
        return self._state


def test_the_app_under_test_is_read_from_the_live_session():
    """Not a constant: the two platforms' ids differ by more than case
    (`ai.agenticmarketintel.ami_trade` vs `…amiTrade`), so a hardcoded one
    would never match on the other platform and the check would be dead."""
    android = FakeDriver(caps={"appPackage": "ai.agenticmarketintel.ami_trade"})
    ios = FakeDriver(caps={"bundleId": "ai.agenticmarketintel.amiTrade"})
    prefixed = FakeDriver(caps={"appium:appPackage": "ai.agenticmarketintel.ami_trade"})

    assert onboarding._app_id(android) == "ai.agenticmarketintel.ami_trade"
    assert onboarding._app_id(ios) == "ai.agenticmarketintel.amiTrade"
    assert onboarding._app_id(prefixed) == "ai.agenticmarketintel.ami_trade"
    assert onboarding._app_id(FakeDriver(caps={})) is None


@pytest.mark.parametrize(
    "state, foreground",
    [
        (4, True),   # RUNNING_IN_FOREGROUND
        (3, False),  # RUNNING_IN_BACKGROUND — the dialer case
        (2, False),  # RUNNING_IN_BACKGROUND_SUSPENDED
        (1, False),  # NOT_RUNNING
        (0, False),  # NOT_INSTALLED
    ],
)
def test_only_foreground_counts_as_still_in_the_app(state, foreground):
    """Background is exactly the state the dialer incident produced — the app
    was alive the whole time (`pidof` returned a pid), just not in front. An
    is-it-running check would have called that healthy."""
    driver = FakeDriver(state=state)
    assert onboarding._is_app_foreground(driver, "ai.agenticmarketintel.ami_trade") is foreground


def test_an_unanswerable_state_query_assumes_we_are_home():
    """The one place this must NOT degrade loudly.

    A false escape relaunches the app mid-interview and throws away every
    answer already given, turning a working run into a failing one. The cost is
    asymmetric: a missed escape wastes the budget of a run that was going to
    fail anyway, a false escape breaks a run that was going to pass. So an
    unknown answer means carry on."""
    driver = FakeDriver(state=RuntimeError("driver does not implement this"))
    assert onboarding._is_app_foreground(driver, "whatever") is True


def test_the_diagnostic_names_the_intruder_and_survives_not_knowing_it():
    """`current_package` is Android-only. It is worth reporting where it works
    — "the dialer" is a diagnosis, "not our app" is a puzzle — and must not
    break the escape path where it does not."""
    assert onboarding._foreground_package(FakeDriver(package="com.android.dialer")) == "com.android.dialer"

    class NoPackage:
        @property
        def current_package(self):
            raise RuntimeError("unsupported on this platform")

    assert onboarding._foreground_package(NoPackage()) is None
