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

    ios = FakeDriver("iOS")
    locators.all_by_text(ios, "FLOOR")
    assert ios.queries[0][0] == AppiumBy.IOS_PREDICATE
    assert '"FLOOR"' in ios.queries[0][1]


def test_android_text_lookup_searches_content_desc_not_only_text():
    """Flutter puts EVERY user-visible string in `content-desc` on Android.

    `Semantics(label:)` maps to `setContentDescription()`, not `setText()`, and
    a canvas-painting app has no native TextViews — so a `text()`-only selector
    matches nothing an actual user can read. This shipped: the bottom nav's
    `content-desc='FLOOR'` was in the tree while `exists_text('FLOOR')`
    returned False, which made the smoke gate's text assertion and the
    onboarding early-return probe both unsatisfiable on Android.

    The predecessor of this test asserted only that Android dispatches to
    ANDROID_UIAUTOMATOR — true, and true of the broken version too. Checking
    the *strategy* without the *coverage* is why it passed for the bug's whole
    lifetime."""
    android = FakeDriver("Android")
    locators.all_by_text(android, "FLOOR")
    selectors = [value for _, value in android.queries]

    assert any('description("FLOOR")' in s for s in selectors), (
        f"content-desc is never searched: {selectors}. Flutter labels live "
        f"there, so this finds nothing a user can read."
    )
    assert any('text("FLOOR")' in s for s in selectors), (
        f"`text` is never searched: {selectors}. Native (non-Flutter) chrome "
        f"and the system UI still use it."
    )
    assert 'description("FLOOR")' in selectors[0], (
        "content-desc should be tried FIRST — it is the overwhelmingly common "
        "case in this app, and ordering it second doubles the hit-path cost."
    )


def test_android_text_contains_also_searches_content_desc():
    android = FakeDriver("Android")
    locators.exists_text_contains(android, "FLO")
    selectors = [value for _, value in android.queries]
    assert any('descriptionContains("FLO")' in s for s in selectors), selectors
    assert any('textContains("FLO")' in s for s in selectors), selectors


def test_labelled_only_is_honoured_on_android_not_silently_dropped():
    """`labelled_only` was implemented inside the iOS predicate and ignored on
    Android, where the keyword was accepted and did nothing (82a54433, CR162).

    The caller that relies on it — `helpers/onboarding.py::_live_chip` — picks
    the BOTTOM-MOST candidate and documents by name that the unlabelled
    send-arrow beside the text field is excluded by this filter. On Android it
    was not, the arrow sits below the chip row, and the Concierge walk spent
    its entire budget tapping send on an empty field.

    A silently-ignored keyword is worse than an unsupported one: the guard
    reads as present in the source and is absent at runtime."""

    class FakeElement:
        def __init__(self, desc, text=""):
            self._desc, self.text = desc, text

        def get_attribute(self, name):
            return self._desc if name == "content-desc" else None

    labelled = FakeElement("Save for retirement")
    send_arrow = FakeElement("")

    class ElementDriver(FakeDriver):
        def find_elements(self, by, value):
            super().find_elements(by, value)
            return [labelled, send_arrow]

    driver = ElementDriver("Android")
    assert locators.interactive_elements(driver) == [labelled, send_arrow]
    assert locators.interactive_elements(driver, labelled_only=True) == [labelled], (
        "labelled_only did not filter on Android — the unlabelled send-arrow "
        "survived, which is the exact failure it exists to prevent."
    )


def test_waits_do_not_nest_the_retry_backoff(monkeypatch):
    """`wait_visible_text`/`wait_visible_id` own their deadline, so the lookup
    underneath must NOT run its own ~5.4s ladder as well.

    When it did, one 'attempt' outlived the entire budget and the caller's
    timeout became a floor instead of a ceiling: measured on the rig device, a
    miss took 7.65s against `timeout_s=2`. Asserted as a query count because
    that is the observable that does not require sleeping."""
    monkeypatch.setattr(locators, "_RETRY_DELAYS", (0.0, 0.0, 0.0, 0.0, 0.0))

    driver = FakeDriver("Android")
    with pytest.raises(Exception):
        locators.wait_visible_text(driver, "FLOOR", timeout_s=0.0)
    # One attempt = the two Android selectors, NOT the full ladder.
    assert len(driver.queries) == 2, (
        f"wait_visible_text issued {len(driver.queries)} queries for a single "
        f"zero-length budget — the inner backoff is nested inside the wait."
    )

    driver = FakeDriver("Android")
    with pytest.raises(Exception):
        locators.wait_visible_id(driver, "ami.nav.floor", timeout_s=0.0)
    assert len(driver.queries) == 1, (
        f"wait_visible_id issued {len(driver.queries)} queries for a single "
        f"zero-length budget — the inner backoff is nested inside the wait."
    )


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
