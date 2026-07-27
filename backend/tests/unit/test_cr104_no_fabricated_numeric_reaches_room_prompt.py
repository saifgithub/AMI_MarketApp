"""Structural guard (CR104, closes DEF123): no rng-derived numeric can reach
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

This guard tests the INVARIANT that fix depends on, not today's six field
names: it walks `_profile_for_ticker`'s AST and fails the build if a
"protected" numeric field (the ones DEF123's corpus measurement found
fabricated, plus their technicals siblings) is EITHER

  1. a key in the function's unconditional baseline dict literal (the shape
     the original bug took — a value present before any live fetch runs), or
  2. assigned anywhere in the function from an expression that references
     `rng` (the per-ticker `random.Random` instance) — catches a
     conditionally-reintroduced rng fallback too, not just the top-level
     dict-literal shape.

A test enumerating today's fields would pass forever the day someone adds a
seventh; this walks structure, per DEF116's AST-guard precedent
(test_no_blocking_io_in_async_routes.py) — same idea, applied to data
provenance instead of blocking I/O.
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ROOM_RUNNER = _REPO_ROOT / "backend" / "app" / "services" / "room_runner.py"

# Every numeric field DEF123's corpus measurement found (or could find,
# structurally) carrying a fabricated value under a LIVE-declared header:
# the fundamentals group (base_price/pe/rev_growth/profit_margin/net_cash),
# the 52-week range, and the technicals group compute_technicals replaced.
# Narrative/illustrative fields (sentiment_score, mention_trend, catalyst,
# ...) are deliberately NOT here — CR104's own scope note excludes the
# CR034 illustrative-scaffolding convention.
_PROTECTED_NUMERIC_FIELDS = {
    "base_price", "pe", "rev_growth", "profit_margin", "net_cash",
    "low", "high",
    "rsi", "rsi_tone", "trend", "support", "breakout", "volume_tone",
}


def _find_function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in {_ROOM_RUNNER}")


def _string_key(node: ast.expr) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _profile_baseline_dict(fn: ast.FunctionDef) -> ast.Dict:
    """The unconditional baseline dict literal assigned to the `profile`
    variable — the exact shape the original DEF123 bug took (a protected
    field present as a literal key, pre-filled before any live fetch runs).

    Matched by ASSIGNMENT TARGET name ("profile = {...}" /
    "profile: T = {...}"), not "the first dict literal in the function" —
    an earlier revision of this guard used positional order and was fooled
    by `field_state: dict[str, str] = {}`, an unrelated empty dict literal
    that happens to appear earlier in source. RED-proved: reintroducing
    `"pe": f"{rng.uniform(12,55):.1f}"` into the real baseline dict passed
    the positional-order version of this guard silently.
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


def _references_rng(expr: ast.expr) -> bool:
    for node in ast.walk(expr):
        if isinstance(node, ast.Name) and node.id == "rng":
            return True
    return False


def _rng_tainted_protected_assignments(fn: ast.FunctionDef) -> list[str]:
    """Every `profile["<protected field>"] = <expr referencing rng>` anywhere
    in the function — catches a reintroduced rng fallback even if it's
    conditional, not just the always-executed dict-literal shape."""
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
            if key in _PROTECTED_NUMERIC_FIELDS and _references_rng(node.value):
                hits.append(f"profile[{key!r}] = <rng-derived expr> (line {node.lineno})")
    return hits


def test_no_protected_numeric_field_in_the_unconditional_baseline_dict():
    tree = ast.parse(_ROOM_RUNNER.read_text())
    fn = _find_function(tree, "_profile_for_ticker")
    baseline = _profile_baseline_dict(fn)
    baseline_keys = {_string_key(k) for k in baseline.keys if k is not None}
    offenders = baseline_keys & _PROTECTED_NUMERIC_FIELDS
    assert not offenders, (
        "DEF123 regression: a numeric fact that must be LIVE-or-absent is "
        "present as a key in _profile_for_ticker's unconditional baseline "
        "dict (built before any live fetch runs) — this is the exact shape "
        "the original bug took. Move it behind a live-fetch overlay guarded "
        "by field_state, or into the test-only fixture "
        "(tests/unit/fixtures/synthetic_room_baseline.py) if it's for tests "
        f"only:\n{sorted(offenders)}"
    )


def test_no_rng_derived_value_assigned_to_a_protected_numeric_field():
    tree = ast.parse(_ROOM_RUNNER.read_text())
    fn = _find_function(tree, "_profile_for_ticker")
    offenders = _rng_tainted_protected_assignments(fn)
    assert not offenders, (
        "DEF123 regression: a numeric fact that must be LIVE-or-absent is "
        "assigned from an expression that references `rng` (the per-ticker "
        "random.Random instance) somewhere in _profile_for_ticker — even "
        "conditionally, this reintroduces the fabricated-numeric-under-a-"
        "LIVE-header hazard CR104 removed:\n" + "\n".join(offenders)
    )
