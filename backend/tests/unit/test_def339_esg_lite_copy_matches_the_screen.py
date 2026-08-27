"""DEF339 — the ESG-lite explanation must describe the screen that actually runs.

The shipped copy told the user AMI screens *"thermal coal, oil sands,
controversial weapons, and severe governance flags."* Measured against
`classification_universe.py`, the enforced set is `fossil ∪ sin ∪ defense`:

* **fossil** — eight yfinance oil-and-gas/coal industry strings, additionally
  gated on `sector == Energy`. Far broader than "oil sands".
* **sin** — tobacco, brewers, wineries & distilleries, gambling, resorts &
  casinos. **Absent from the copy entirely.**
* **defense** — the whole `aerospace & defense` industry, which sweeps
  commercial aerospace and is not the narrower "controversial weapons".
* **governance** — *does not exist*. Nothing anywhere implements it.

So the sheet claimed a check that is not there and omitted one that is, on a
values-sensitive control. A user who reads it and ticks the box believes their
book was screened for governance quality: CR040's shown-does-not-match-enforced
class, in DEF059's confident-false shape. The app also contradicted itself — the
per-verdict `_ESG_LITE_DISCLAIMER` names the real three buckets correctly, and
the wrong half was the one shown *before* the user decides.

**Why the guard is worded as a set relationship rather than a string match.**
Pinning the copy to an exact sentence would fail on every legitimate rewording
and would be suppressed within a month. What must hold is narrower and durable:
the copy names each enforced bucket, and it never claims a bucket that is not
enforced. `governance` is the specific never-claim, because that is the word
that made the sheet false.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.services.classification_universe import (
    _DEFENSE_INDUSTRIES,
    _FOSSIL_INDUSTRIES,
    _SIN_INDUSTRIES,
)

_ARB = Path(__file__).resolve().parents[3] / "mobile" / "lib" / "l10n" / "app_en.arb"
_BODY_KEY = "settingsComplianceEsgLiteExplainBody"
_SETTINGS = (
    Path(__file__).resolve().parents[3]
    / "mobile" / "lib" / "screens" / "settings" / "settings_screen.dart"
)


@pytest.fixture(scope="module")
def body() -> str:
    arb = json.loads(_ARB.read_text(encoding="utf-8"))
    assert _BODY_KEY in arb, (
        f"{_BODY_KEY} is missing from app_en.arb — DEF339 moved this copy out of "
        "the hardcoded Dart map precisely so it could be translated and guarded."
    )
    return arb[_BODY_KEY].casefold()


def test_the_enforced_buckets_are_non_empty():
    """Vacuity: every assertion below is 'the copy mentions X', and all of them
    pass trivially if the industry sets import as empty."""
    assert len(_FOSSIL_INDUSTRIES) >= 5
    assert len(_SIN_INDUSTRIES) >= 4
    assert len(_DEFENSE_INDUSTRIES) >= 1


@pytest.mark.parametrize(
    "bucket,must_mention",
    [
        ("fossil", ("oil", "gas", "coal")),
        ("sin", ("tobacco", "alcohol", "gambling")),
        ("defense", ("defence", "defense")),
    ],
)
def test_the_copy_names_every_bucket_the_screen_enforces(body, bucket, must_mention):
    """`sin` is the one this defect was really about — it is enforced and the
    shipped copy did not mention it at all."""
    assert any(w in body for w in must_mention), (
        f"the ESG-lite explanation never mentions the {bucket!r} bucket, which "
        f"the screen DOES enforce. Expected one of {must_mention}."
    )


def test_the_copy_does_not_claim_a_governance_screen(body):
    """The specific false claim. Nothing in the codebase implements it."""
    assert "governance" not in body or re.search(
        r"(not|never|no[t]?)\s+(\w+\s+){0,3}governance", body
    ), (
        "the ESG-lite explanation claims a governance screen. There is no "
        "governance check anywhere in the codebase — this is the exact sentence "
        "DEF339 was filed for. If governance appears, it may only appear as a "
        "denial."
    )


def test_no_governance_check_exists_to_justify_such_a_claim():
    """The other half of the pair. If a governance bucket is ever built, this
    test fails and whoever built it is sent to update the copy deliberately —
    rather than the copy quietly becoming true by accident years later."""
    src = (
        Path(__file__).resolve().parents[2]
        / "app" / "services" / "classification_universe.py"
    ).read_text(encoding="utf-8")
    assert "GOVERNANCE" not in src.upper().replace("GOVERNANCE FLAGS", ""), (
        "a governance classification now exists — update the ESG-lite copy and "
        "this guard together."
    )


def test_the_copy_states_its_coverage_and_the_unknown_rule(body):
    """The two facts a user most needs and the old copy omitted: coverage is the
    ~503-name S&P parent set, and a ticker outside it resolves UNKNOWN, which
    PERMITS the trade. Without those the sheet implies universal screening."""
    assert "s&p" in body, "the copy does not name its coverage universe"
    assert any(w in body for w in ("permitted", "unscreened", "not screened")), (
        "the copy does not say that a ticker outside the covered universe is "
        "permitted — a user reading it believes everything is screened"
    )


def test_the_dart_map_no_longer_carries_a_hardcoded_esg_body():
    """DEF339's secondary finding: this body was hardcoded English in the Dart
    const map while the observance-sensitive `halal` entry had already been
    moved to the ARB, so ESG-lite copy was untranslatable and drifted unguarded.
    A reintroduced hardcoded entry would be invisible to every test above."""
    src = _SETTINGS.read_text(encoding="utf-8")
    block = re.search(
        r"const Map<String, _ComplianceExplanation> _complianceExplanations = \{(.*?)\n\};",
        src,
        re.S,
    )
    assert block, "the explanation map moved — update this guard"
    assert "'esgLite'" not in block.group(1), (
        "the esgLite entry is back in the hardcoded Dart map, which makes its "
        "copy untranslatable and invisible to the ARB-based guards above"
    )
