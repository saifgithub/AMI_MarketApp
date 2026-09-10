"""DEF403 guard — the CR051 real-users exclusion rule has exactly ONE
canonical definition and every consuming site resolves to it, never a
hand-synced copy.

Two checks, per the failure_patterns.md P34 invariant:

  1. Static scan — the 12 CR125/DEF227-229 probe UUIDs appear as string
     literals in exactly one Python/shell source file in the whole repo
     (`admin_analytics.py`). Any second file matching is a resurrected
     hand-copy — the exact shape DEF403 found in `inbox_store.py`.
  2. Behavioral — every Python site that needs the rule
     (`admin_analytics.is_real_user`/`_real_users_clause`,
     `inbox_store._is_real_tester`, `weekly_room_retro.is_synthetic_user`,
     `verdict_outcomes.excluded_user_ids`) agrees on the identical verdict
     for a fixture covering all three exclusion classes (CR035 synthetic,
     seed-burst fixture, probe-id) plus a genuine real user — against a
     real (sqlite) DB, not just by reading the source.

Cheap and unambiguous by design (failure_patterns.md's "second occurrence"
house rule: an entry without an enforcing check is not done).
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select

from app.db import get_session
from app.db.models import User
from app.services import verdict_outcomes
from app.services.admin_analytics import (
    _EXCLUDED_USER_IDS,
    _real_users_clause,
    is_real_user,
)

REPO_ROOT = Path(__file__).resolve().parents[3]

_PROBE_ID_STRINGS = [str(u) for u in _EXCLUDED_USER_IDS]
assert len(_PROBE_ID_STRINGS) == 12, (
    "fixture expects the 12 CR125/DEF227-229 probe ids — count changed, "
    "update this guard deliberately if that's real"
)

_SEED_BURST_TS = datetime(2026, 5, 24, 5, 10, 30, tzinfo=timezone.utc)


def _iter_source_files():
    for pattern in ("*.py", "*.sh"):
        for path in REPO_ROOT.rglob(pattern):
            # Skip worktrees (other lanes' checkouts), venvs, and caches —
            # this guard is about THIS checkout's source, not every mirror
            # of it on disk. Judge segments RELATIVE to the checkout root:
            # the checkout itself may live under .claude/worktrees/<lane>,
            # and an absolute-path filter would skip every file in it
            # (DEF404 — the vacuity assert fired in a worktree).
            parts = path.relative_to(REPO_ROOT).parts
            if any(
                seg in (
                    ".claude", ".venv", "venv", "__pycache__", "node_modules",
                    ".git",
                )
                for seg in parts
            ):
                continue
            yield path


def test_probe_ids_appear_as_literals_in_exactly_one_file() -> None:
    """The 12 probe UUIDs, as string literals, live in ONE file only.

    A second hit is a resurrected hand-copy of the id list — the DEF403
    drift itself was `inbox_store.py` carrying its own copy that a later
    change (the probe-id additions) never reached.
    """
    hits: dict[Path, int] = {}
    for path in _iter_source_files():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        found = sum(1 for pid in _PROBE_ID_STRINGS if pid in text)
        if found:
            hits[path] = found

    assert hits, "vacuity check: the probe ids must appear SOMEWHERE"
    rel_hits = {str(p.relative_to(REPO_ROOT)): n for p, n in hits.items()}
    assert list(rel_hits) == ["backend/app/services/admin_analytics.py"], (
        "probe-id literals found outside the one canonical file — a "
        f"hand-synced copy has reappeared: {rel_hits}"
    )
    # And the canonical file must actually carry all 12, not a partial list.
    assert hits[REPO_ROOT / "backend/app/services/admin_analytics.py"] == 12


def test_no_second_byte_identical_real_pred_sql_literal() -> None:
    """The raw-SQL predicate string must not be hand-pasted a second time.

    `daily_report.py`/`users.sh` used to carry a literal
    `coalesce(last_app_version,'') <> 'room-benchmark' ...` string; DEF403's
    fix replaced both with a runtime fetch. Guard against it coming back by
    scanning for the room-benchmark clause's distinctive fragment outside
    the one file that is allowed to render it (`admin_analytics.py`) and
    the test files that assert against its OUTPUT (not a second definition).
    """
    needle = "<> 'room-benchmark'"  # the raw-SQL (non-ORM) spelling only
    self_path = Path(__file__).resolve()
    hits = []
    for path in _iter_source_files():
        if path.resolve() == self_path:
            continue  # this file's own docstring names the needle
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if needle in text:
            hits.append(str(path.relative_to(REPO_ROOT)))
    assert hits == [], (
        f"a raw-SQL copy of the CR051 predicate reappeared outside the "
        f"canonical source: {hits}"
    )


def _make_users(s) -> dict[str, UUID]:
    """One user per exclusion class, plus one genuine real user."""
    ids: dict[str, UUID] = {}

    real = uuid4()
    s.add(User(
        id=real, plan="floor_pass", credit_balance=8,
        device_model="iPhone18,1", last_app_version="0.1.0+104",
        created_at=datetime.now(timezone.utc) - timedelta(days=1),
    ))
    ids["real"] = real

    synthetic = uuid4()
    s.add(User(
        id=synthetic, plan="trader", credit_balance=950,
        device_model=None, last_app_version="room-benchmark",
        created_at=datetime.now(timezone.utc) - timedelta(days=10),
    ))
    ids["cr035_synthetic"] = synthetic

    seed = uuid4()
    s.add(User(
        id=seed, plan="floor_pass", credit_balance=0,
        device_model=None, last_app_version=None,
        created_at=_SEED_BURST_TS,
    ))
    ids["seed_fixture"] = seed

    probe = _EXCLUDED_USER_IDS[0]
    s.add(User(
        id=probe, plan="floor_pass", credit_balance=8,
        device_model=None, last_app_version=None,
        created_at=datetime.now(timezone.utc) - timedelta(days=2),
    ))
    ids["probe_by_id"] = probe

    return ids


def test_every_python_site_agrees_on_the_identical_exclusion_set() -> None:
    """`is_real_user`, `_real_users_clause`, and `excluded_user_ids` (the
    `verdict_outcomes` wrapper) must classify every fixture user identically.

    This is the behavioral half: even if the static scan above ever missed
    a rewritten-but-still-divergent copy, a real disagreement on a real DB
    fails here.
    """
    with get_session() as s:
        ids = _make_users(s)

    with get_session() as s:
        clause_ok = {
            uid for (uid,) in s.execute(
                select(User.id).where(_real_users_clause())
            ).all()
        }
        all_users = {
            u.id: u for u in s.execute(select(User)).scalars().all()
        }

    is_real_user_ok = {
        uid for uid, u in all_users.items() if is_real_user(u)
    }
    excluded = verdict_outcomes.excluded_user_ids()
    excluded_ok = set(all_users) - excluded

    assert clause_ok == is_real_user_ok == excluded_ok, (
        "the ORM clause, the Python predicate, and verdict_outcomes' "
        "wrapper disagree on who counts as real:\n"
        f"  _real_users_clause  -> {sorted(clause_ok)}\n"
        f"  is_real_user        -> {sorted(is_real_user_ok)}\n"
        f"  excluded_user_ids   -> {sorted(excluded_ok)}"
    )

    # And the verdict must be the SUBSTANTIVELY correct one, not merely a
    # three-way tie on a wrong answer.
    assert clause_ok == {ids["real"]}, (
        f"expected only the genuine real user to pass; got {clause_ok}"
    )


def test_weekly_room_retro_is_synthetic_user_agrees_with_canonical() -> None:
    """The one script-site left with its own function name
    (`weekly_room_retro.is_synthetic_user`) must be a pure delegation, not
    a reimplementation — this was the actual DEF403 finding: the old
    hand-copy never carried the probe-id exclusion at all.
    """
    import importlib
    import sys

    sys.path.insert(0, str(REPO_ROOT / "backend"))
    wrr = importlib.import_module("scripts.weekly_room_retro")

    with get_session() as s:
        ids = _make_users(s)

    with get_session() as s:
        all_users = {u.id: u for u in s.execute(select(User)).scalars().all()}

    for label, uid in ids.items():
        u = all_users[uid]
        assert wrr.is_synthetic_user(u) == (not is_real_user(u)), (
            f"weekly_room_retro.is_synthetic_user disagrees with the "
            f"canonical rule on the {label} fixture (id={uid})"
        )
    # The probe-id case is the one the old hand-copy silently missed —
    # assert it explicitly rather than only via the loop above.
    probe_user = all_users[ids["probe_by_id"]]
    assert wrr.is_synthetic_user(probe_user) is True


def test_inbox_store_real_tester_uses_canonical_predicate_not_a_copy() -> None:
    """`inbox_store._is_real_tester` must reject every non-real-user
    fixture via the canonical predicate (plus its own suspended/desk
    checks, which are NOT part of the CR051 rule and stay local)."""
    from app.services.inbox_store import _is_real_tester

    with get_session() as s:
        ids = _make_users(s)

    with get_session() as s:
        all_users = {u.id: u for u in s.execute(select(User)).scalars().all()}

    assert _is_real_tester(all_users[ids["real"]]) is True
    assert _is_real_tester(all_users[ids["cr035_synthetic"]]) is False
    assert _is_real_tester(all_users[ids["seed_fixture"]]) is False
    assert _is_real_tester(all_users[ids["probe_by_id"]]) is False


def test_daily_report_sql_fragment_is_sourced_from_the_canonical_clause() -> None:
    """`real_users_where_sql()` (what `daily_report.py`/`users.sh` fetch at
    runtime) is a straight compile of `_real_users_clause()` — same
    predicate, different rendering — proven by re-parsing it back into a
    raw-SQL query against the fixture DB and comparing to the ORM result.
    """
    from sqlalchemy import text as sql_text

    from app.services.admin_analytics import real_users_where_sql

    with get_session() as s:
        ids = _make_users(s)

    frag = real_users_where_sql()
    # Every one of the 12 probe ids must be present in the fetched fragment
    # (this is what daily_report.py/users.sh actually receive over the
    # docker-exec transport) — not a truncated or stale copy.
    for pid in _PROBE_ID_STRINGS:
        assert pid in frag

    with get_session() as s:
        raw_ok = {
            row[0] for row in s.execute(
                sql_text(f"SELECT id FROM users WHERE {frag}")  # noqa: S608
            ).all()
        }
        clause_ok = {
            str(uid) for (uid,) in s.execute(
                select(User.id).where(_real_users_clause())
            ).all()
        }
    assert raw_ok == clause_ok == {str(ids["real"])}
