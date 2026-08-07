"""DEF225 — no test may read a source file through a cwd-relative path.

Two guards in `test_cr136_health_gate.py` did `ast.parse(Path("app/....py")
.read_text())`. That resolves only when pytest is invoked from `backend/`. The
command CLAUDE.md actually documents is `pytest backend/tests/unit/ -q` from the
repo root, and under it both raised `FileNotFoundError` — so the documented
command reported 2 failures on a clean tree, and anyone bisecting a real
regression had to first work out that two of them were noise.

The sharper cost is the other direction. Both are *structural* guards — "the
free tiles route must be incapable of calling `enforce_gate`", "the gate module
must not import the journal enum". A structural guard that errors is a guard
that is not checking anything, and an error is easy to wave through as an
environment quirk. This was found by running the documented command, not by a
test failing where anyone was looking.

Matches on SHAPE, not on a filename list (P15): any `Path("...")` literal whose
argument looks like a repo source path is caught, whoever writes it and whatever
they call it. `Path(__file__)`, tmp_path fixtures and non-source strings are
untouched.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_UNIT_DIR = Path(__file__).resolve().parent

# Directory prefixes that mean "a source file in this repo". A relative path
# starting with one of these is the bug; anything else (a tmpdir name, a URL
# fragment, a bare filename used as a label) is not this guard's business.
_SOURCE_PREFIXES = ("app/", "tests/", "backend/", "alembic/", "scripts/")


def _test_files() -> list[Path]:
    return sorted(p for p in _UNIT_DIR.glob("test_*.py") if p.name != Path(__file__).name)


def _relative_source_path_literals(tree: ast.AST) -> list[str]:
    """Every `Path("<repo-source-path>")` whose argument is not absolute.

    Only `Path(...)` calls are inspected: a plain string containing "app/" is
    usually a log key, a route or a comment, and flagging those would make the
    guard noisy enough to be disabled — which is worse than not having it.
    """
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        if name != "Path" or not node.args:
            continue
        arg = node.args[0]
        if not isinstance(arg, ast.Constant) or not isinstance(arg.value, str):
            continue
        value = arg.value
        if value.startswith("/"):
            continue
        if value.startswith(_SOURCE_PREFIXES):
            found.append(value)
    return found


@pytest.mark.parametrize("path", _test_files(), ids=lambda p: p.name)
def test_no_test_reads_a_source_file_by_cwd_relative_path(path: Path) -> None:
    offenders = _relative_source_path_literals(ast.parse(path.read_text()))
    assert not offenders, (
        f"{path.name} builds a source path relative to the cwd: {offenders}. "
        "It passes from backend/ and raises FileNotFoundError from the repo root. "
        "Anchor it to the test file instead: Path(__file__).resolve().parents[2] (DEF225)."
    )


def test_the_guard_would_catch_the_original_defect() -> None:
    """Vacuity check — the detector fires on DEF225's exact original source.

    Without this, a refactor that quietly narrowed `_relative_source_path_literals`
    would leave every parametrised case above passing on an empty result set,
    which is indistinguishable from the codebase being clean.
    """
    original = 'from pathlib import Path\ntree = ast.parse(Path("app/services/health_gate.py").read_text())\n'
    assert _relative_source_path_literals(ast.parse(original)) == [
        "app/services/health_gate.py"
    ]

    anchored = 'tree = ast.parse((_BACKEND_ROOT / "app" / "services" / "health_gate.py").read_text())\n'
    assert _relative_source_path_literals(ast.parse(anchored)) == []
