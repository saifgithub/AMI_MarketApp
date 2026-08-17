"""DEF325 — the glossary the device carries is a second copy, and it drifted.

`content/glossary/terms.<locale>.json` is the corpus. The Flutter reader does
not read it. `TermRegistry._loadLocale` (`mobile/lib/widgets/lessons/
term_registry.dart`) loads `assets/glossary/terms.<locale>.json` out of the
app bundle — deliberately, so an inline `<Term/>` chip never costs a network
round trip mid-lesson. That is the right call for the reader and it creates a
second derivation of one fact (DEF098), with nothing anywhere comparing them.

They drifted, measured 2026-08-17: the bundled EN asset was written once, at
`30c60148`, and never again; the corpus has moved three times since. **188 ids
on the device against 208 in content** — the 20 missing are the entire
Islamic-finance set CR058-SUPPORT added (`halal`, `riba`, `sukuk`, `gharar`,
`sharia_screening`, …), so a halal-flagged user tapping one of those terms gets
the prettified id instead of a definition. Two shared entries had also drifted
in text, one of them `ami_coach_your_agent`, which on the device still read
under the pre-AT:R27 name **"Coach Your Agent"** while every other surface in
the app says "Brief Your Agent".

No lesson body broke, which is why nothing surfaced it: no `<Term/>` in the
corpus references any of the 20, so the drift was only reachable through the
term sheet's `see_also` links and through a future lesson that used one. It was
found while investigating DEF199 (a report of a placeholder in RISK 16), and it
is not that defect's cause — RISK 16's own four terms all resolve in the stale
asset too.

**The fix is this file, not the copy.** Re-copying the asset fixes it once; a
test that fails when the two disagree is what stops the fourth divergence. Kept
in the backend suite rather than as a Flutter test because this suite runs in
the promotion preflight, and shipping a stale glossary is a promotion-time
mistake.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]
_CONTENT = _REPO / "content" / "glossary"
_BUNDLED = _REPO / "mobile" / "assets" / "glossary"


def _bundled_locales() -> list[str]:
    return sorted(p.name.split(".")[1] for p in _BUNDLED.glob("terms.*.json"))


def test_english_is_bundled_at_all():
    """The one locale alpha ships. A missing asset is not loud: `_loadLocale`
    catches everything and caches an empty map, so every `<Term/>` in all 348
    lessons would silently render as its prettified id."""
    assert "en" in _bundled_locales(), (
        "mobile/assets/glossary/terms.en.json is gone — the reader will resolve "
        "no glossary term at all, and it will not say so"
    )


@pytest.mark.parametrize("locale", _bundled_locales())
def test_the_bundled_glossary_matches_the_corpus(locale: str):
    """Compared as parsed JSON, not bytes: formatting is not the fact, the
    entries are, and a byte compare would fail on a trailing newline and teach
    everyone to ignore it."""
    corpus = json.loads((_CONTENT / f"terms.{locale}.json").read_text("utf-8"))
    bundled = json.loads((_BUNDLED / f"terms.{locale}.json").read_text("utf-8"))

    by_id_c = {e["id"]: e for e in corpus}
    by_id_b = {e["id"]: e for e in bundled}

    missing = sorted(set(by_id_c) - set(by_id_b))
    extra = sorted(set(by_id_b) - set(by_id_c))
    drifted = sorted(i for i in set(by_id_c) & set(by_id_b) if by_id_c[i] != by_id_b[i])

    assert not (missing or extra or drifted), (
        f"mobile/assets/glossary/terms.{locale}.json has drifted from "
        f"content/glossary/terms.{locale}.json — re-copy it.\n"
        f"  in content, absent on device ({len(missing)}): {missing}\n"
        f"  on device, absent in content ({len(extra)}): {extra}\n"
        f"  present in both, text differs ({len(drifted)}): {drifted}"
    )


def test_every_bundled_locale_exists_in_the_corpus():
    """The other direction: an asset with no corpus file behind it is a copy
    nobody can maintain, and the parity test above would not see it."""
    orphans = [
        loc for loc in _bundled_locales() if not (_CONTENT / f"terms.{loc}.json").exists()
    ]
    assert not orphans, f"bundled glossary locales with no corpus source: {orphans}"
