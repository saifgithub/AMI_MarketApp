"""DEF499 — NULL-run_id uniqueness for sim_portfolios and portfolio_nav_daily.

`uq_portfolio_user_kind_run` / `uq_nav_user_run_date` never fired for training
rows (run_id NULL; NULLs are distinct in a unique index), so a concurrent first
touch produced two `training` portfolios and every `scalar_one_or_none()` over
the pair raised MultipleResultsFound. The partial unique indexes make the
constraint real; `ensure_portfolio` now recovers from losing the insert race.
The migration test drives the dedupe against SQLite (the chain itself holds
Postgres-only DDL elsewhere, so it cannot run end to end here).
"""

from __future__ import annotations

import importlib.util
import threading
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.db import get_session
from app.db.models import PortfolioNavDailyRow, SimHoldingRow, SimPortfolioRow
from app.db.session import get_engine
from app.services.sim_engine import SimEngine

_MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic" / "versions" / "def499a0b0c0d2_unique_null_run_portfolio_nav.py"
)


def _migration():
    spec = importlib.util.spec_from_file_location("def499_migration", _MIGRATION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _portfolio(user_id, *, cash=10_000.0, created=None, kind="training", run_id=None):
    return SimPortfolioRow(
        id=uuid4(), user_id=user_id, kind=kind, run_id=run_id, name="Main",
        starting_capital=10_000.0, current_cash=cash,
        created_at=created or datetime.now(timezone.utc),
    )


def _nav(user_id, day, nav=10_000.0):
    return PortfolioNavDailyRow(
        user_id=user_id, run_id=None, as_of_date=day, nav=nav, cash=nav,
        price_source="live", created_at=datetime.now(timezone.utc),
    )


def test_second_training_portfolio_is_rejected_by_the_database():
    uid = uuid4()
    with get_session() as s:
        s.add(_portfolio(uid))
    with pytest.raises(IntegrityError):
        with get_session() as s:
            s.add(_portfolio(uid))


def test_second_training_nav_row_same_day_is_rejected_by_the_database():
    uid = uuid4()
    with get_session() as s:
        s.add(_nav(uid, date(2026, 11, 20)))
    with pytest.raises(IntegrityError):
        with get_session() as s:
            s.add(_nav(uid, date(2026, 11, 20)))


def test_game_portfolios_with_distinct_runs_still_coexist_with_training():
    uid = uuid4()
    with get_session() as s:
        s.add(_portfolio(uid))
        s.add(_portfolio(uid, kind="game", run_id=uuid4()))
        s.add(_portfolio(uid, kind="game", run_id=uuid4()))
    with get_session() as s:
        assert len(s.execute(select(SimPortfolioRow)).scalars().all()) == 3


def test_ensure_portfolio_losing_the_insert_race_returns_the_winner(monkeypatch):
    sim = SimEngine()
    uid = uuid4()
    winner = sim.ensure_portfolio(uid)

    real = SimEngine._load_portfolio_row
    calls = {"n": 0}

    def stale_first_read(self, s, user_id, **kw):
        calls["n"] += 1
        return None if calls["n"] == 1 else real(self, s, user_id, **kw)

    monkeypatch.setattr(SimEngine, "_load_portfolio_row", stale_first_read)
    loser = sim.ensure_portfolio(uid)
    assert loser.id == winner.id
    monkeypatch.undo()
    with get_session() as s:
        assert len(s.execute(
            select(SimPortfolioRow).where(SimPortfolioRow.user_id == uid)
        ).scalars().all()) == 1


def test_concurrent_first_touch_yields_one_row_and_one_id(monkeypatch):
    sim = SimEngine()
    uid = uuid4()
    barrier = threading.Barrier(2)
    real = SimEngine._load_portfolio_row
    seen = threading.local()

    def synchronised(self, s, user_id, **kw):
        row = real(self, s, user_id, **kw)
        if not getattr(seen, "done", False):
            seen.done = True
            try:
                barrier.wait(timeout=5)
            except threading.BrokenBarrierError:
                pass
        return row

    monkeypatch.setattr(SimEngine, "_load_portfolio_row", synchronised)
    ids: list = []
    errors: list = []

    def work():
        try:
            ids.append(sim.ensure_portfolio(uid).id)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=work) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    monkeypatch.undo()

    assert not errors, errors
    assert len(ids) == 2 and ids[0] == ids[1]
    with get_session() as s:
        assert len(s.execute(
            select(SimPortfolioRow).where(SimPortfolioRow.user_id == uid)
        ).scalars().all()) == 1


# ── migration dedupe ──────────────────────────────────────────────────────


@pytest.fixture
def legacy_db():
    """The pre-migration state: tables exist, the two partial indexes do not."""
    mod = _migration()
    eng = get_engine()
    with eng.begin() as c:
        c.execute(text(f"DROP INDEX IF EXISTS {mod.PORTFOLIO_INDEX}"))
        c.execute(text(f"DROP INDEX IF EXISTS {mod.NAV_INDEX}"))
    return mod, eng


def _count(eng, table):
    with eng.connect() as c:
        return c.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()


def test_migration_deletes_empty_duplicates_keeps_earliest(legacy_db):
    mod, eng = legacy_db
    uid = uuid4()
    t0 = datetime(2026, 9, 28, 2, 34, tzinfo=timezone.utc)
    with get_session() as s:
        for i in range(3):
            s.add(_portfolio(uid, created=t0.replace(microsecond=i * 1000)))
    with get_session() as s:
        first = s.execute(
            select(SimPortfolioRow.id).where(SimPortfolioRow.user_id == uid)
            .order_by(SimPortfolioRow.created_at)
        ).scalars().first()
    with eng.begin() as c:
        assert mod._dedupe_portfolios(c) == 2
    with get_session() as s:
        rows = s.execute(
            select(SimPortfolioRow.id).where(SimPortfolioRow.user_id == uid)
        ).scalars().all()
    assert rows == [first]
    with eng.begin() as c:
        assert mod._dedupe_portfolios(c) == 0


