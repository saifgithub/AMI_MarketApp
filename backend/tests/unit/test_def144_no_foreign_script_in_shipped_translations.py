"""DEF144 — no code-switched foreign script survives in committed ar/ms content.

The on-prem model (Qwen3.6-35B-A3B-NVFP4, quantized) code-switches mid-generation
at a measured ~3-4%: a Chinese, Cyrillic or Japanese word glued into otherwise
correct Arabic or Malay, sometimes severing a target-language word to do it
(`بنفس الق因为它们` for `بنفس القدر`). It reached **user-facing quiz options** and
**19 already-committed files** before anything checked.

`scripts/_i18n_script_guard.py` was built for it and is wired into all four LAN
translate scripts — but that is a **generation-time filter**, and it can only
protect text that happens to be produced by those scripts. Nothing checked the
corpus. A hand edit, a restored file, a paste, or a future tool that forgets to
call the filter all land unexamined, and the failure is invisible on review
unless the reader happens to read Arabic.

So this is the same rule enforced one layer out: not "the generator filtered it"
but "the repository does not contain it". Saiful's ruling in the 2026-07-28
daily review was *"build the detector, then re-run"*; the detector exists and the
re-run is clean — measured here at **714 artifacts, 0 genuine leaks** — and this
test is what makes that a property rather than a snapshot.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "scripts"))

from _i18n_script_guard import foreign_script_leak  # noqa: E402

#: Strings that legitimately carry another script, with the reason. A language
#: picker MUST render each language in its own script — showing "Arabic" to an
#: Arabic reader in Latin letters is the bug, not the fix. Keyed by ARB key so
#: the exemption cannot silently widen to a whole file.
LEGITIMATE_FOREIGN_SCRIPT_KEYS = {
    "settingsLanguageArabic": "the language picker renders Arabic in Arabic",
}

_LOCALES = ("ar", "ms")


def _content_files(locale: str) -> list[Path]:
    out = list((_ROOT / "content" / "lessons").glob(f"*.{locale}.mdx"))
    for sub in ("ai_coach", "daily_challenges"):
        d = _ROOT / "content" / sub / locale
        if d.exists():
            out += sorted(d.glob("*.json"))
    g = _ROOT / "content" / "glossary" / f"terms.{locale}.json"
    if g.exists():
        out.append(g)
    return sorted(out)


def test_the_detector_still_detects():
    """Vacuity, and not a formality: every assertion below is 'no leak found',
    so a detector that silently stopped matching would turn this whole file
    green while the corpus rotted. Uses the exact string from the defect."""
    assert foreign_script_leak("بنفس الق因为它们 تأتيان", "ar") is not None
    assert foreign_script_leak("Nilai книга tersebut", "ms") is not None
    assert foreign_script_leak("نص عربي سليم تماما", "ar") is None
    assert foreign_script_leak("Teks Melayu yang betul", "ms") is None


@pytest.mark.parametrize("locale", _LOCALES)
def test_enough_files_exist_for_this_to_mean_anything(locale):
    files = _content_files(locale)
    assert len(files) >= 100, (
        f"only {len(files)} {locale} content files found — the corpus did not "
        "load and every leak assertion below would pass trivially"
    )


@pytest.mark.parametrize("locale", _LOCALES)
def test_no_foreign_script_in_translated_content(locale):
    offenders = []
    for path in _content_files(locale):
        snippet = foreign_script_leak(path.read_text(encoding="utf-8"), locale)
        if snippet:
            offenders.append(f"{path.relative_to(_ROOT)}: …{snippet}…")
    assert not offenders, (
        f"{len(offenders)} {locale} file(s) contain a foreign script. This is "
        "the model code-switching mid-generation (DEF144) — it has reached "
        "user-facing quiz options before. Regenerate the file through the LAN "
        "translate scripts, which call the same detector at generation time:\n"
        + "\n".join(offenders)
    )


@pytest.mark.parametrize("locale", _LOCALES)
def test_no_foreign_script_in_the_mobile_arb(locale):
    """Checked per KEY rather than whole-file, because one legitimate exemption
    exists and a whole-file skip would blind the other ~1,250 strings."""
    import json

    arb = json.loads(
        (_ROOT / "mobile" / "lib" / "l10n" / f"app_{locale}.arb").read_text(
            encoding="utf-8"
        )
    )
    offenders = []
    for key, value in arb.items():
        if key.startswith("@") or not isinstance(value, str):
            continue
        if key in LEGITIMATE_FOREIGN_SCRIPT_KEYS:
            continue
        snippet = foreign_script_leak(value, locale)
        if snippet:
            offenders.append(f"{key}: …{snippet}…")
    assert not offenders, (
        f"{len(offenders)} string(s) in app_{locale}.arb contain a foreign "
        f"script (DEF144): {offenders}"
    )


def test_every_exemption_still_earns_its_place():
    """An exemption that no longer applies is a hole nobody is watching —
    DEF295's 'marker outlives its key', applied to an allowlist."""
    import json

    stale = []
    for key in LEGITIMATE_FOREIGN_SCRIPT_KEYS:
        found = False
        for locale in _LOCALES:
            arb = json.loads(
                (_ROOT / "mobile" / "lib" / "l10n" / f"app_{locale}.arb").read_text(
                    encoding="utf-8"
                )
            )
            value = arb.get(key)
            if isinstance(value, str) and foreign_script_leak(value, locale):
                found = True
        if not found:
            stale.append(key)
    assert not stale, (
        f"exemption(s) that no longer carry a foreign script — remove them "
        f"rather than leaving an unguarded key: {stale}"
    )
