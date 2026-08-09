"""Mirror of `mobile/lib/qa/semantics_ids.dart` — the app<->harness element
contract (CR162).

The app sets these via Flutter's `Semantics(identifier: …)`, which the engine
maps to **`resource-id` on Android** and **`accessibilityIdentifier` on iOS**.
They ship in release builds and render nothing, so the same release artifact
CR080 already tests is addressable by ID on both platforms — no instrumented
build, no `enableFlutterDriverExtension()`.

Why this matters beyond iOS: before CR162 this harness located everything by
*rendered text*, so `config/locales.py` had to carry every EN/AR/MS string
verbatim just to tap a bottom-nav tab. Navigation was coupled to translation and
any ARB copy edit could break the suite. Navigate by ID; assert on text only
where the text is the thing under test (that is what `test_locale_matrix.py` is
for).

Keep in sync with the Dart file. `mobile/test/qa/semantics_ids_test.dart` fails
if the app side drops one; `tests/test_00_smoke_hierarchy.py` fails if the
running build does not expose them.
"""

from __future__ import annotations

# Bottom-nav destinations, in on-screen order. Keys are the same
# locale-independent semantic names `pages/base_page.py::TAB_LABELS` uses.
NAV_IDS: dict[str, str] = {
    "Floor": "ami.nav.floor",
    "Portfolio": "ami.nav.portfolio",
    "Journal": "ami.nav.journal",
    "Lessons": "ami.nav.lessons",
    "Settings": "ami.nav.settings",
}

# Modal sheets — the DEF075 class the nav-bar/bottom-inset check exists for.
SHEET_CONVENE = "ami.sheet.convene"
SHEET_CONVENE_CTA = "ami.sheet.convene.cta"
SHEET_MERGE = "ami.sheet.merge"
SHEET_MERGE_CTA = "ami.sheet.merge.cta"