def test_migration_survivor_is_the_row_with_children_and_children_stay(legacy_db):
    mod, eng = legacy_db
    uid = uuid4()
    early = _portfolio(uid, created=datetime(2026, 9, 28, tzinfo=timezone.utc))
    late = _portfolio(uid, created=datetime(2026, 9, 29, tzinfo=timezone.utc))
    with get_session() as s:
        s.add_all([early, late])
        s.flush()
        s.add(SimHoldingRow(portfolio_id=late.id, ticker="AAPL", quantity=1, avg_cost=1))
    with eng.begin() as c:
        assert mod._dedupe_portfolios(c) == 1
    with get_session() as s:
        ids = s.execute(
            select(SimPortfolioRow.id).where(SimPortfolioRow.user_id == uid)
        ).scalars().all()
        held = s.execute(select(SimHoldingRow.portfolio_id)).scalars().all()
    assert ids == [late.id] and held == [late.id]


def test_migration_repoints_loser_children_when_no_conflict(legacy_db):
    mod, eng = legacy_db
    uid = uuid4()
    a = _portfolio(uid, created=datetime(2026, 9, 28, tzinfo=timezone.utc))
    b = _portfolio(uid, created=datetime(2026, 9, 29, tzinfo=timezone.utc))
    with get_session() as s:
        s.add_all([a, b])
        s.flush()
        s.add_all([
            SimHoldingRow(portfolio_id=a.id, ticker="AAPL", quantity=1, avg_cost=1),
            SimHoldingRow(portfolio_id=a.id, ticker="MSFT", quantity=1, avg_cost=1),
            SimHoldingRow(portfolio_id=b.id, ticker="NVDA", quantity=1, avg_cost=1),
        ])
    with eng.begin() as c:
        assert mod._dedupe_portfolios(c) == 1
    with get_session() as s:
        held = s.execute(select(SimHoldingRow.portfolio_id)).scalars().all()
    assert len(held) == 3 and set(held) == {a.id}


def test_migration_aborts_on_colliding_children_and_changes_nothing(legacy_db):
    mod, eng = legacy_db
    uid = uuid4()
    a = _portfolio(uid, created=datetime(2026, 9, 28, tzinfo=timezone.utc))
    b = _portfolio(uid, created=datetime(2026, 9, 29, tzinfo=timezone.utc))
    with get_session() as s:
        s.add_all([a, b])
        s.flush()
        s.add_all([
            SimHoldingRow(portfolio_id=a.id, ticker="AAPL", quantity=1, avg_cost=1),
            SimHoldingRow(portfolio_id=a.id, ticker="MSFT", quantity=1, avg_cost=1),
            SimHoldingRow(portfolio_id=b.id, ticker="AAPL", quantity=1, avg_cost=1),
        ])
    with pytest.raises(mod.DuplicateDataConflict) as exc:
        with eng.begin() as c:
            mod._dedupe_portfolios(c)
    assert str(b.id).replace("-", "") in str(exc.value).replace("-", "")
    assert _count(eng, "sim_portfolios") == 2


def test_migration_aborts_when_loser_cash_was_touched(legacy_db):
    mod, eng = legacy_db
    uid = uuid4()
    with get_session() as s:
        s.add(_portfolio(uid, created=datetime(2026, 9, 28, tzinfo=timezone.utc)))
        s.add(_portfolio(uid, cash=9_500.0, created=datetime(2026, 9, 29, tzinfo=timezone.utc)))
    with pytest.raises(mod.DuplicateDataConflict):
        with eng.begin() as c:
            mod._dedupe_portfolios(c)
    assert _count(eng, "sim_portfolios") == 2


def test_migration_dedupes_identical_nav_rows_and_aborts_on_differing(legacy_db):
    mod, eng = legacy_db
    uid, day = uuid4(), date(2026, 11, 20)
    with get_session() as s:
        s.add(_nav(uid, day))
        s.add(_nav(uid, day))
    with eng.begin() as c:
        assert mod._dedupe_nav(c) == 1
    assert _count(eng, "portfolio_nav_daily") == 1

    uid2 = uuid4()
    with get_session() as s:
        s.add(_nav(uid2, day))
        s.add(_nav(uid2, day, nav=9_000.0))
    with pytest.raises(mod.DuplicateDataConflict):
        with eng.begin() as c:
            mod._dedupe_nav(c)


def test_migration_upgrade_adds_both_indexes_and_downgrade_drops_them(legacy_db):
    mod, eng = legacy_db
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    def _index_names():
        with eng.connect() as c:
            return {
                r[0] for r in c.execute(
                    text("SELECT name FROM sqlite_master WHERE type='index'")
                )
            }

    with eng.begin() as c:
        with Operations.context(MigrationContext.configure(c)):
            mod.upgrade()
            mod.upgrade()
    assert {mod.PORTFOLIO_INDEX, mod.NAV_INDEX} <= _index_names()
    with eng.begin() as c:
        with Operations.context(MigrationContext.configure(c)):
            mod.downgrade()
    assert not ({mod.PORTFOLIO_INDEX, mod.NAV_INDEX} & _index_names())
