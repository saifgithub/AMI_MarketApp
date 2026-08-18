"""DEF144 — the Sharia carve-out has to hold against a script that never asks it.

`content/i18n/sensitive_keys.json` is the register of content AMI must not
machine-translate freely: Sharia-ruling-adjacent Q&A, the Islamic-finance lesson
unit, halal-screen UI strings whose own translator notes say things like
"'unscreened' must never become 'haram'".

It was consulted by the four standing CLI translate tools and by nothing else.
So when DEF144's own remediation needed a quick fix, an **ad-hoc direct-call
script** retranslated `qa_plt_halal_flag` — a `strict_review` entry — with no
awareness the register existed. The output happened to be sound, read by hand
afterwards. The row records the verdict on that plainly: *"Correct by luck of
careful review, not by design — the exclusion mechanism needs to actually gate
ad-hoc fixes too, not just the four standing CLI tools, or this recurs."*

That is CLAUDE.md's own rule in content form — **prompt instructions are not
controls**, and neither is "the tool is supposed to check". A gate living inside
the four tools is bypassed by not being one of the four tools.

This file is the gate that cannot be bypassed that way, because it does not sit
on the writing path at all: it sits on the **suite**. Whatever wrote the file —
a standing tool, an ad-hoc script, a hand edit, a future agent lane — the next
run compares the result against what was signed off, and an unacknowledged
change to Sharia-adjacent content goes red.

Two mechanisms, chosen per scope rather than uniformly:

  - **`exclude` / `arb_key`** — these keys are *pre-seeded with the literal EN
    value* so `translate_arb_lan.py`'s skip-unless-overwrite logic leaves them
    alone. So the invariant is not a fingerprint, it is an equality: the AR and
    MS values must still BE the English ones. That states the actual rule, and
    it is self-describing when it fails.
  - **everything else** — a content fingerprint against a committed baseline.

Coverage is derived from `sensitive_keys.json` itself, never hand-listed here
(CR175 F3): adding an entry to the register with no baseline reds this file, so
the register cannot outgrow its own guard silently.

Updating the baseline is not "making the test pass". It is the acknowledgement
that someone read the new text and stands behind it — which for this content
means a human, and for a ruling means Saiful or an SME.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]
_REGISTER = _REPO / "content" / "i18n" / "sensitive_keys.json"
_BASELINE = Path(__file__).with_suffix(".baseline.json")

_LOCALES = ("ar", "ms")


def _register() -> dict:
    return json.loads(_REGISTER.read_text(encoding="utf-8"))


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _translated_paths(entry: dict) -> list[Path]:
    """The AR/MS artifacts an entry governs. Derived from the entry's own
    `scope` + `file`, so a new scope shows up as an empty list and is caught by
    the coverage test below rather than silently skipped."""
    scope = entry.get("scope")
    out: list[Path] = []

    if scope == "lessons":
        for lesson_id in entry.get("ids", []):
            for loc in _LOCALES:
                out.append(_REPO / "content" / "lessons" / f"{lesson_id}.{loc}.mdx")
    elif scope in ("whole_file", "content_json_ids"):
        src = Path(entry["file"])
        # content/ai_coach/platform.json      -> content/ai_coach/{ar,ms}/platform.json
        # content/daily_challenges/2026_12.json -> content/daily_challenges/{ar,ms}/2026_12.json
        for loc in _LOCALES:
            out.append(_REPO / src.parent / loc / src.name)
    elif scope == "glossary_ids":
        for loc in _LOCALES:
            out.append(_REPO / "content" / "glossary" / f"terms.{loc}.json")

    return out


def _fingerprints() -> dict[str, str]:
    """Current fingerprint of every governed artifact that exists on disk."""
    prints: dict[str, str] = {}
    for entry in _register().get("strict_review", []) + _register().get("exclude", []):
        if entry.get("scope") == "arb_key":
            continue  # handled by the equality test, not by a fingerprint
        for p in _translated_paths(entry):
            if p.is_file():
                prints[str(p.relative_to(_REPO))] = _sha(p.read_text(encoding="utf-8"))
    return prints


# ── the `exclude` / arb_key rule, stated as what it actually is ────────────


def test_excluded_arb_keys_still_hold_the_english_value():
    """These are pre-seeded with the EN literal precisely so the translate tool
    skips them. If any AR/MS value has diverged from EN, something translated a
    key the register says must never be sent to a model — which is how
    'unscreened' becomes 'haram'."""
    arb = {
        loc: json.loads((_REPO / "mobile" / "lib" / "l10n" / f"app_{loc}.arb").read_text("utf-8"))
        for loc in ("en",) + _LOCALES
    }
    entries = [e for e in _register()["exclude"] if e.get("scope") == "arb_key"]
    assert entries, "the arb_key exclusion disappeared from the register"

    drifted = []
    for entry in entries:
        for key in entry["ids"]:
            for loc in _LOCALES:
                if arb[loc].get(key) != arb["en"].get(key):
                    drifted.append(f"{key} [{loc}]")

    assert not drifted, (
        "Sharia-screen UI strings that must be held to English have been "
        f"translated: {drifted}.\n"
        "These keys carry load-bearing translator notes in their own "
        "@description ('unscreened' must never become 'haram') and are routed "
        "to Saiful for external translation. Restore the EN literal, or — if "
        "an approved human translation has genuinely arrived — remove the key "
        "from sensitive_keys.json's arb_key exclusion in the same commit, so "
        "the decision is visible rather than absorbed."
    )


def test_the_arb_equality_check_is_not_vacuous():
    """If the ids list ever empties, the test above passes over nothing."""
    ids = [k for e in _register()["exclude"] if e.get("scope") == "arb_key" for k in e["ids"]]
    assert len(ids) >= 10, f"only {len(ids)} arb keys under exclusion — expected the CR069 set"


# ── the fingerprint rule for everything else ──────────────────────────────


def test_no_sensitive_translated_content_changed_without_acknowledgement():
    baseline = json.loads(_BASELINE.read_text(encoding="utf-8"))["fingerprints"]
    current = _fingerprints()

    changed = sorted(k for k in current if k in baseline and current[k] != baseline[k])
    removed = sorted(k for k in baseline if k not in current)

    assert not (changed or removed), (
        "Sharia-adjacent translated content changed without acknowledgement.\n"
        f"  changed: {changed}\n"
        f"  missing: {removed}\n\n"
        "sensitive_keys.json governs these files. The four standing CLI "
        "translate tools consult it; an ad-hoc script does not, and that is "
        "exactly how qa_plt_halal_flag got retranslated (DEF144) — the output "
        "was sound, but by careful review afterwards, not by design.\n\n"
        "This is not a test to silence. Read the new text. If it is correct — "
        "and for a ruling that means Saiful or an SME, not a model — update\n"
        f"    {_BASELINE.name}\n"
        "in the same commit, and flag `retranslate:[ar,ms]` per id if the EN "
        "source moved."
    )


def test_every_register_entry_is_covered_by_the_baseline():
    """CR175 F3 — coverage is derived from the register, never hand-listed, so
    a new sensitive entry cannot be added without a baseline to compare against.

    Two ways an entry escapes, and both are checked, because the first version
    of this test only caught one of them: a governed file that CHANGED with no
    baseline row, and a governed file that does not exist on disk at all. The
    second is the one that slipped — a new register entry pointing at an
    artifact nobody has generated yet resolves to nothing, `_fingerprints`
    skips it, and the entry reads as covered while governing zero bytes.
    """
    baseline = json.loads(_BASELINE.read_text(encoding="utf-8"))["fingerprints"]
    current = _fingerprints()

    uncovered = sorted(k for k in current if k not in baseline)
    assert not uncovered, (
        f"sensitive_keys.json now governs files with no baseline: {uncovered}. "
        f"Add their fingerprints to {_BASELINE.name} in the commit that added "
        "them, after reading the content."
    )

    # An entry that governs nothing is the alarm, not a pass.
    empty = []
    for entry in _register().get("strict_review", []):
        paths = _translated_paths(entry)
        if not paths:
            empty.append(f"{entry.get('scope')} — scope not understood by _translated_paths")
            continue
        if not any(p.is_file() for p in paths):
            empty.append(f"{entry.get('scope')}:{entry.get('file') or entry.get('ids')} "
                         f"— none of its {len(paths)} artifacts exist")
    assert not empty, (
        "these sensitive_keys.json entries govern no file this guard can see, so "
        f"they are protected by nothing: {empty}. Either the artifact has not been "
        "generated yet (then this entry is aspirational and should say so), or the "
        "scope\u2192path derivation in `_translated_paths` does not understand a new "
        "scope and is silently skipping it."
    )


def test_the_never_translate_file_has_no_translated_twin():
    """`content/ai_coach/islamic_finance.json` is `exclude`/`whole_file`: 15
    dedicated Sharia-ruling Q&A entries, routed to an SME, never sent to a
    model. Its correct state on disk is that **no AR or MS version exists**.

    So the invariant is the file's absence, which no fingerprint can express —
    a baseline only notices things that are there. If a translated twin ever
    appears, a pipeline translated fiqh content, and that is the failure this
    whole register exists to prevent.
    """
    appeared = []
    for entry in _register().get("exclude", []):
        if entry.get("scope") != "whole_file":
            continue
        for p in _translated_paths(entry):
            if p.is_file():
                appeared.append(str(p.relative_to(_REPO)))

    assert not appeared, (
        f"a machine translation of never-translate Sharia content exists: {appeared}.\n"
        "sensitive_keys.json routes this file to an SME and holds it out of every "
        "translate run. Delete the generated file, find what produced it, and make "
        "that path consult the register \u2014 an ad-hoc script bypassing it is DEF144's "
        "own recurrence."
    )


def test_the_fingerprint_set_is_not_empty():
    """Non-vacuity: a path-derivation bug that resolved every governed artifact
    to a non-existent file would make all three tests above pass over nothing."""
    current = _fingerprints()
    assert len(current) >= 20, (
        f"only {len(current)} governed artifacts resolved on disk — the scope→path "
        "derivation is probably wrong, which would make this whole file vacuous"
    )
