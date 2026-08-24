"""DEF369 (security review M3) — `credit_service.spend()` must lock the row.

Everything in `spend()` is a read-modify-write on `credit_balance`: read it,
compare to the cost, write the difference. Two concurrent spends that both
read the same starting balance both pass the check, and the second write
clobbers the first — a user with 1 credit buys two Rooms.

**Why it was latent and is not any more.** The review recorded it as masked by
a single worker plus await-free callers. DEF205 removed that mask: 1-on-1 and
Brief now spend through this same function, both are SSE streams, both are
reachable 12x/minute per user, and they share a concurrency cap greater than
one. The window is real now.

**Why this test asserts SQL instead of racing two sessions.** The unit suite
runs on SQLite, where `FOR UPDATE` is silently a no-op — a race test would
either pass for the wrong reason or be flaky. Compiling against the Postgres
dialect asserts the thing that actually matters in production, deterministically
and with no database at all.
"""

from __future__ import annotations

import inspect

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.db.models import User


def _pg(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect())).upper()


def test_a_locked_select_compiles_to_for_update_on_postgres():
    """The mechanism itself, pinned — so a SQLAlchemy change that stopped
    emitting the lock could not pass unnoticed."""
    locked = select(User).where(User.id == None).with_for_update()  # noqa: E711
    assert "FOR UPDATE" in _pg(locked)


def test_an_unlocked_select_does_not_claim_the_lock():
    """The negative half: proves the assertion above discriminates."""
    plain = select(User).where(User.id == None)  # noqa: E711
    assert "FOR UPDATE" not in _pg(plain)


def test_spend_loads_the_user_row_with_for_update():
    """THE regression. `s.get(User, user_id)` without `with_for_update=True`
    is the double-spend window; the fix is that one keyword and nothing else,
    so the guard has to be able to see it."""
    from app.services import credit_service

    src = inspect.getsource(credit_service.spend)
    assert "with_for_update=True" in src, (
        "spend() must take a row lock on the user before reading the balance "
        "it is about to modify"
    )
    # And specifically on the User load, not somewhere incidental.
    assert "s.get(User, user_id, with_for_update=True)" in src


def test_the_lock_is_taken_before_the_balance_is_read():
    """Order matters: a lock acquired after the read protects nothing. Both
    the load and the first balance read live in `spend`, so their relative
    position is checkable."""
    from app.services import credit_service

    src = inspect.getsource(credit_service.spend)
    lock_at = src.index("with_for_update=True")
    read_at = src.index("old_balance = user.credit_balance")
    assert lock_at < read_at, "the row must be locked before its balance is read"


def test_spend_still_works_end_to_end_under_the_lock():
    """SQLite ignores FOR UPDATE, so this proves only that adding it did not
    break the ordinary path — which is the other way this change could go
    wrong."""
    from app.services.auth_service import AuthService
    from app.services.credit_service import balance_for, spend

    user, _token, _ = AuthService().ensure_anonymous(device_user_id=None)
    before = balance_for(user.id)[0]
    new_balance, cost = spend(user.id, 2, reason="test:def369")
    assert cost == 2
    assert new_balance == before - 2
    assert balance_for(user.id)[0] == before - 2
