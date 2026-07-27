"""Structural guard (CR104, closes DEF123): no rng-derived value can reach
`_format_profile` (the LLM-facing Room prompt renderer) under production
config.

Thirteen prior mechanism-B fabrication instances (DEF052, DEF063, CR037,
CR038, DEF123 — see `failure_patterns.md` P2) were all fixed by relabelling
the fake data, not by removing it. DEF123 proved labelling doesn't hold:
`data_source="yfinance_live"` asserted the whole fundamentals block was real
while an rng-seeded P/E sat under it, 21.1% of the time. CR104 deleted the
rng baseline from `_profile_for_ticker` (backend/app/services/room_runner.py)
and made `_format_profile` (room_prompts.py) refuse to render a field with no
recorded `field_state` provenance.

Round-1 version of this guard used `_PROTECTED_NUMERIC_FIELDS`, an allowlist
of 13 field names. Round-2 audit (CR104-ROOM auditor, round 1) reproduced two
defeats of that shape:

  A. a field name outside the allowlist is simply invisible —
     `profile["peg_ratio"] = f"{rng.uniform(...):.2f}"` passed green.
  B. WORSE — an allowlisted field defeated via one intermediate local:
     `_v = rng.uniform(12.0, 55.0); profile["pe"] = f"{_v:.1f}"` passed
     green. That is DEF123's literal original shape, laundered through a
     local variable, on the production path.

This version inverts the polarity: **taint-following, deny-by-default.** Any
`profile[...]` write — in the unconditional baseline dict literal, or in a
later `profile[key] = expr` assignment anywhere in the function — is flagged
if its value expression is rng-tainted, meaning it references `rng` directly
OR references any local variable that is itself rng-tainted, followed
through an arbitrary chain of intermediate local assignments (not just one
hop). A field must argue its way onto the exclusion list below to opt out;
nothing is silently safe by virtue of an unrecognised name.

A test enumerating today's field names would pass forever the day someone
adds a new one; this walks structure and follows data flow, per DEF116's
AST-guard precedent (test_no_blocking_io_in_async_routes.py) — same idea,
applied to data provenance instead of blocking I/O.
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ROOM_RUNNER = _REPO_ROOT / "backend" / "app" / "services" / "room_runner.py"

# Explicit, justified deny-by-default EXCLUSION list — not an allowlist of
# what's protected, but the only names permitted to opt OUT of protection.
# All three are the CR034 illustrative-scaffolding convention: narrative
# framing text, never presented to the model (or the user) as a measured
# fact. `_format_profile` never labels them "(LIVE)" or attaches
# `field_state` provenance to them — they read as intentionally synthetic
# in the prompt. Every other field, known today or added tomorrow, is
# protected by default.
_EXCLUDED_NARRATIVE_FIELDS = {
    "sentiment_tone", "sentiment_score", "mention_trend",
}


def _find_function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in {_ROOM_RUNNER}")


def _string_key(node: ast.expr | None) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _profile_baseline_dict(fn: ast.FunctionDef) -> ast.Dict:
    """The unconditional baseline dict literal assigned to the `profile`
    variable — the exact shape the original DEF123 bug took (a protected
    field present as a literal key, pre-filled before any live fetch runs).

    Matched by ASSIGNMENT TARGET name ("profile = {...}" /
    "profile: T = {...}"), not "the first dict literal in the function" —
    an earlier revision of this guard used positional order and was fooled
    by `field_state: dict[str, str] = {}`, an unrelated empty dict literal
    that happens to appear earlier in source.
    """
    for node in ast.walk(fn):
        target = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
        elif isinstance(node, ast.AnnAssign):
            target = node.target
        else:
            continue
        if (
            isinstance(target, ast.Name) and target.id == "profile"
            and isinstance(node.value, ast.Dict)
        ):
            return node.value
    raise AssertionError(
        "_profile_for_ticker has no `profile = {...}` dict-literal assignment "
        "— has its shape changed? Update this guard to match."
    )


#: `profile` (and `field_state`) are tracked precisely, per-key, by the
#: subscript/baseline-entry scanners below — NOT as a single tainted/untainted
#: local. Both are containers that legitimately mix tainted narrative
#: entries (sentiment_tone, ...) with untainted or live-only ones (pe,
#: is_growth, ...); treating either name itself as "tainted" the moment any
#: one of its entries references `rng` would flood every later
#: `profile["pe"]`-derived read (e.g. `pe_val = float(profile["pe"])`) as a
#: false positive, drowning the real hits.
_TAINT_TRACKING_EXCLUDED_LOCALS = {"profile", "field_state"}


def _local_name_assignments(fn: ast.FunctionDef) -> list[tuple[str, ast.expr]]:
    """Every `<name> = <expr>` / `<name>: T = <expr>` assignment to a plain
    local variable anywhere in the function, in the order ast.walk yields
    them. Order doesn't need to match execution order — taint propagation
    below is a fixed-point over this list, so chains resolve regardless of
    which order the assignments are discovered in."""
    assignments: list[tuple[str, ast.expr]] = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if (
                isinstance(target, ast.Name)
                and target.id not in _TAINT_TRACKING_EXCLUDED_LOCALS
                and node.value is not None
            ):
                assignments.append((target.id, node.value))
        elif isinstance(node, ast.AnnAssign):
            if (
                isinstance(node.target, ast.Name)
                and node.target.id not in _TAINT_TRACKING_EXCLUDED_LOCALS
                and node.value is not None
            ):
                assignments.append((node.target.id, node.value))
    return assignments


def _expr_is_tainted(expr: ast.expr, tainted_names: set[str]) -> bool:
    for node in ast.walk(expr):
        if isinstance(node, ast.Name) and (node.id == "rng" or node.id in tainted_names):
            return True
    return False


def _rng_tainted_locals(fn: ast.FunctionDef) -> set[str]:
    """Fixed-point closure of every local variable name that is rng-tainted
    — assigned directly from `rng`, or assigned from an expression that
    references another already-tainted local. Iterates to a fixed point so
    an arbitrary chain (`_v = rng.uniform(...)`; `_w = _v`; `_x = _w`) is
    fully followed, not just one hop."""
    assignments = _local_name_assignments(fn)
    tainted: set[str] = set()
    changed = True
    while changed:
        changed = False
        for name, value in assignments:
            if name in tainted:
                continue
            if _expr_is_tainted(value, tainted):
                tainted.add(name)
                changed = True
    return tainted


def _rng_tainted_baseline_entries(fn: ast.FunctionDef, tainted_locals: set[str]) -> list[str]:
    baseline = _profile_baseline_dict(fn)
    hits: list[str] = []
    for key_node, value_node in zip(baseline.keys, baseline.values):
        key = _string_key(key_node)
        if key is None or key in _EXCLUDED_NARRATIVE_FIELDS:
            continue
        if _expr_is_tainted(value_node, tainted_locals):
            hits.append(f"profile[{key!r}] = <rng-tainted expr> (baseline dict literal)")
    return hits


def _rng_tainted_profile_assignments(fn: ast.FunctionDef, tainted_locals: set[str]) -> list[str]:
    """Every `profile["<field>"] = <rng-tainted expr>` anywhere in the
    function, outside the baseline dict literal — deny-by-default: any field
    name not on the explicit exclusion list is protected, and taint is
    followed through chained local assignments, not just a direct `rng`
    reference."""
    hits: list[str] = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not (
                isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Name)
                and target.value.id == "profile"
            ):
                continue
            key = _string_key(target.slice)
            if key is not None and key in _EXCLUDED_NARRATIVE_FIELDS:
                continue
            if _expr_is_tainted(node.value, tainted_locals):
                hits.append(f"profile[{key!r}] = <rng-tainted expr> (line {node.lineno})")
    return hits


def test_no_rng_tainted_value_in_the_unconditional_baseline_dict():
    tree = ast.parse(_ROOM_RUNNER.read_text())
    fn = _find_function(tree, "_profile_for_ticker")
    tainted_locals = _rng_tainted_locals(fn)
    offenders = _rng_tainted_baseline_entries(fn, tainted_locals)
    assert not offenders, (
        "DEF123 regression: a non-excluded profile field is present as a key "
        "in _profile_for_ticker's unconditional baseline dict (built before "
        "any live fetch runs) with an rng-tainted value — this is the exact "
        "shape the original bug took. Move it behind a live-fetch overlay "
        "guarded by field_state, add it to the test-only fixture "
        "(tests/unit/fixtures/synthetic_room_baseline.py) if it's for tests "
        "only, or — if it is genuinely illustrative narrative, not a fact — "
        f"justify it onto _EXCLUDED_NARRATIVE_FIELDS in this file:\n{offenders}"
    )


def test_no_rng_tainted_value_assigned_to_any_profile_field():
    tree = ast.parse(_ROOM_RUNNER.read_text())
    fn = _find_function(tree, "_profile_for_ticker")
    tainted_locals = _rng_tainted_locals(fn)
    offenders = _rng_tainted_profile_assignments(fn, tainted_locals)
    assert not offenders, (
        "DEF123 regression: a non-excluded profile field is assigned an "
        "rng-tainted value somewhere in _profile_for_ticker — directly from "
        "`rng`, or laundered through one or more intermediate local "
        "variables. Even conditionally, this reintroduces the "
        "fabricated-value-under-a-LIVE-header hazard CR104 removed:\n"
        + "\n".join(offenders)
    )
