"""Phase 3 (CR080) — multi-language UAT matrix: EN / AR / MS.

Switches the in-app language override (Settings -> Language,
mobile/lib/i18n/locale_provider.dart, A11) rather than the device/OS locale —
that's app-level Riverpod state persisted via SharedPreferences, the same
control a real user has, and switching it re-renders MaterialApp immediately
with no relaunch needed.

Why this matters beyond "does the translation exist": translated strings
change length. A Portfolio header that fits at "TOTAL VALUE" (11 chars) can
overflow at "القيمة الإجمالية" or wrap a fixed-height Row never sized for it —
exactly Saiful's original ask ("screens that do not scroll when they need
to"), just triggered by locale instead of by data volume. So every tab here
re-runs the same two Phase 1 mechanical checks (scroll-overflow, nav-bar
overlap) per locale, not just a content probe.

RTL adds a second, distinct failure class: Arabic mirrors layout
(Directionality.rtl) automatically for standard Flutter widgets, but that
only holds for widgets that don't hardcode `textDirection` or paint their own
canvas. HexBottomNav (mobile/lib/widgets/hex/hex_bottom_nav.dart) is a plain
Row with no override, so it's expected to mirror — test_bottom_nav_mirrors_
under_rtl below is a structural check on that guarantee, not a heuristic,
so it hard-asserts (unlike the scroll/navbar checks, which only record a
finding for human triage).

Content strings are pulled from config/locales.py, itself copied verbatim
from the live ARBs (see that file's docstring for the real translation gaps
already found this way — untranslated "Floor" tab in AR/MS, mixed-script
"CONVENE الغرفة" heading in AR — flagged to Saiful, not fixed here; this
harness ships test tooling only, never app copy).
"""

from __future__ import annotations

import pytest
from selenium.common.exceptions import NoSuchElementException

from conftest import snap
from config.locales import LOCALES
from helpers.gestures import screenshot_png
from helpers.layout import find_navbar_overlaps, find_scroll_overflow
from helpers.locale_switch import switch_locale
from helpers.locators import all_by_text, interactive_elements, wait_visible_text
from helpers.report import annotate_png
from pages.base_page import content_band, open_tab, probe_content

pytestmark = [pytest.mark.phase3, pytest.mark.locale]

_LOCALE_CODES = ("en", "ar", "ms")

# base_page.TAB_LABELS key -> config/locales.py strings keys hard-asserted on
# that tab, structurally guaranteed at the top of the screen with no scroll
# or data dependency (same split Phase 1's tests/test_*.py already made).
_TAB_CONTENT_KEYS = {
    "Floor": ("floor_concierge_heading",),
    "Portfolio": ("portfolio_total_value", "portfolio_cash"),
    "Journal": ("journal_filter_all",),
    "Settings": ("settings_mandate",),
}


@pytest.fixture(scope="module", autouse=True)
def _reset_to_english_after_module(driver):
    yield
    try:
        switch_locale(driver, "en")
    except Exception as exc:  # best-effort hygiene, never mask a real test failure
        print(f"(locale-matrix teardown reset to English also failed: {exc})")


def _bottom_nav_tab_center_x(driver, text: str) -> float:
    """The bottom-nav cell, not any other on-screen element sharing the same
    text — Arabic has no case distinction, so e.g. tabSettings and
    settingsHeading are the identical string 'الإعدادات' where their EN/MS
    equivalents differ by case ('Settings' vs 'SETTINGS'). The nav cell is
    always the lowest such element on screen (pinned via Scaffold's
    bottomNavigationBar slot), so picking max-y disambiguates it."""
    candidates = all_by_text(driver, text)
    if not candidates:
        raise NoSuchElementException(f"no element with exact text {text!r}")
    element = max(candidates, key=lambda e: e.rect["y"])
    rect = element.rect
    return rect["x"] + rect["width"] / 2


@pytest.mark.parametrize("locale", _LOCALE_CODES)
def test_tab_content_and_scroll_per_locale(driver, device, run_dir, flags, locale):
    switch_locale(driver, locale)
    profile = LOCALES[locale]
    band = content_band(device)

    for tab_key, content_keys in _TAB_CONTENT_KEYS.items():
        open_tab(driver, tab_key, locale=locale)
        exact = tuple(profile.strings[k] for k in content_keys)
        signals = probe_content(driver, f"{tab_key.lower()} [{locale}]", exact=exact)
        for content_key, string in zip(content_keys, exact):
            assert signals[string], (
                f"{tab_key} ({locale}) should show {content_key}={string!r} — "
                "structurally guaranteed at the top of the screen in every locale "
                "(see tests/test_*.py for the EN version of this same assertion)"
            )
        snap(driver, run_dir, f"tab_{tab_key.lower()}", locale)

        findings = find_scroll_overflow(
            driver, band, device["navbar_top_y"],
            screen=f"tab_{tab_key.lower()} [{locale}]", scale=device["scale"],
        )
        for finding in findings:
            flags.add(finding)
        if findings:
            annotate_png(
                screenshot_png(driver),
                run_dir / "screenshots" / f"tab_{tab_key.lower()}__{locale}__scroll_overflow.png",
                navbar_top_y=device["navbar_top_y"],
                scale=device["scale"],
            )


