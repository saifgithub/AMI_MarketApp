"""DEF324 — a test must never be able to reach the developer's real database.

`_resolve_url()`'s last branch exists for solo-dev convenience: with no DB
configured, bind to `backend/.local.db` and keep working. Under pytest that
branch is a trapdoor. `reset_for_tests(url=None)` **deletes**
`AMI_TEST_DATABASE_URL` — its stated job is "leave test mode" — and the next DB
read therefore lands on a real, persistent, **gitignored** file rather than on
the test's own tempfile.

Measured on the machine this was found on: `.local.db` last written 2026-08-02,
stamped four migrations behind head, `sim_holdings` with no `split_adjusted_at`,
and **five `mandates` rows carrying `single_name_cap_pct = None` at
`risk_score = 3`** — a null cap resolving to the risk-tier preset, **3.0%**,
which is the number in DEF321's `position size 68.8% exceeds single-name cap
3.0%` on a test that had just written `100.0`.

Every property that made DEF321 unfalsifiable follows from a *file* rather than
an ordering: it is gitignored, so the shared checkout has it and a fresh
worktree does not — the same commit genuinely behaves differently, which is why
"re-run it SHA-pinned" produced red and green on consecutive runs. A test that
passes alone passes because nothing has torn the variable down yet.

Both halves are guarded here, because they read different state and can fail
independently: the fixture-level restore, and the structural refusal underneath
it. Neither test asserts on `.local.db`'s CONTENTS — the point is that a test
never reaches it, whatever it happens to hold on any given machine.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.db import reset_for_tests
from app.db.session import _resolve_url, get_engine


_LOCAL_DB = Path(__file__).resolve().parents[2] / ".local.db"


def test_a_bare_reset_returns_to_the_suites_database_not_the_developers():
    """The fixture half. `test_def215_schema_ownership.py::fresh_db_url` is the
    only bare caller in the repo, and its `finally: reset_for_tests()` used to
    hand the rest of that test's teardown chain — including the autouse ledger
    invariant — a database nobody in the suite owns.
    """
    before = os.environ["AMI_TEST_DATABASE_URL"]
    assert "ami_trade_test.db" in before, "precondition: _isolated_db owns this test"

    reset_for_tests()

    assert os.environ.get("AMI_TEST_DATABASE_URL") == before, (
        "a bare reset left test mode instead of returning to the suite's DB"
    )
    assert str(_LOCAL_DB) not in str(get_engine().url), (
        f"the engine reached the developer's real database at {_LOCAL_DB}"
    )


def test_the_solo_dev_fallback_refuses_to_serve_a_test(monkeypatch):
    """The structural half, and the one that holds when a future fixture finds
    some other way to clear the variable.

    Degrade LOUDLY (CR040): the alternative — binding silently — is what turned
    this into eight months of an unreproducible flake. The refusal names the
    file and the cause, so the next person reads one sentence instead of
    bisecting a suite.
    """
    from app.db import session as db_session

    monkeypatch.delenv("AMI_TEST_DATABASE_URL", raising=False)
    monkeypatch.setattr(db_session, "_ambient_test_url", None)

    with pytest.raises(RuntimeError, match="refusing the solo-dev sqlite fallback"):
        _resolve_url()


def test_the_refusal_is_scoped_to_pytest_and_does_not_break_the_solo_dev_path(
    monkeypatch,
):
    """Non-vacuity, and the reason the guard reads `PYTEST_CURRENT_TEST` rather
    than simply deleting the branch.

    A developer running the app with no DB configured must still get
    `.local.db` — that is the branch's whole purpose and it is not the defect.
    Deleting it outright would have been the easy fix and the wrong one; the
    defect is reaching it *from a test*. Without this assertion a future
    "simplification" could raise unconditionally and nothing here would notice.
    """
    from app.db import session as db_session

    monkeypatch.delenv("AMI_TEST_DATABASE_URL", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(db_session, "_ambient_test_url", None)

    assert _resolve_url() == f"sqlite:///{_LOCAL_DB}"
