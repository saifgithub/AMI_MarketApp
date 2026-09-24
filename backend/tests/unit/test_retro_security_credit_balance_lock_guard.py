"""RETRO-SECURITY (round 2, U68 MAJOR-1) — every write to `users.credit_balance`
goes through the ONE locked path, or the build fails.

DEF369 row-locked exactly one of eight read-modify-write sites on this column
(`credit_service.spend()`). The auditor found the other seven read the balance
unlocked and wrote a Python-computed literal back — same lost-update shape,
different door — and measured it live on Postgres (round 1 run report): a
`refund(+1)` racing a `spend(-1)` from a balance of 5 landed the final balance
on 6, not 5. The spend's write evaporated.

Round 2 routes every writer through `credit_service._lock_user_row` (a thin
`session.get(User, user.id, with_for_update=True)` re-select, taken inside the
caller's own open transaction before the balance is read). This guard is the
"CLAUDE.md second-occurrence rule" enforcement: an AST scan over every
function in `app/` that assigns `<name>.credit_balance = ...`, failing unless
that function's source also calls `_lock_user_row(` (or, for `spend()`/
`refund()` which lock at load instead of via the shared helper, contains
`with_for_update=True` before the assignment).

**Why this reads source instead of racing sessions.** Same reasoning as
`test_def369_spend_takes_a_row_lock.py`: SQLite (the unit-test engine) makes
`FOR UPDATE` a silent no-op, so a race test on this stack would either pass
for the wrong reason or be flaky. Compiling/inspecting the guarantee
statically is what actually holds in every environment, deterministically,
with no database at all. The auditor's own round-1 Postgres probe
(`refund_vs_spend`, start=5 -> final=6) is the property this guard protects;
re-measuring THAT number on real Postgres after this fix is exactly the kind
of check a unit suite cannot perform and is called out in the round-2 lane
note for the auditor to re-run.

**Why an AST scan of assignment targets, not a name allowlist.** A guard that
listed "these 8 functions are fine" would pass the moment a NINTH unlocked
writer was added anywhere in `app/` — the same blind spot P15's guard's first
version had (matching `upsert_*` by name instead of the check-then-insert
shape). Scanning for the ASSIGNMENT ITSELF means a new writer is caught by
construction, not by someone remembering to update an inventory.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[2]
_APP = _BACKEND / "app"

# The one sanctioned entry point. Every write to `credit_balance` must be
# preceded, in its own enclosing function's source, by a call to this helper
# (which does the actual `with_for_update=True` re-select) — OR be one of the
# two functions that lock directly at load time instead of via the helper,
# because they start from a bare user_id rather than an already-loaded User.
_LOCK_HELPER_CALL = "_lock_user_row("
_DIRECT_LOAD_LOCK = "with_for_update=True"

# (module, function) pairs that assign `credit_balance` directly at load time
# via `with_for_update=True` rather than calling `_lock_user_row` — both are
# the sanctioned shape; `_lock_user_row` itself is only meaningful when a
# `User` object already exists to re-lock.
_DIRECT_LOAD_SITES = {
    ("credit_service.py", "spend"),
    ("credit_service.py", "refund"),
}


def _iter_backend_py_files():
    for path in sorted(_APP.rglob("*.py")):
        yield path


def _functions_assigning_credit_balance() -> list[tuple[Path, str, ast.FunctionDef]]:
    """Every (file, function_name, node) that contains `X.credit_balance = ...`
    somewhere in its body (nested functions/closures included, since the
    assignment and the lock can be in the same enclosing def even if a
    sub-node technically owns the line)."""
    found: list[tuple[Path, str, ast.FunctionDef]] = []
    for path in _iter_backend_py_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            assigns_balance = any(
                isinstance(node, ast.Assign)
                and any(
                    isinstance(t, ast.Attribute) and t.attr == "credit_balance"
                    for t in node.targets
                )
                for node in ast.walk(fn)
            )
            if assigns_balance:
                found.append((path, fn.name, fn))
    return found


def test_the_guard_finds_something_to_check() -> None:
    """Vacuity: a guard that scans nothing passes forever."""
    sites = _functions_assigning_credit_balance()
    names = {(p.name, fn) for p, fn, _ in sites}
    assert len(names) >= 6, f"expected the known credit_balance writers, found {names}"


@pytest.mark.parametrize(
    "site",
    sorted(
        {(p.name, fn) for p, fn, _ in _functions_assigning_credit_balance()}
    ),
    ids=lambda s: f"{s[0]}::{s[1]}",
)
def test_every_credit_balance_writer_locks_the_row_first(site: tuple[str, str]) -> None:
    """THE regression. A new function that writes `credit_balance` without
    first calling `_lock_user_row` (or loading with `with_for_update=True`
    directly, for the two functions that start from a bare user_id) is
    exactly DEF369's class through a new door — this must fail the build,
    not wait for a security review to notice."""
    module_name, fn_name = site
    for path in _iter_backend_py_files():
        if path.name != module_name:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for fn in ast.walk(tree):
            if (
                isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
                and fn.name == fn_name
            ):
                src = ast.get_source_segment(path.read_text(encoding="utf-8"), fn) or ""
                is_direct = site in _DIRECT_LOAD_SITES
                required = _DIRECT_LOAD_LOCK if is_direct else _LOCK_HELPER_CALL
                assert required in src, (
                    f"{module_name}::{fn_name} assigns credit_balance but never "
                    f"calls {required!r} — every credit_balance writer must lock "
                    "the row first (RETRO-SECURITY MAJOR-1, round 2). Either route "
                    "the write through credit_service._lock_user_row(session, "
                    "user), or if loading fresh from a user_id, load with "
                    "with_for_update=True directly."
                )
                return
    pytest.fail(f"could not re-locate {module_name}::{fn_name} for source inspection")


def test_lock_user_row_itself_uses_with_for_update() -> None:
    """The helper's own contract, pinned directly — a change to
    `_lock_user_row` that silently dropped the lock would otherwise satisfy
    every test above (they only check that the helper is CALLED) while
    removing the protection entirely.

    Checked against the parsed AST `Call` node, not raw source text: the
    function's own docstring quotes the call verbatim for documentation, so a
    substring check on `inspect.getsource(...)` is satisfied by the docstring
    even after the real `session.get(...)` line has the keyword deleted —
    caught only by mutation-testing this test itself, which is exactly why it
    now inspects the executable node instead of prose that describes it."""
    from app.services import credit_service

    src = inspect.getsource(credit_service._lock_user_row)
    tree = ast.parse(src)
    fn = tree.body[0]
    assert isinstance(fn, ast.FunctionDef)

    # Skip the docstring (body[0] when it's a bare string expression) —
    # everything else is executable code.
    body = fn.body[1:] if (
        fn.body and isinstance(fn.body[0], ast.Expr)
        and isinstance(fn.body[0].value, ast.Constant)
        and isinstance(fn.body[0].value.value, str)
    ) else fn.body

    calls = [
        node for stmt in body for node in ast.walk(stmt)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
    ]
    assert calls, "no session.get(...) call found in _lock_user_row's executable body"
    locking_calls = [
        c for c in calls
        if any(
            kw.arg == "with_for_update"
            and isinstance(kw.value, ast.Constant)
            and kw.value.value is True
            for kw in c.keywords
        )
    ]
    assert locking_calls, (
        "_lock_user_row's session.get(...) call must pass with_for_update=True "
        "as a literal keyword — found none in the executable body (docstring "
        "prose does not count)"
    )


def test_known_writer_inventory_is_exact() -> None:
    """An exact pin, not a floor — same P15 rationale: a NEW unlocked-looking
    writer should stop the build until someone has looked at it, and a writer
    that disappears should have its site removed from here so the next real
    gap doesn't hide behind a stale entry."""
    found = {(p.name, fn) for p, fn, _ in _functions_assigning_credit_balance()}
    known = {
        ("credit_service.py", "_ensure_period"),
        ("credit_service.py", "spend"),
        ("credit_service.py", "set_plan_and_grant_allowance"),
        ("credit_service.py", "add_credit_pack"),
        ("credit_service.py", "carry_billing_on_merge"),
        ("credit_service.py", "refund"),
        ("reputation_service.py", "_grant_milestone"),
        ("admin.py", "adjust_credits"),
    }
    new = found - known
    assert new == set(), (
        f"new credit_balance writer(s) not in the known inventory: {sorted(new)}. "
        "Add the lock (see test_every_credit_balance_writer_locks_the_row_first) "
        "and add the site here, or this guard's parametrize will silently skip it."
    )
    gone = known - found
    assert gone == set(), (
        f"site(s) no longer found: {sorted(gone)}. If renamed/removed, update this "
        "inventory — a stale entry hides the next real unlocked writer."
    )
