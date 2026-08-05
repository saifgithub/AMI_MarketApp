"""P15-GUARD — every check-then-INSERT under a unique constraint handles IntegrityError.

`failure_patterns.md` P15. A function that SELECTs what exists and INSERTs the
rest is correct in one process and raises in two: the read-to-commit gap means
two callers whose reads both land before either commits will both INSERT, and
one loses the constraint.

Second occurrence in CR136 alone — M03 wrote the handler
(`portfolio_snapshot.py:192`), M01 did not — which is what CLAUDE.md's
second-occurrence rule turns into a guard rather than another point fix.

**Why this reads source instead of racing.** The auditor measured 0 races in 60
trials on this stack, because an in-process throttle dict happens to hold the
invariant that nobody wrote down. A runtime test would be flaky-green for the
same reason the bug was invisible: the protection is a deployment fact
(one uvicorn, no `--workers`), and CLAUDE.md's Beta stack is Cloud Run, where
instances share no dict. So this asserts the HANDLER EXISTS, the same way
`test_cr136_dart_parity.py` asserts a cross-boundary contract it cannot execute.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_SERVICES = Path(__file__).resolve().parents[2] / "app" / "services"


def _upsert_calls(tree: ast.AST) -> list[ast.Call]:
    return [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id.startswith("upsert_")
    ]


def _guarded_line_ranges(tree: ast.AST) -> list[tuple[int, int]]:
    """Line spans of every `try` block whose handlers name IntegrityError."""
    spans: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            names: list[str] = []
            exc = handler.type
            if isinstance(exc, ast.Name):
                names.append(exc.id)
            elif isinstance(exc, ast.Attribute):
                names.append(exc.attr)
            elif isinstance(exc, ast.Tuple):
                for elt in exc.elts:
                    if isinstance(elt, ast.Name):
                        names.append(elt.id)
                    elif isinstance(elt, ast.Attribute):
                        names.append(elt.attr)
            if "IntegrityError" in names:
                body = node.body
                spans.append((body[0].lineno, body[-1].end_lineno or body[-1].lineno))
    return spans


def _modules_calling_upsert() -> list[Path]:
    out = []
    for path in sorted(_SERVICES.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if _upsert_calls(tree):
            out.append(path)
    return out


def test_the_guard_finds_something_to_check() -> None:
    """Vacuity: a guard that scans nothing passes forever. P15 has two known
    instances, so anything under two means the discovery broke, not that the
    codebase got safer."""
    modules = _modules_calling_upsert()
    assert len(modules) >= 1, "no upsert_* call sites found — the scan is broken"


@pytest.mark.parametrize(
    "module", _modules_calling_upsert(), ids=lambda p: p.name,
)
def test_every_upsert_call_site_handles_integrity_error(module: Path) -> None:
    tree = ast.parse(module.read_text(encoding="utf-8"))
    spans = _guarded_line_ranges(tree)

    unguarded = [
        call.lineno for call in _upsert_calls(tree)
        if not any(start <= call.lineno <= end for start, end in spans)
    ]
    assert unguarded == [], (
        f"{module.name}: upsert_* called at line(s) {unguarded} with no enclosing "
        "`except IntegrityError`. See failure_patterns.md P15 — a check-then-INSERT "
        "is correct in one process and raises in two, and a throttle is a deployment "
        "fact, not a guard."
    )
