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
    populate_existing_calls = [
        c for c in calls
        if any(
            kw.arg == "populate_existing"
            and isinstance(kw.value, ast.Constant)
            and kw.value.value is True
            for kw in c.keywords
        )
    ]
    assert populate_existing_calls, (
        "_lock_user_row's session.get(...) call must ALSO pass "
        "populate_existing=True as a literal keyword (RETRO-SECURITY MAJOR-1, "
        "round 3). Without it, SQLAlchemy 2.0's Session.get(with_for_update=True) "
        "takes the row lock but returns the identity-map object with its "
        "PRE-lock attributes — the caller re-reads a stale credit_balance right "
        "after 'locking' it. Measured on real Postgres by the round-2 auditor: "
        "pack_vs_spend landed on 15 instead of 14, admin_vs_spend on 6 instead "
        "of 5 — the lock was taken and then ignored."
    )


def test_lock_user_row_re_reads_the_balance_after_a_concurrent_write() -> None:
    """Round 3 sqlite-runnable regression for MAJOR-1's re-read half.

    SQLite ignores FOR UPDATE, but `populate_existing` is a SQLAlchemy ORM
    identity-map behaviour, not a database lock — it is fully exercisable on
    SQLite. This proves the actual bug the auditor measured on Postgres: with
    `user` already loaded in `s`'s identity map (exactly `add_credit_pack`'s
    and `adjust_credits`'s shape — load, then `_lock_user_row`), a second
    session commits a change to the same row, and `_lock_user_row`'s return
    value must see the NEW balance, not the one `user` was loaded with.

    Without `populate_existing=True`, `session.get(...)` returns the same
    Python object already in the identity map untouched — the mutation from
    the second session is invisible until something else expires/refreshes
    it, which is exactly how a concurrent spend's write got erased.
    """
    from app.db import get_session
    from app.db.models import User
    from app.services.auth_service import AuthService
    from app.services.credit_service import _lock_user_row

    user, _token, _ = AuthService().ensure_anonymous(device_user_id=None)

    with get_session() as s1:
        loaded = s1.get(User, user.id)
        assert loaded is not None
        starting_balance = loaded.credit_balance

        # A concurrent writer (a spend, in the real race) commits a change
        # to the same row via its OWN session while s1 still holds `loaded`
        # in its identity map with the old balance.
        with get_session() as s2:
            other = s2.get(User, user.id)
            assert other is not None
            other.credit_balance = starting_balance - 1

        relocked = _lock_user_row(s1, loaded)
        assert relocked.credit_balance == starting_balance - 1, (
            "_lock_user_row must re-read the row's current balance after "
            "taking the lock — it returned the pre-lock value, reproducing "
            "the round-2 MAJOR-1 gap (populate_existing missing)"
        )


