"""CR125 audit MINOR — `allow_expired` / `allow_legacy` must keep exactly one
caller.

Both flags relax a real authentication check, and the entire argument that
they are safe rests on *where* they are used: `get_rebootstrap_identity_optional`,
behind `/v1/auth/anon`, answering the single question "does this caller hold a
token we issued for the user they claim to be?" — never authorizing a request.

A second caller silently invalidates that argument. `allow_expired` would mean
an expired token authenticates something; `allow_legacy` would mean a token
with no revocation field does. Neither would look wrong at the call site, which
is exactly why this is a test and not a comment.

The guard matches the flag being passed truthy, not the name of the function
receiving it — matching a name would only test whether someone followed a
convention (P15).
"""

from __future__ import annotations

import ast
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
APP = BACKEND / "app"

FLAGS = ("allow_expired", "allow_legacy")

# The one function entitled to relax these, and the file it lives in.
SANCTIONED_FUNCTION = "get_rebootstrap_identity_optional"
SANCTIONED_FILE = APP / "api" / "dependencies.py"


def _truthy_flag_calls(tree: ast.AST) -> list[tuple[str, int]]:
    """Every call passing one of FLAGS as a literal True, with the name of the
    enclosing function. A `False` (or an omitted flag) is the default and is
    not a widening, so it doesn't count."""
    found: list[tuple[str, int]] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.stack: list[str] = []

        def _visit_func(self, node) -> None:
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        visit_FunctionDef = _visit_func
        visit_AsyncFunctionDef = _visit_func

        def visit_Call(self, node: ast.Call) -> None:
            for kw in node.keywords:
                if (
                    kw.arg in FLAGS
                    and isinstance(kw.value, ast.Constant)
                    and kw.value.value is True
                ):
                    found.append((self.stack[-1] if self.stack else "<module>", node.lineno))
            self.generic_visit(node)

    Visitor().visit(tree)
    return found


def test_the_relaxing_flags_are_used_in_exactly_one_place():
    offenders: list[str] = []
    sanctioned = 0

    for path in sorted(APP.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for func_name, lineno in _truthy_flag_calls(tree):
            if path == SANCTIONED_FILE and func_name == SANCTIONED_FUNCTION:
                sanctioned += 1
                continue
            offenders.append(
                f"{path.relative_to(BACKEND)}:{lineno} in {func_name}()"
            )

    assert not offenders, (
        "allow_expired / allow_legacy relax an authentication check and are "
        f"safe only inside {SANCTIONED_FUNCTION}(), which proves ownership on "
        "/v1/auth/anon and authorizes nothing. New use(s) found: "
        f"{offenders}. If a second caller is genuinely needed, the safety "
        "argument in parse_scaffold_token's docstring has to be rewritten "
        "first — and this guard updated in the same commit, saying why."
    )
    assert sanctioned >= 1, (
        "no truthy allow_expired/allow_legacy call found at all — either the "
        f"re-bootstrap leniency was removed (which re-orphans every anonymous "
        "account, see test_cr125_secure_session.py) or this guard has drifted "
        "off the code it is meant to watch."
    )
