"""CR219 R59 phase-2, lane A3 — the three checks that make
`app.services.numeric_provenance.NUMERIC_PROVENANCE` an enforcing guard rather
than a document that can quietly rot.

See `app/services/numeric_provenance.py`'s module docstring for the registry
shape, the audit this classifies against
(`docs/forward_planning/CR219_room_prompt_contradictions/dev_instructions/
R59_numbers_audit.md`), and — most importantly — what this guard deliberately
does NOT do (it does not check prose, does not veto, and does not enforce
correctness, only declaration). Read that before trusting a green run here as
more than it is.

Three checks, one per test:

  1. `test_every_numeric_verdict_and_costed_structure_field_is_registered` —
     the red-fail. Walks `Verdict.model_fields` and `CostedStructure.
     model_fields`, selects every numeric-or-container-of-numeric field, and
     asserts a registry row exists. A new numeric field on either class fails
     this test until someone classifies it.
  2. `test_no_silent_downgrade_pin` — pins today's COMPUTED/CODE_CHECKED rows
     by exact class. A row moving from either of those to LLM_UNVERIFIED must
     edit this pin in the same commit — the point is that the diff is where a
     reviewer sees a guarantee being given up, not that the move is forbidden.
  3. `test_every_code_checked_row_names_an_importable_callable` — every
     CODE_CHECKED row's `site` string names a module and a callable; this
     imports the module and asserts the callable exists on it. Catches a
     declared-but-nonexistent checker (DEF288's shape: an annotation claiming
     a rewrite happened when the rewriter had matched nothing).
"""

from __future__ import annotations

import importlib
import re
import types
import typing

import pytest

from app.schemas.options import CostedStructure
from app.schemas.room import Verdict
from app.services.numeric_provenance import NUMERIC_PROVENANCE, Provenance

_NUMERIC_LEAVES = (int, float)


