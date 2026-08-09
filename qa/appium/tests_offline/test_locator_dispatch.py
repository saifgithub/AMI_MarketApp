"""Offline guards for the CR162 platform-dispatch logic. No device, no Appium
server — these run anywhere, in milliseconds, including on the rig.

They exist because the dispatch is the one place in this harness where being
wrong is *silent*. `AppiumBy.ACCESSIBILITY_ID` is the correct strategy for
Flutter's `Semantics(identifier:)` on iOS and the WRONG one on Android — there
it means `content-desc`, which the app does not set, so every lookup would
return nothing and read exactly like "the element isn't on screen". A test that
fails for a fake reason is worse than no test, and this suite's whole job is
telling a real defect from a harness artefact (see CR080's two hand-edit
incidents, where a `TypeError` was reported as 27 app failures).
"""

from __future__ import annotations

import pytest
from appium.webdriver.common.appiumby import AppiumBy

from helpers import locators
from helpers.platform import platform_of


class FakeDriver:
    """Records the (by, value) pairs a helper asks for, and returns nothing —
    enough to assert *how* we look, which is the part under test."""

    def __init__(self, platform_name: str):
        self.capabilities = {"platformName": platform_name}
        self.queries: list[tuple[str, str]] = []

    def find_elements(self, by, value):
        self.queries.append((by, value))
        return []


@pytest.fixture(autouse=True)
def _no_retry_sleep(monkeypatch):
    """The retry backoff is ~5.4s of real sleeping per lookup — irrelevant here
    and it would make this file the slowest thing in the suite."""
    monkeypatch.setattr(locators, "_RETRY_DELAYS", ())


def test_platform_of_reads_the_live_session():
    assert platform_of(FakeDriver("Android")) == "android"
    assert platform_of(FakeDriver("iOS")) == "ios"


def test_unknown_platform_raises_rather_than_guessing():
    with pytest.raises(RuntimeError, match="platformName"):
        platform_of(FakeDriver("Windows"))


def test_identifier_uses_resource_id_on_android_not_accessibility_id():
    """The load-bearing assertion of this file. Flutter maps
    SemanticsProperties.identifier to resource-id on Android; ACCESSIBILITY_ID
    means content-desc there and would silently match nothing."""
    driver = FakeDriver("Android")
    locators.all_by_id(driver, "ami.nav.floor")

    by, value = driver.queries[0]
    assert by == AppiumBy.ANDROID_UIAUTOMATOR
    assert value == 'new UiSelector().resourceId("ami.nav.floor")'
    assert AppiumBy.ACCESSIBILITY_ID not in [q[0] for q in driver.queries]


def test_identifier_uses_accessibility_id_on_ios():
    """...and on iOS the same Flutter property lands on
    accessibilityIdentifier, which IS AppiumBy.ACCESSIBILITY_ID."""
    driver = FakeDriver("iOS")
    locators.all_by_id(driver, "ami.nav.floor")

    assert driver.queries[0] == (AppiumBy.ACCESSIBILITY_ID, "ami.nav.floor")


def test_missing_identifier_names_the_build_flag():
    """A NoSuchElement here is far more often a build problem than a missing
    element, so the message has to say so — otherwise it gets debugged as an
    app bug (CR080 lost a session to exactly that)."""
    driver = FakeDriver("iOS")
    with pytest.raises(Exception) as exc:
        locators.by_id(driver, "ami.nav.floor")
    assert "AMI_QA_SEMANTICS" in str(exc.value)


def test_text_lookup_is_platform_specific():
    android = FakeDriver("Android")
    locators.all_by_text(android, "FLOOR")
    assert android.queries[0][0] == AppiumBy.ANDROID_UIAUTOMATOR
    assert 'text("FLOOR")' in android.queries[0][1]

    ios = FakeDriver("iOS")
    locators.all_by_text(ios, "FLOOR")
    assert ios.queries[0][0] == AppiumBy.IOS_PREDICATE
    assert '"FLOOR"' in ios.queries[0][1]


def test_predicate_literals_escape_quotes():
    """Today's copy contains no double quotes. A translation will, and a
    locator that breaks on punctuation gets blamed on the app."""
    assert locators._predicate_literal('say "hi"') == '"say \\"hi\\""'
    assert locators._predicate_literal("back\\slash") == '"back\\\\slash"'


def test_scrollable_is_tristate_and_never_false_on_ios():
    """None means undetermined. Returning False on iOS would manufacture
    scroll-overflow findings on screens that scroll perfectly well — see
    helpers/locators.scrollable_exists."""
    assert locators.scrollable_exists(FakeDriver("iOS")) is None
    assert locators.scrollable_exists(FakeDriver("Android")) is False