@pytest.mark.parametrize("locale", _LOCALE_CODES)
def test_lessons_honeycomb_per_locale(driver, run_dir, locale):
    """Lessons has no fixed hard-assert string in any locale — the honeycomb
    is built from backend lesson-catalogue content (see tests/test_lessons.py
    for why category names aren't asserted). Same clickable-count richness
    signal, just re-run after a locale switch in case translated labels
    (FittedBox + scaleDown, see hex_bottom_nav.dart's label-fit comment,
    though this is the Lessons grid not the nav cell) collapse the grid."""
    switch_locale(driver, locale)
    open_tab(driver, "Lessons", locale=locale)
    clickable_count = len(interactive_elements(driver))
    print(f"    [lessons {locale}] {clickable_count} clickable element(s)")
    assert clickable_count > 3, (
        f"only {clickable_count} clickable elements on Lessons ({locale}) — honeycomb may be empty"
    )
    snap(driver, run_dir, "lessons", locale)


@pytest.mark.parametrize("locale", _LOCALE_CODES)
def test_convene_sheet_per_locale(driver, device, run_dir, flags, locale):
    switch_locale(driver, locale)
    profile = LOCALES[locale]
    open_tab(driver, "Floor", locale=locale)
    cta = wait_visible_text(driver, profile.strings["floor_convene_cta"], timeout_s=10)
    cta.click()
    wait_visible_text(driver, profile.strings["convene_confirm"], timeout_s=8)
    snap(driver, run_dir, "convene_sheet", locale)

    navbar_findings = find_navbar_overlaps(driver, device["navbar_top_y"], screen=f"convene_sheet [{locale}]")
    scroll_findings = find_scroll_overflow(
        driver, content_band(device), device["navbar_top_y"],
        screen=f"convene_sheet [{locale}]", scale=device["scale"],
    )
    for finding in navbar_findings + scroll_findings:
        flags.add(finding)
    if navbar_findings:
        annotate_png(
            screenshot_png(driver),
            run_dir / "screenshots" / f"convene_sheet__{locale}__navbar_overlap.png",
            navbar_top_y=device["navbar_top_y"],
            boxes=[tuple(f["bounds"]) for f in navbar_findings],
            scale=device["scale"],
        )
    driver.back()

    high = [f for f in navbar_findings if f["severity"] == "high"]
    assert not high, f"convene_sheet ({locale}): {len(high)} element(s) with center under the nav bar: {high}"


@pytest.mark.parametrize("locale", _LOCALE_CODES)
def test_bottom_nav_mirrors_under_rtl(driver, flags, locale):
    """HexBottomNav is a plain Row over a fixed-order item list with no
    explicit textDirection override, so Flutter mirrors it automatically
    under ambient RTL Directionality like any other Row — a structural
    guarantee, not a heuristic. "Floor" is the first item (leftmost under
    LTR, rightmost under RTL); "Settings" is the last (mirrored the other
    way). Unlike the scroll/navbar checks above, a mismatch here is a
    confirmed bug, so this hard-asserts instead of only recording a finding.
    """
    switch_locale(driver, locale)
    profile = LOCALES[locale]
    floor_x = _bottom_nav_tab_center_x(driver, "Floor")  # tabFloor untranslated in every locale today
    settings_x = _bottom_nav_tab_center_x(driver, profile.tab_labels["Settings"])
    mirrored = floor_x > settings_x

    if mirrored != profile.rtl:
        flags.add(
            {
                "check": "rtl_mirroring",
                "screen": f"bottom_nav [{locale}]",
                "severity": "high",
                "suggested_category": "ui_glitch",
                "note": (
                    f"expected mirrored={profile.rtl} for locale={locale!r} (rtl={profile.rtl}) but "
                    f"bottom-nav gave mirrored={mirrored} (Floor center_x={floor_x}, "
                    f"Settings center_x={settings_x})"
                ),
            }
        )

    assert mirrored == profile.rtl, (
        f"HexBottomNav did not mirror as expected under locale={locale!r} (rtl={profile.rtl}): "
        f"Floor center_x={floor_x}, Settings center_x={settings_x}"
    )