def _strip_optional(annotation: object) -> object:
    """Unwrap `X | None` / `Optional[X]` to `X`. Anything else passes through."""
    origin = typing.get_origin(annotation)
    if origin in (typing.Union, types.UnionType):
        args = [a for a in typing.get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            return args[0]
    return annotation


def _is_numeric_leaf(annotation: object) -> bool:
    """`int` or `float`, but NOT `bool` — a flag is not a quantity a numeric-
    provenance registry has anything to say about, even though `bool` is a
    Python subclass of `int`."""
    return isinstance(annotation, type) and issubclass(annotation, _NUMERIC_LEAVES) and annotation is not bool


def _has_numeric_leaf(annotation: object, *, _depth: int = 0) -> bool:
    """True if `annotation` is itself numeric, or a container (list/dict/tuple)
    whose value/element type is numeric, or a nested Pydantic model with at
    least one such field — recursing exactly ONE level into a nested model,
    matching how the audit itself treats `structure.*` and `metrics`/
    `net_greeks`/`legs` as single rows rather than exploding every leaf.

    `_depth` caps that recursion at one nested-model hop so this stays a
    faithful mirror of the registry's own granularity rather than silently
    deepening into `GreeksOut.delta`-style leaves the registry does not
    (and, per the audit, should not) carry individual rows for.
    """
    annotation = _strip_optional(annotation)

    if _is_numeric_leaf(annotation):
        return True

    origin = typing.get_origin(annotation)
    if origin in (list, tuple, set, frozenset):
        return any(_has_numeric_leaf(a, _depth=_depth) for a in typing.get_args(annotation))
    if origin is dict:
        args = typing.get_args(annotation)
        value_type = args[1] if len(args) == 2 else object
        return _has_numeric_leaf(value_type, _depth=_depth)

    # A nested BaseModel: only recurse one hop deep, and only via model_fields
    # (never touch model instances) so this never needs a live payload.
    model_fields = getattr(annotation, "model_fields", None)
    if model_fields is not None and _depth == 0:
        return any(
            _has_numeric_leaf(f.annotation, _depth=_depth + 1)
            for f in model_fields.values()
        )
    return False


def _numeric_fields(model: type) -> set[str]:
    return {
        name for name, field in model.model_fields.items()
        if _has_numeric_leaf(field.annotation)
    }


# ── Check 1: exhaustiveness over the schema (the red-fail) ────────────────────


def test_every_numeric_verdict_and_costed_structure_field_is_registered():
    """A numeric field on `Verdict` or `CostedStructure` with no registry row
    is exactly the DEF038/DEF063 shape one domain over: a field nobody
    declared a provenance decision about. This must be exact — it is the
    entire point of the guard."""
    missing_verdict = {
        f for f in _numeric_fields(Verdict) if ("verdict", f) not in NUMERIC_PROVENANCE
    }
    missing_structure = {
        f for f in _numeric_fields(CostedStructure)
        if ("costed_structure", f) not in NUMERIC_PROVENANCE
    }
    assert not missing_verdict, (
        f"Verdict has numeric field(s) with no NUMERIC_PROVENANCE row: "
        f"{sorted(missing_verdict)}. Classify each as COMPUTED, CODE_CHECKED "
        "or LLM_UNVERIFIED in app/services/numeric_provenance.py before this "
        "field ships further — an undeclared numeric is a provenance decision "
        "nobody made."
    )
    assert not missing_structure, (
        f"CostedStructure has numeric field(s) with no NUMERIC_PROVENANCE row: "
        f"{sorted(missing_structure)}. Same fix, under the 'costed_structure' "
        "surface."
    )


def test_registry_names_no_field_that_no_longer_exists():
    """The inverse direction: a stale row (a field renamed or removed from the
    schema) is not a defect the way a missing row is, but it is a lie sitting
    in a file whose whole purpose is to be a faithful citation — worth
    catching so the registry does not accumulate rows about fields nobody can
    find anymore."""
    verdict_fields = set(Verdict.model_fields)
    structure_fields = set(CostedStructure.model_fields)
    stale = [
        (surface, field) for surface, field in NUMERIC_PROVENANCE
        if surface == "verdict" and field not in verdict_fields
        or surface == "costed_structure" and field not in structure_fields
    ]
    assert not stale, (
        f"NUMERIC_PROVENANCE rows name fields that no longer exist on their "
        f"schema: {sorted(stale)}. Remove the row or fix the field name."
    )


# ── Check 2: no silent downgrade ───────────────────────────────────────────────
#
# Pins every row that is NOT LLM_UNVERIFIED today, by its exact class. A row
# moving from this pin's COMPUTED/CODE_CHECKED into LLM_UNVERIFIED is a
# guarantee being given up, and this test forces that move to touch this file
# in the same commit — the diff IS the review artifact, the same idea as
# test_inline_compose_defaults_match_settings ("a declared thing must stay
# declared"). An UPGRADE (LLM_UNVERIFIED -> either of these, or CODE_CHECKED ->
# COMPUTED) is never blocked here: only the harmful direction — a guarantee
# quietly disappearing — needs a human to touch this pin to let it through.

_PINNED_NOT_LLM_UNVERIFIED: dict[tuple[str, str], Provenance] = {
    ("verdict", "size_pct"): Provenance.CODE_CHECKED,
    ("verdict", "entry"): Provenance.CODE_CHECKED,
    ("verdict", "stop"): Provenance.COMPUTED,
    ("verdict", "target"): Provenance.COMPUTED,
    ("verdict", "approve_votes"): Provenance.COMPUTED,
    ("verdict", "samples"): Provenance.COMPUTED,
    ("verdict", "scripted_turns"): Provenance.COMPUTED,
    ("verdict", "structure"): Provenance.COMPUTED,
    ("costed_structure", "contracts"): Provenance.COMPUTED,
    ("costed_structure", "days_to_expiry"): Provenance.COMPUTED,
    ("costed_structure", "legs"): Provenance.COMPUTED,
    ("costed_structure", "metrics"): Provenance.COMPUTED,
    ("costed_structure", "net_greeks"): Provenance.COMPUTED,
    ("costed_structure", "payoff_curve"): Provenance.COMPUTED,
    ("costed_structure", "spot"): Provenance.COMPUTED,
    ("risk_rung", "size_pct"): Provenance.COMPUTED,
    ("risk_rung", "contribution_pts"): Provenance.COMPUTED,
    ("risk_rung", "headroom_after_pts"): Provenance.COMPUTED,
    ("risk_rung", "share_of_cap_pct"): Provenance.COMPUTED,
    ("risk_rung", "reward_risk"): Provenance.COMPUTED,
    ("risk_rung", "recommended"): Provenance.CODE_CHECKED,
    ("risk_rung", "confidence"): Provenance.CODE_CHECKED,
    ("stance_envelope", "argued_size_pct"): Provenance.CODE_CHECKED,
}


def test_no_silent_downgrade_pin():
    for key, expected in _PINNED_NOT_LLM_UNVERIFIED.items():
        assert key in NUMERIC_PROVENANCE, (
            f"{key} was pinned as {expected.name} and has disappeared from "
            "NUMERIC_PROVENANCE entirely — a removed row loses the guarantee "
            "just as surely as a downgraded one."
        )
        actual = NUMERIC_PROVENANCE[key].provenance
        assert actual is expected, (
            f"{key} moved from the pinned {expected.name} to {actual.name}. "
            "If this is a deliberate, reviewed downgrade (a checker was "
            "removed, or a computed value became model-stated), update this "
            "pin in the SAME commit — that is the point of this test: the "
            "diff is where the guarantee being given up gets seen. If it is "
            "not deliberate, this is the regression the test exists to catch."
        )
    assert Provenance.LLM_UNVERIFIED not in _PINNED_NOT_LLM_UNVERIFIED.values(), (
        "_PINNED_NOT_LLM_UNVERIFIED exists to pin rows AWAY from "
        "LLM_UNVERIFIED — an LLM_UNVERIFIED entry here defeats its own point"
    )


def test_llm_unverified_rows_match_the_audit_today():
    """The complement of the pin above: today's known-unverified rows, by
    name, so a row silently disappearing from the registry (rather than being
    reclassified) is caught too. F4's time_horizon_days and F2's key_number /
    decisive_number are recorded here because that is what the code does as
    of this module — see numeric_provenance.py's docstring for why F2's two
    rows are expected to flip to CODE_CHECKED once lane A2 lands, and why that
    flip needs no permission from this test (only the harmful direction does)."""
    expected_unverified = {
        ("verdict", "time_horizon_days"),
        ("risk_rung", "key_number"),
        ("risk_rung", "decisive_number"),
    }
    actual_unverified = {
        key for key, row in NUMERIC_PROVENANCE.items()
        if row.provenance is Provenance.LLM_UNVERIFIED
    }
    assert actual_unverified == expected_unverified, (
        f"LLM_UNVERIFIED rows changed: expected {sorted(expected_unverified)}, "
        f"got {sorted(actual_unverified)}. A row REMOVED from this set without "
        "appearing in _PINNED_NOT_LLM_UNVERIFIED above means it vanished from "
        "the registry rather than being reclassified — check "
        "NUMERIC_PROVENANCE directly."
    )


# ── Check 3: declared-checker-exists ───────────────────────────────────────────

# `site` strings are prose citations, not import paths — this pulls the
# leading `module.callable` token out of one. Matches the shape every
# CODE_CHECKED row in numeric_provenance.py actually uses: a dotted path
# starting with `app.`, ending at the first character that is not a valid
# Python identifier or dot (a space, an em-dash, a comma, an opening paren).
_SITE_CALLABLE_RE = re.compile(r"^(app(?:\.[A-Za-z_][A-Za-z0-9_]*)+)")


def _split_module_and_callable(site: str) -> tuple[str, str]:
    m = _SITE_CALLABLE_RE.match(site)
    assert m, (
        f"CODE_CHECKED row's site does not start with a dotted app.* path: "
        f"{site!r} — check 3 cannot verify a citation it cannot parse"
    )
    dotted = m.group(1)
    module_path, _, callable_name = dotted.rpartition(".")
    assert module_path and callable_name, (
        f"could not split {dotted!r} into a module and a callable name"
    )
    return module_path, callable_name


@pytest.mark.parametrize(
    "key", [k for k, row in NUMERIC_PROVENANCE.items() if row.provenance is Provenance.CODE_CHECKED],
    ids=lambda k: f"{k[0]}.{k[1]}",
)
def test_every_code_checked_row_names_an_importable_callable(key):
    site = NUMERIC_PROVENANCE[key].site
    module_path, callable_name = _split_module_and_callable(site)
    module = importlib.import_module(module_path)
    target = getattr(module, callable_name, None)
    assert target is not None and callable(target), (
        f"{key} is CODE_CHECKED and names {module_path}.{callable_name} as "
        "its checker, but that callable does not exist (or is not callable) — "
        "this is DEF288's shape: an annotation claiming a check happens where "
        "none does. Fix the citation or fix the code."
    )


def test_at_least_one_code_checked_row_exists():
    """A guard whose parametrized test collects zero cases passes trivially
    and silently — this fails loudly if that ever happens, so an empty
    CODE_CHECKED set is visible rather than a green run with nothing behind
    it."""
    checked = [k for k, row in NUMERIC_PROVENANCE.items() if row.provenance is Provenance.CODE_CHECKED]
    assert checked, "no CODE_CHECKED rows in NUMERIC_PROVENANCE — check 3 verified nothing"