def test_ensure_period_does_not_re_grant_over_a_concurrent_rollover() -> None:
    """Round 4 sqlite-runnable regression for MAJOR-1's last open path.

    `_ensure_period` (round 3) still decided `eff` / `window_rolled` /
    `plan_drifted` from the CALLER's pre-lock `user`, took the lock via
    `_lock_user_row`, then wrote `ALLOWANCE[eff]` unconditionally. The lock's
    `populate_existing` refreshes the balance the code then USES for the old
    baseline, but nothing re-checked whether a re-grant was still due — so a
    concurrent writer that already rolled the window (or re-tagged the plan)
    in the gap between this call's load and its lock gets its own write
    re-granted straight over the top.

    Reproduced live on Postgres by the round-3 auditor: a `GET /mandate`
    balance read racing a RevenueCat pack webhook at month rollover erased
    the just-delivered paid pack (160 expected, 150 delivered) — because
    `_ensure_period`, called first inside `add_credit_pack`, saw the rolled
    window on the LOCKED row (good, thanks to `populate_existing`) but wrote
    the plain allowance again even though the concurrent caller's own
    `_ensure_period` had already granted it for this period.

    This test drives the same shape without needing Postgres's `FOR UPDATE`
    semantics: the property under test — "don't re-grant when a concurrent
    writer already brought the period up to date" — is a pure Python decision
    made from ORM-visible state (`populate_existing`'s refresh), exercisable
    on SQLite exactly like `test_lock_user_row_re_reads_the_balance_after_a_-
    concurrent_write` above.
    """
    from datetime import timedelta

    from app.db import get_session
    from app.db.models import User
    from app.schemas.mandate import Plan
    from app.services.auth_service import AuthService
    from app.services.credit_service import ALLOWANCE, _ensure_period, _month_start, _utcnow

    user, _token, _ = AuthService().ensure_anonymous(device_user_id=None)
    last_month = _month_start(_utcnow()) - timedelta(days=1)

    # Stale, last-period bookkeeping committed first — as if this row was
    # last touched before anyone rolled it for the new month.
    with get_session() as setup:
        row = setup.get(User, user.id)
        assert row is not None
        row.credit_balance = 3
        row.credits_period_start = last_month
        row.credits_plan_at_grant = Plan.FLOOR_PASS.value

    with get_session() as s1:
        # s1 loads the same stale snapshot a real caller's `_ensure_period`
        # would (e.g. `balance_for`'s `s.get(User, user_id)`), READ ONLY —
        # nothing pending on this transaction yet.
        loaded = s1.get(User, user.id)
        assert loaded is not None
        assert loaded.credits_period_start.replace(tzinfo=None) == last_month.replace(tzinfo=None)

        # A concurrent writer (the real race: another request's own
        # `_ensure_period`, e.g. from a pack webhook) commits the rollover
        # AND spends against the fresh allowance, all before s1 takes its
        # lock — s1's transaction has made no writes yet, so this commits
        # cleanly on SQLite instead of deadlocking against s1.
        with get_session() as s2:
            other = s2.get(User, user.id)
            assert other is not None
            other.credit_balance = ALLOWANCE[Plan.FLOOR_PASS] - 1  # granted, then spent 1
            other.credits_period_start = _month_start(_utcnow())
            other.credits_plan_at_grant = Plan.FLOOR_PASS.value

        eff = _ensure_period(s1, loaded)
        s1.flush()
        assert eff == Plan.FLOOR_PASS
        refreshed = s1.get(User, user.id, populate_existing=True)
        assert refreshed.credit_balance == ALLOWANCE[Plan.FLOOR_PASS] - 1, (
            "_ensure_period must not re-grant the allowance a concurrent "
            "writer already brought this period up to date for — it "
            "overwrote the concurrent spend with a fresh ALLOWANCE, "
            "reproducing the round-3 MAJOR-1 gap (decision made pre-lock)"
        )


def test_ensure_period_does_not_re_grant_over_a_concurrent_plan_drift() -> None:
    """Round 4 — the plan-drift branch of the same gap, which the round-3
    auditor named but did not drive (it drove only the rollover branch).

    Same shape: this session's `user` is stale (still tagged for the OLD
    effective plan), a concurrent writer already re-tags the row for the NEW
    effective plan (e.g. a trial expiring, caught by a Room run's own
    `_ensure_period` call) and grants that plan's allowance, then THIS call's
    `_ensure_period` must see the drift is already resolved on the locked row
    and must not clobber the concurrent grant with its own recomputation.
    """
    from app.db import get_session
    from app.db.models import User
    from app.schemas.mandate import Plan
    from app.services.auth_service import AuthService
    from app.services.credit_service import ALLOWANCE, _ensure_period, _month_start, _utcnow

    user, _token, _ = AuthService().ensure_anonymous(device_user_id=None)
    month_start = _month_start(_utcnow())

    # Same period, but still tagged for trader — stale relative to what a
    # concurrent caller is about to do. Committed first, like the rollover
    # test above, so s1's own load is read-only until `_ensure_period` runs.
    with get_session() as setup:
        row = setup.get(User, user.id)
        assert row is not None
        row.plan = Plan.FLOOR_PASS.value
        row.credit_balance = 3
        row.credits_period_start = month_start
        row.credits_plan_at_grant = Plan.TRADER.value

    with get_session() as s1:
        loaded = s1.get(User, user.id)
        assert loaded is not None
        assert loaded.credits_plan_at_grant == Plan.TRADER.value

        # Concurrent writer: the drift is real (plan really did change to
        # floor_pass) and it already re-granted + re-tagged for it, then the
        # user spent some of the fresh allowance.
        with get_session() as s2:
            other = s2.get(User, user.id)
            assert other is not None
            other.plan = Plan.FLOOR_PASS.value
            other.credit_balance = ALLOWANCE[Plan.FLOOR_PASS] - 2
            other.credits_period_start = month_start
            other.credits_plan_at_grant = Plan.FLOOR_PASS.value

        eff = _ensure_period(s1, loaded)
        s1.flush()
        assert eff == Plan.FLOOR_PASS
        refreshed = s1.get(User, user.id, populate_existing=True)
        assert refreshed.credit_balance == ALLOWANCE[Plan.FLOOR_PASS] - 2, (
            "_ensure_period must not re-grant over a concurrent writer that "
            "already resolved the same plan drift — it re-decided from the "
            "pre-lock plan_drifted=True instead of re-checking the locked "
            "row, reproducing the round-3 MAJOR-1 gap on the drift branch"
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
