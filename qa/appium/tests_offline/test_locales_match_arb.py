"""DEF250 — the locale table must match the strings the app actually renders.

`config/locales.py` was hand-copied from `tabFloor`/`tabPortfolio`/… — ARB keys
that exist, generate into `app_localizations*.dart`, and are referenced by no
screen. The bottom nav renders `floorTabUpper`/`portfolioTabUpper`/….

Nothing caught it for two weeks. CR080 recorded the strings as "copied verbatim
from the live ARBs — never guessed", and they were verbatim; they were just the
wrong keys, which no amount of care in the copying would have caught. So the
guard is a mechanical comparison against the ARB, not a more careful copy.

Skips rather than fails when `mobile/` is absent: on melehost the harness is
rsync'd on its own, and a skip there is honest where a failure would be noise.
The check runs on the Mac and in CI, which is where a drift would be introduced.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from config.locales import LOCALES

# base_page.TAB_LABELS key -> the ARB key home_shell.dart actually renders.
TAB_ARB_KEYS = {
    "Floor": "floorTabUpper",
    "Portfolio": "portfolioTabUpper",
    "Lessons": "lessonsTabUpper",
    "You": "youTabUpper",
}

# locales.py `strings` key -> the ARB key YOU's segment bar renders.
#
# Deliberately NOT the *Heading keys: `you_screen.dart` builds its AmiSegments
# from `settingsTabUpper`/`journalTabUpper`, so the EN journal segment says
# "JOURNAL" where the retired standalone screen said "DECISION JOURNAL". That
# near-miss is the DEF250 shape exactly — a verbatim copy of a plausible,
# wrong key — so it gets the same mechanical check.
YOU_SEGMENT_ARB_KEYS = {
    "you_segment_settings": "settingsTabUpper",
    "you_segment_journal": "journalTabUpper",
    "you_segment_insights": "youSegmentInsights",
}

# Every `strings` key -> the ARB key the app renders it from. Kept complete on
# purpose: the dead-key check below can only cover what is mapped, so an
# unmapped entry is an untested one, and `test_every_string_is_mapped` fails if
# this drifts from `config/locales.py`.
STRING_ARB_KEYS = {
    "floor_omnibox_hint": "floorOmniboxHint",
    "floor_convene_cta": "floorConveneCta",
    "convene_confirm": "conveneCta",
    "portfolio_heading": "portfolioHeading",
    "portfolio_total_value": "portfolioTotalValue",
    "portfolio_cash": "portfolioCash",
    "journal_heading": "journalHeading",
    "journal_filter_all": "journalFilterAll",
    "lessons_heading": "lessonsHeading",
    "settings_heading": "settingsHeading",
    "settings_mandate": "settingsSectionMandate",
    **YOU_SEGMENT_ARB_KEYS,
}

_ARB_DIR = Path(__file__).resolve().parents[3] / "mobile" / "lib" / "l10n"
_LIB_DIR = Path(__file__).resolve().parents[3] / "mobile" / "lib"


def _arb(locale: str) -> dict:
    path = _ARB_DIR / f"app_{locale}.arb"
    if not path.exists():
        pytest.skip(f"{path} not present — harness delivered without mobile/")
    return json.loads(path.read_text())


@pytest.mark.parametrize("locale", sorted(LOCALES))
def test_tab_labels_match_the_rendered_arb_keys(locale):
    arb = _arb(locale)
    profile = LOCALES[locale]

    mismatches = []
    for tab, arb_key in TAB_ARB_KEYS.items():
        expected = arb.get(arb_key)
        actual = profile.tab_labels.get(tab)
        if expected != actual:
            mismatches.append(f"{tab}: app renders {expected!r}, harness expects {actual!r}")

    assert not mismatches, (
        f"DEF250: config/locales.py[{locale!r}].tab_labels has drifted from the "
        f"strings the app renders:\n  " + "\n  ".join(mismatches) + "\n"
        f"home_shell.dart renders the *TabUpper keys. Do not hand-copy these — "
        f"the original defect was a verbatim copy of the WRONG key set "
        f"(tabFloor/tabPortfolio/…, which no screen references)."
    )


@pytest.mark.parametrize("locale", sorted(LOCALES))
def test_every_string_matches_the_arb_it_claims_to_copy(locale):
    """The table says the strings are verbatim copies. This checks that they
    still are, for every one — not just the tab labels."""
    arb = _arb(locale)
    profile = LOCALES[locale]

    mismatches = []
    for key, arb_key in STRING_ARB_KEYS.items():
        if key not in profile.strings:
            continue
        expected = arb.get(arb_key)
        actual = profile.strings[key]
        if expected != actual:
            mismatches.append(f"{key} ({arb_key}): app renders {expected!r}, harness expects {actual!r}")

    assert not mismatches, (
        f"config/locales.py[{locale!r}].strings has drifted from the ARB:\n  "
        + "\n  ".join(mismatches)
    )


@pytest.mark.parametrize("locale", sorted(LOCALES))
def test_you_segment_labels_match_the_rendered_arb_keys(locale):
    arb = _arb(locale)
    profile = LOCALES[locale]

    mismatches = []
    for key, arb_key in YOU_SEGMENT_ARB_KEYS.items():
        expected = arb.get(arb_key)
        actual = profile.strings.get(key)
        if expected != actual:
            mismatches.append(f"{key}: app renders {expected!r}, harness expects {actual!r}")

    assert not mismatches, (
        f"config/locales.py[{locale!r}].strings has drifted from YOU's segment "
        f"bar:\n  " + "\n  ".join(mismatches) + "\n"
        f"you_screen.dart builds its AmiSegments from the *TabUpper keys "
        f"(+ youSegmentInsights), not the *Heading keys."
    )


def test_every_string_is_mapped_to_an_arb_key():
    """An unmapped string is one the dead-key check silently skips, which is
    the same shape as the bug it exists to catch."""
    unmapped = set(LOCALES["en"].strings) - set(STRING_ARB_KEYS)
    assert not unmapped, (
        f"config/locales.py has strings with no ARB key mapped here: "
        f"{sorted(unmapped)}. Add them to STRING_ARB_KEYS."
    )


@pytest.mark.parametrize("key, arb_key", sorted(STRING_ARB_KEYS.items()))
def test_no_string_is_asserted_against_a_key_no_screen_renders(key, arb_key):
    """DEF250, second occurrence — and this time the mechanical check.

    `floorConciergeHeading` = "AMI CONCIERGE" survived in all three ARBs and in
    the generated `app_localizations*.dart` long after the Floor redesign moved
    the Concierge access point into the omnibox. Nothing referenced it. The
    harness went on hard-asserting it, so `test_floor_renders_convene_cta`
    could not pass however healthy the app was — and it took a live device run
    to notice, exactly as DEF250 did.

    Existing in the ARB is not the property that matters; being *rendered* is.
    Generated localizations are excluded because they define every key by
    construction and would make every dead key look alive — which is precisely
    how this one hid.
    """
    if not _LIB_DIR.exists():
        pytest.skip("mobile/ not present — harness delivered on its own")

    referenced = [
        path
        for path in _LIB_DIR.rglob("*.dart")
        if "generated" not in path.parts and f".{arb_key}" in path.read_text()
    ]
    assert referenced, (
        f"config/locales.py asserts {key!r} against ARB key {arb_key!r}, which "
        f"no screen or widget references — only the ARBs and the generated "
        f"localizations still carry it. Any test asserting it is unsatisfiable. "
        f"Point the harness at whatever replaced it, or drop the string."
    )


def test_the_dead_keys_are_not_what_we_read():
    """Pins the actual mistake, not just its symptom.

    If someone 'fixes' a future mismatch by pointing the table back at the
    `tab*` keys — they look like the obvious choice, which is exactly why this
    happened — the values would agree with an ARB and disagree with the screen.
    This fails in that case, while the test above would pass.
    """
    arb = _arb("en")
    dead = {k: arb[k] for k in ("tabFloor", "tabPortfolio") if k in arb}
    if not dead:
        pytest.skip("the dead tab* keys have since been removed from the ARB")

    assert LOCALES["en"].tab_labels["Floor"] != dead.get("tabFloor"), (
        "DEF250: the EN Floor label matches the DEAD `tabFloor` key rather than "
        "the rendered `floorTabUpper`. No screen references tabFloor."
    )
