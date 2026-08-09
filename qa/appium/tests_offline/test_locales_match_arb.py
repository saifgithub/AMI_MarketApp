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
    "Journal": "journalTabUpper",
    "Lessons": "lessonsTabUpper",
    "Settings": "settingsTabUpper",
}

_ARB_DIR = Path(__file__).resolve().parents[3] / "mobile" / "lib" / "l10n"


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
