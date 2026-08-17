"""DEF295 — an English string sitting in an Arabic file is recorded as one.

Two shipped rules used to collide, and the collision was invisible to both:

* DEF137's parity guard fails the build if `app_ar.arb` / `app_ms.arb` are
  missing any template key, so a new string has to be written into all three
  files at once — in practice, seeded with the English.
* `translate_arb.py` skips any key whose target value is a non-empty string, by
  design, so a translator's hand edits are never overwritten.

English seeded to satisfy the first is indistinguishable from a hand
translation under the second, so it is skipped **forever**: the key is present,
the parity guard is green, and the Arabic screen renders English. That is the
silent per-key fallback DEF137 was filed to stop, arriving through its own fix
rather than around it. Measured 2026-08-17, after the marker landed: 615 keys
in `app_ar.arb` and 630 in `app_ms.arb` were in that state — up from the
320/321 prose keys counted when DEF295 was filed four days earlier, because
every CR that adds a string adds to the pile.

`failure_patterns.md`'s house rule for a second occurrence is a guard, not a
sweep, and the guard has to make *"translated"* a fact the file records rather
than one inferred from *"the value is non-empty"*. It does that with one
`@@x-ami-seeds` map per target ARB, holding `key → sha256[:12]` of the value
that was seeded in.

The tests below pin both halves:

* the **mechanism** — a marked key is pending, an unmarked one is not, and the
  marker is self-healing: a key stops being a seed the moment its value changes,
  so a human who translates by hand never has to know this exists;
* the **corpus** — no target value is byte-identical to its English without
  being marked. That count is zero, not a ratchet: `--seed-missing` is the one
  supported way to satisfy DEF137's parity guard, and hand-copying English into
  a target file is what this test is here to catch.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "scripts"))

import translate_arb as T  # noqa: E402

_ARB = _REPO / "mobile" / "lib" / "l10n"

# `appTitle` is the product name. `_is_translatable_key` excludes it from the
# source set entirely, so it is identical in every locale on purpose and is
# never a seed.
_NEVER_TRANSLATED = {"appTitle"}


def _load(locale: str) -> dict:
    return json.loads((_ARB / f"app_{locale}.arb").read_text(encoding="utf-8"))


def _en_strings() -> dict[str, str]:
    en = _load("en")
    return {k: str(v) for k, v in en.items() if T._is_translatable_key(k)}


def _targets() -> list[str]:
    return sorted(
        p.name.split("_")[1].split(".")[0]
        for p in _ARB.glob("app_*.arb")
        if p.name not in {"app_en.arb"}
    )


# --------------------------------------------------------------------------
# The mechanism
# --------------------------------------------------------------------------


def test_a_marked_seed_is_pending_and_an_unmarked_value_is_not():
    en = {"greeting": "Hello", "farewell": "Goodbye"}
    target = {"greeting": "Hello", "farewell": "Selamat tinggal"}
    T.mark_seed(target, "greeting", "Hello")

    assert T.pending_keys(target, en) == ["greeting"], (
        "the seeded key must be translated on the next run, and the hand "
        "translation must be left alone — that is the whole of DEF295"
    )


def test_translating_clears_the_marker_so_the_two_cannot_drift():
    en = {"greeting": "Hello"}
    target = {"greeting": "Hello"}
    T.mark_seed(target, "greeting", "Hello")

    target["greeting"] = "Salam"
    T.clear_seed(target, "greeting")

    assert T.pending_keys(target, en) == []
    assert T.SEEDS_KEY not in target, (
        "the last marker gone takes the map with it — an empty map left "
        "behind is a fact about nothing"
    )


def test_a_hand_edit_stops_being_a_seed_without_clearing_anything():
    """The self-healing half.

    A bare `translated: false` flag would need whoever edits the value to
    remember to flip it, and forgetting re-translates over their work — the
    exact thing the skip rule exists to prevent. Hashing the seeded value means
    the edit itself is the signal.
    """
    en = {"greeting": "Hello"}
    target = {"greeting": "Hello"}
    T.mark_seed(target, "greeting", "Hello")
    assert T.is_seed(target, "greeting")

    target["greeting"] = "Salam"  # a human translated it, marker untouched

    assert not T.is_seed(target, "greeting")
    assert T.pending_keys(target, en) == []


def test_seed_missing_marks_everything_it_seeds():
    en = {"a": "Alpha", "b": "Bravo"}
    target = {"a": "Alfa"}

    seeded = T.seed_missing(target, en)

    assert seeded == ["b"]
    assert target["b"] == "Bravo"
    assert T.pending_keys(target, en) == ["b"], (
        "seeding to satisfy DEF137's parity guard must leave the key visible "
        "to the translator, which is the collision DEF295 names"
    )


def test_overwrite_still_takes_everything():
    en = {"a": "Alpha"}
    target = {"a": "Alfa"}
    assert T.pending_keys(target, en, overwrite=True) == ["a"]


# --------------------------------------------------------------------------
# The corpus
# --------------------------------------------------------------------------


@pytest.mark.parametrize("locale", _targets())
def test_no_english_sits_unmarked_in_a_target_arb(locale: str):
    en = _en_strings()
    target = _load(locale)

    unmarked = sorted(
        key
        for key, en_val in en.items()
        if key not in _NEVER_TRANSLATED
        and target.get(key) == en_val
        and not T.is_seed(target, key)
    )
    assert not unmarked, (
        f"app_{locale}.arb holds {len(unmarked)} English string(s) that claim "
        f"to be translations: {unmarked[:10]}. Seed with "
        "`python3 scripts/translate_arb.py --seed-missing` instead of copying "
        "English by hand — a hand copy is skipped by the translator forever "
        "and the parity guard cannot see it (DEF295)."
    )


@pytest.mark.parametrize("locale", _targets())
def test_no_marker_outlives_its_key(locale: str):
    en = _en_strings()
    target = _load(locale)
    seeds = target.get(T.SEEDS_KEY, {})

    orphans = sorted(set(seeds) - set(en))
    assert not orphans, (
        f"app_{locale}.arb marks keys the template no longer defines: "
        f"{orphans[:10]}. A stale entry hides the next real one."
    )
