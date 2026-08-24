"""A Dart model and the response model that feeds it must agree on key names.

**Why this exists.** P18/DEF357 — *a feature proven on the builder, never on
the caller that must feed it* — has happened three times inside CR172 alone:

  1. `OptionProposalTicket` shipped with exactly one referencing file: its own
     test. No service ever called the options API.
  2. DEF363 — the Dart model read `greeks_reason`; the server sends
     `greeks_not_evaluated`. **Both** covering tests supplied the wrong key
     themselves, so both were green.
  3. DEF365 — `SimPortfolio.fromJson` read `options` and a whole portfolio card
     rendered off it, while `PortfolioSnapshot` had no `options` field at all.
     4 backend tests drove the builder directly; 13 Flutter tests built their
     own fixtures. Neither side ever consumed the other's output.

Each was written by someone testing carefully. The suite cannot see across the
wire: Python tests assert on Python objects, Dart tests on Dart maps, and the
contract between them has no home. Naming the third instance would produce a
fourth, so this closes the mechanism.

**Why PAIRS and not a sweep.** The first version of this test compared every
`j['…']` key in `mobile/lib/models/` against every Pydantic field in
`app.api` + `app.schemas`, and reported ~250 orphans. Almost all were false:
this codebase serialises a great deal through **untyped `list[dict]`**
(`PortfolioSnapshot.holdings` is literally `list[dict]`, and its `mark` /
`value` / `unrealised_pnl` / `stop` / `target` keys are dict literals in the
route body). No schema-based check can see inside those, and an allowlist of
250 keys would be a rubber stamp — the very thing that makes a guard decorative.

So the unit here is a **declared pair**: one Dart class, one Pydantic model,
asserted to agree. Every pair is a claim someone verified. Adding a pair is how
this guard grows, and the honest state of the codebase is that it can only
cover the surfaces whose response models are fully typed. Typing the
`list[dict]` response fields is the prerequisite for covering the rest, and is
worth its own CR rather than a fake allowlist here.

For a declared pair this catches BOTH failure shapes: a key the server never
emits (DEF365) and a key the client spells differently (DEF363).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_MOBILE_MODELS = _REPO.parent / "mobile" / "lib" / "models"

# (dart file stem, dart class) → (import path, pydantic model attr)
#
# Add a pair only after checking the route actually serialises that model for
# that client class. An unverified pair is worse than no pair.
_PAIRS = [
    # The pair that would have caught DEF365 outright: SimPortfolio read
    # `options` and PortfolioSnapshot had no such field. Every key this class
    # reads is a typed field on the response model — the `list[dict]` opacity
    # is one level down, in SimHolding, not here.
    (("sim", "SimPortfolio"), ("app.api.sim", "PortfolioSnapshot")),
    (("sim", "SimOptionLeg"), ("app.api.sim", "OptionLegOut")),
]

# Keys a declared Dart class reads that its paired model legitimately does not
# carry, each with the reason. Kept per-pair so one exemption cannot silence
# another surface.
_EXEMPT: dict[tuple[str, str], dict[str, str]] = {}

_FACTORY_RE = re.compile(r"factory\s+(\w+)\.fromJson\b")
_KEY_RE = re.compile(r"""j\[\s*'([a-z0-9_]+)'\s*\]""")


def _keys_by_dart_class(stem: str) -> dict[str, set[str]]:
    """`{class name: keys its fromJson reads}` for one models file.

    Sliced on `factory X.fromJson` boundaries: everything from one factory to
    the next belongs to that class. Coarse, and correct for this codebase's
    one-factory-per-class style.
    """
    path = _MOBILE_MODELS / f"{stem}.dart"
    if not path.is_file():
        pytest.skip(f"mobile model not present: {path}")
    text = path.read_text()
    marks = [(m.start(), m.group(1)) for m in _FACTORY_RE.finditer(text)]
    out: dict[str, set[str]] = {}
    for i, (start, cls) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        out.setdefault(cls, set()).update(_KEY_RE.findall(text[start:end]))
    return out


def _model_fields(module_path: str, attr: str) -> set[str]:
    import importlib

    model = getattr(importlib.import_module(module_path), attr)
    return set(model.model_fields)


@pytest.mark.parametrize(("dart", "api"), _PAIRS, ids=lambda v: f"{v[1]}")
def test_a_declared_pair_agrees_on_every_key(dart, api):
    stem, cls = dart
    module_path, attr = api
    by_class = _keys_by_dart_class(stem)
    assert cls in by_class, (
        f"{cls}.fromJson not found in {stem}.dart — the extractor found "
        f"{sorted(by_class)}. A renamed class silently empties this test."
    )
    read = by_class[cls]
    assert read, f"{cls}.fromJson reads no keys — the extractor is broken"
    emitted = _model_fields(module_path, attr)
    exempt = set(_EXEMPT.get((stem, cls), {}))
    missing = read - emitted - exempt
    assert not missing, (
        f"{cls}.fromJson reads {sorted(missing)}, which {attr} does not emit.\n"
        "This is the DEF365/DEF363 shape: client and server each green against "
        "their own fixtures, disagreeing on the wire.\n"
        "Fix the route, fix the client, or add the key to _EXEMPT with a "
        "reason naming its real source."
    )


def test_the_extractor_is_not_silently_matching_nothing():
    """A guard whose extractor breaks would pass forever.

    Pins keys known to be read by `SimOptionLeg`, so a regex or path change
    turns this red instead of turning the parametrised test into a no-op.
    """
    by_class = _keys_by_dart_class("sim")
    assert "SimOptionLeg" in by_class, sorted(by_class)
    assert {"occ_symbol", "strike", "days_to_expiry"} <= by_class["SimOptionLeg"]
    # And that it separates classes rather than pooling one file's keys.
    assert "SimPortfolio" in by_class
    assert "occ_symbol" not in by_class["SimPortfolio"]


def test_the_def365_key_is_emitted():
    """The specific field whose absence was the defect: an entire card read
    `options` off a response model that had no such field."""
    from app.api.sim import PortfolioSnapshot

    assert "options" in PortfolioSnapshot.model_fields


def test_every_declared_pair_names_a_real_model():
    """A typo in `_PAIRS` would skip a surface silently."""
    for _dart, (module_path, attr) in _PAIRS:
        assert _model_fields(module_path, attr), f"{module_path}.{attr} empty"
