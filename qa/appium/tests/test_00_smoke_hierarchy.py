"""GO/NO-GO gate — run this first, always.

AMI Trade has no `enableFlutterDriverExtension()` call anywhere, so this
harness's whole premise is that a plain black-box driver can still see the app
through the platform accessibility tree, against the same release artifact users
get. That premise holds differently on the two platforms, and this file is where
the difference is proven rather than assumed:

- **Android** builds the tree as soon as an accessibility client (UiAutomator2's
  own server) interrogates the window. No app cooperation needed — which is why
  CR080 shipped without touching `mobile/lib/`.
- **iOS** does not. The engine gates the tree on
  `UIAccessibilityIsVoiceOverRunning() || UIAccessibilityIsSwitchControlRunning()`
  (flutter#25485, open since 2018), so a normal build presents the entire app to
  XCUITest as one opaque `FlutterView` with an empty page source. CR162 added
  `--dart-define=AMI_QA_SEMANTICS=1`, which calls
  `SemanticsBinding.instance.ensureSemantics()` and forces the tree on.

So the first two tests here are not ceremony. They are the difference between a
suite that is testing the app and a suite that is testing a blank rectangle, and
they are written to say *which* when they fail.

If this file fails, do NOT trust anything else in this suite. The documented
next step is fixing the build or the accessibility path — never silently falling
back to coordinate-only interaction, which produces a green report against an
app nobody looked at.
"""

from __future__ import annotations

import pytest

from config.locales import LOCALES
from config.semantics_ids import NAV_IDS
from helpers.locators import exists_id, exists_text, wait_visible_text
from pages.base_page import TAB_LABELS

pytestmark = [pytest.mark.smoke, pytest.mark.phase1]

# A live Flutter screen exposes dozens of semantics nodes. One opaque
# FlutterView plus its window chrome is a handful. Anything at or below this is
# the collapsed-tree signature, not a sparse screen.
_MIN_PLAUSIBLE_NODES = 12


def test_semantics_identifiers_resolve(driver, device, run_dir):
    """THE gate (CR162). Every bottom-nav destination must be addressable by
    its `Semantics(identifier:)` — `resource-id` on Android,
    `accessibilityIdentifier` on iOS.

    This is the one check that distinguishes "the app is driveable" from "the
    driver is connected to something". It is also the staleness detector: an
    APK/IPA built before CR162 has no identifiers at all, and the melehost rig
    has shipped stale builds before (DEF224)."""
    driver.get_screenshot_as_file(str(run_dir / "screenshots" / "smoke__launch.png"))
    (run_dir / "page_source" / "smoke__launch.xml").write_text(driver.page_source)

    found = {tab: exists_id(driver, ident) for tab, ident in NAV_IDS.items()}
    missing = sorted(tab for tab, ok in found.items() if not ok)

    assert not missing, (
        f"bottom-nav destinations not addressable by semantics identifier: {missing}.\n"
        f"  platform: {device['platform']}\n"
        f"  If ALL five are missing, the cause is almost certainly the BUILD, not the app:\n"
        f"    - iOS: the build needs --dart-define=AMI_QA_SEMANTICS=1 (CR162). Without it\n"
        f"      Flutter never builds the semantics tree unless VoiceOver is running, and\n"
        f"      XCUITest sees one opaque FlutterView.\n"
        f"    - Either platform: the artifact under test predates CR162 and has no\n"
        f"      Semantics(identifier:) at all — check the build actually shipped\n"
        f"      (Android: scripts/share_apk_to_tester.sh; DEF224).\n"
        f"  If only SOME are missing, mobile/lib/qa/semantics_ids.dart and\n"
        f"  qa/appium/config/semantics_ids.py have drifted apart."
    )


def test_hierarchy_is_not_one_opaque_view(driver, device):
    """Direct proof that the semantics tree is populated, independent of any
    particular element.

    Worth having alongside the identifier gate because it distinguishes the two
    failure modes that otherwise look identical: a *collapsed tree* (nothing is
    addressable, the whole premise is broken) versus *missing identifiers* (the
    tree is fine, the build is just old)."""
    node_count = driver.page_source.count("<")
    assert node_count > _MIN_PLAUSIBLE_NODES, (
        f"the accessibility hierarchy has only ~{node_count} nodes on "
        f"{device['platform']} — that is the signature of a collapsed tree, i.e. "
        f"the app rendering as a single opaque view.\n"
        f"  On iOS this means AMI_QA_SEMANTICS was not set at build time.\n"
        f"  Do not proceed: every downstream test would fail in a way that looks "
        f"like an app bug and is not."
    )


def test_bottom_nav_text_resolves(driver):
    """Secondary: rendered text is findable too. Navigation no longer depends on
    this (CR162 moved it to identifiers), but `test_locale_matrix.py` asserts on
    copy, so the text path still has to work.

    Uses the locale table rather than the semantic keys — the on-screen strings
    are the uppercase ARB values, not the English key names."""
    labels = LOCALES["en"].tab_labels
    found = {tab: exists_text(driver, labels[tab]) for tab in TAB_LABELS}
    missing = sorted(tab for tab, ok in found.items() if not ok)
    assert not missing, (
        f"bottom-nav labels not found via text locator: {missing} "
        f"(looked for {[labels[t] for t in missing]}). The identifier gate above "
        f"passing while this fails would mean the tree is fine but the copy "
        f"changed — check mobile/lib/l10n/app_en.arb against config/locales.py."
    )


def test_bottom_band_is_plausible(device):
    """Sanity-check the bottom-obstruction read before any mechanical check
    relies on it. On Android this is a live dumpsys parse; on iOS it is the
    documented 34pt home-indicator constant, and `navbar_top_y_measured` says
    which — so a failure here is read correctly instead of blamed on the
    parse."""
    _width, height = device["display"]
    bottom_y = device["navbar_top_y"]
    measured = device["navbar_top_y_measured"]

    assert 0 < bottom_y < height, (
        f"navbar_top_y={bottom_y} is outside the display height {height} "
        f"(measured={measured}). On Android the dumpsys parse likely failed onto "
        f"the fallback constant — check helpers/device.obstructed_bottom_y's two "
        f"regexes against this device's actual output."
    )
    assert bottom_y > height * 0.85, (
        f"navbar_top_y={bottom_y} claims the bottom system band occupies more "
        f"than 15% of a {height}-unit display — implausible, re-check the parse "
        f"(measured={measured})."
    )


def test_scale_is_plausible(device):
    """The points-vs-pixels ratio. 1.0 on Android; a Retina iPhone is 2 or 3.
    A wrong value here does not error — it silently crops the wrong region in
    every screenshot diff, so it is asserted rather than trusted."""
    scale = device["scale"]
    if device["platform"] == "android":
        assert scale == 1.0, f"Android should report scale 1.0, got {scale}"
    else:
        assert 1.0 <= scale <= 4.0, (
            f"iOS scale={scale} is outside the plausible 1–4 range; "
            f"screenshot-diff bands would be cropped from the wrong region"
        )


def test_floor_tab_is_default_landing(driver, run_dir):
    """Confirms the app actually launched into the shell (not stuck on
    onboarding/a splash) — the precondition every other Phase 1 test assumes
    via noReset."""
    element = wait_visible_text(driver, LOCALES["en"].tab_labels["Floor"], timeout_s=15)
    assert element is not None
    driver.get_screenshot_as_file(str(run_dir / "screenshots" / "smoke__floor_landing.png"))
