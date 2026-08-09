"""CR109 §7.1 — the game trade path must not reuse the training submit path.

The game requires no mandate; the training path requires it unconditionally.
The tempting shortcut is a `skip_compliance=True` argument on the one shared
function — and that is exactly the shape this file exists to prevent, because
a boolean that disables the safety floor is one wrong call site away from
being `True` on the training path. CR040's rule is that a guarantee must be
structural rather than conditional.

So the split is: `_execute_fill()` holds the mechanics and never consults
compliance at all, while *deciding* compliance belongs to each public entry
point. `submit()` runs `check_mandate_compliance` and hands the verdict down.

These assertions are cheap and they are the kind that only ever fail when
someone is midway through reintroducing the bypass.
"""

from __future__ import annotations

import ast
import inspect
import textwrap

from app.services.sim_engine import SimEngine


def _calls_in(func: object) -> set[str]:
    """Every function name actually CALLED inside `func`.

    Deliberately an AST walk rather than a substring search: the docstrings
    around this split necessarily *name* `check_mandate_compliance` while
    explaining the fence, and a naive `in source` check fires on the prose
    that documents the rule it is enforcing. Only a call counts.
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            target = node.func
            if isinstance(target, ast.Name):
                names.add(target.id)
            elif isinstance(target, ast.Attribute):
                names.add(target.attr)
    return names

_BYPASS_TOKENS = (
    "skip_compliance",
    "skip_mandate",
    "bypass_compliance",
    "bypass_mandate",
    "no_compliance",
    "no_mandate",
    "skip_floor",
    "no_floor",
    "ignore_mandate",
    "enforce_compliance",
    "run_compliance",
    "check_compliance",
)


def test_execute_fill_takes_no_compliance_bypass_flag() -> None:
    """No argument may switch the safety floor off. Not on the shared helper,
    and not on any public entry point either — the whole point is that no
    caller can ask for the floor to be skipped."""
    for name in ("_execute_fill", "submit"):
        params = inspect.signature(getattr(SimEngine, name)).parameters
        offenders = [
            p for p in params
            if any(token in p.lower() for token in _BYPASS_TOKENS)
        ]
        assert not offenders, (
            f"SimEngine.{name}() grew a compliance-bypass argument "
            f"{offenders} — CR109 §7.1 forbids it. Keep two public entry "
            f"points whose difference is structural: the training path runs "
            f"check_mandate_compliance, the game path does not run it at all."
        )


def test_execute_fill_never_calls_the_mandate_check() -> None:
    """The shared helper holds mechanics only. If it ever calls the floor
    itself, the game path inherits the mandate it is specified not to have —
    and the only way back out would be the bypass flag above."""
    assert "check_mandate_compliance" not in _calls_in(SimEngine._execute_fill), (
        "SimEngine._execute_fill() now calls check_mandate_compliance. The "
        "helper must stay compliance-agnostic; deciding compliance is the "
        "caller's job (CR109 §7.1)."
    )


def test_training_submit_still_runs_the_mandate_check() -> None:
    """The other half of the fence, and the one that actually protects users:
    extracting the mechanics must never cost the training path its floor.

    A refactor that moved the fill out but forgot to keep the check would
    leave every training trade unscreened while every test about *rejections*
    still passed for the wrong reason.
    """
    assert "check_mandate_compliance" in _calls_in(SimEngine.submit), (
        "SimEngine.submit() no longer calls check_mandate_compliance — the "
        "training path's uncoachable safety floor is gone."
    )
