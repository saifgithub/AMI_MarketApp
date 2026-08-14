"""Offline guards for `pages/base_page.py`'s navigation.

CR133 restructured the bottom nav — SETTINGS and JOURNAL stopped being
destinations and became segments of YOU — and three test modules went on
calling `open_tab(driver, "Settings")` / `open_tab(driver, "Journal")` for
months afterwards. Nothing caught it on the Mac because the harness's tests
only ever ran against a device, and on the device it failed as an AssertionError
inside a suite that already had unrelated red, so it read as noise.

These run with no device and no Appium server, so the *next* nav restructure
fails here, in milliseconds, with the reason spelled out.
"""

from __future__ import annotations

import pytest

from config.locales import LOCALES
from config.semantics_ids import NAV_IDS, YOU_SEGMENT_IDS
from pages.base_page import TAB_LABELS, open_tab, open_you_segment


class FakeElement:
    def __init__(self):
        self.clicks = 0

    def click(self):
        self.clicks += 1


class FakeDriver:
    """Resolves any `resourceId(...)` UiSelector to a distinct element and
    records the tap order — which is the thing under test here, since a
    navigation helper's whole job is *which* handles it touches, in what order.
    """

    def __init__(self, *, resolve: bool = True):
        self.capabilities = {"platformName": "Android"}
        self.resolve = resolve
        self.tapped: list[str] = []
        self.queried: list[str] = []
        self._elements: dict[str, FakeElement] = {}

    def find_elements(self, by, value):
        self.queried.append(value)
        if not self.resolve:
            return []
        element = self._elements.setdefault(value, FakeElement())
        original_click = element.click

        def click():
            self.tapped.append(value)
            original_click()

        element.click = click
        return [element]


def _ids(queries: list[str]) -> list[str]:
    """The identifier inside each `resourceId("…")` selector, in order."""
    out = []
    for q in queries:
        if 'resourceId("' in q:
            out.append(q.split('resourceId("')[1].split('"')[0])
    return out


def test_the_bottom_nav_has_exactly_the_destinations_the_app_ships():
    """`TAB_LABELS` and `NAV_IDS` are two hand-maintained mirrors of one list.
    CR133 edited the app and only one of them would have been noticed."""
    assert set(TAB_LABELS) == set(NAV_IDS), (
        f"TAB_LABELS {TAB_LABELS} and NAV_IDS {tuple(NAV_IDS)} disagree about "
        f"what the bottom nav contains."
    )


@pytest.mark.parametrize("retired", ["Settings", "Journal"])
def test_the_retired_destinations_fail_loudly_not_silently(retired):
    """CR133 made these segments of YOU. `open_tab` must reject them by name —
    a helper that quietly tapped nothing would leave the caller asserting
    against whatever screen happened to be up."""
    with pytest.raises(AssertionError, match="not a known bottom-nav tab"):
        open_tab(FakeDriver(), retired)


def test_open_you_segment_goes_through_the_you_tab_first():
    """A segment is only reachable once its tab is on screen. Tapping the
    segment identifier alone resolves fine on a stale tree and does nothing."""
    driver = FakeDriver()
    open_you_segment(driver, "Settings")

    assert _ids(driver.queried)[:2] == [NAV_IDS["You"], YOU_SEGMENT_IDS["Settings"]]
    assert driver.tapped == [
        f'new UiSelector().resourceId("{NAV_IDS["You"]}")',
        f'new UiSelector().resourceId("{YOU_SEGMENT_IDS["Settings"]}")',
    ], "both the tab and the segment must actually be tapped, in that order"


def test_open_you_segment_rejects_a_name_that_is_not_a_segment():
    with pytest.raises(AssertionError, match="not a YOU segment"):
        open_you_segment(FakeDriver(), "Portfolio")


def test_the_segment_text_fallback_exists_for_every_locale():
    """The fallback only fires on a build older than the YOU identifiers, so it
    is exactly the path that never gets exercised until it is needed. A missing
    key would raise KeyError there — inside the recovery path, on the device,
    at the worst moment."""
    for code, profile in LOCALES.items():
        for segment in YOU_SEGMENT_IDS:
            key = f"you_segment_{segment.lower()}"
            assert profile.strings.get(key), (
                f"config/locales.py[{code!r}] has no {key!r}; "
                f"base_page.open_you_segment's fallback reads it."
            )
