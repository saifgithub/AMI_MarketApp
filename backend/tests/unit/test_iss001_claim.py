"""ISS001 — `app.db.ami_claim`: the claim() primitive and the tripwire, on synthetic models.

One canary per constraint KIND (composite unique, unique column, natural PK, unique index, the
partial/NULL key that DEF499 was): a bare insert of each must raise `UnclaimedInsert`. They are
the tests that go red if the hook is deleted or muted — the property no earlier guard had
("neither failure was ever detected by the guard failing"). The mutation harness
(`backend/scripts/iss001_mutate.py`) removes each load-bearing line and requires red.

The race is interleaved deterministically on two real connections to one sqlite file: both
sessions SELECT before either INSERTs. sqlite's default (legacy) transaction mode opens no
transaction on SELECT, so nothing serialises the two readers — the same window Postgres has.
Postgres itself is NOT exercised here (partial-index ON CONFLICT inference, READ COMMITTED
re-read): that needs a throwaway schema on melehost before any production path is converted.
"""

from __future__ import annotations

import threading
import uuid
from typing import Optional

import pytest
from sqlalchemy import Index, String, UniqueConstraint, create_engine, func, insert, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.db import ami_claim as ac


class Base(DeclarativeBase):
    pass


class Portfolio(Base):
    """DEF499 as shipped: unique over (user, kind, run_id) with run_id NULL for 'training'."""

    __tablename__ = "portfolios_bad"
    __table_args__ = (UniqueConstraint("user_id", "kind", "run_id", name="uq_bad"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String, default="training")
    run_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class PortfolioFixed(Base):
    """The same table with the partial unique index DEF499 added."""

    __tablename__ = "portfolios_fixed"
    __table_args__ = (
        UniqueConstraint("user_id", "kind", "run_id", name="uq_fixed"),
        Index("uq_fixed_training", "user_id", "kind", unique=True,
              sqlite_where=text("run_id IS NULL"), postgresql_where=text("run_id IS NULL")),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String, default="training")
    run_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class Floor(Base):
    """Unique column (the client_release_floor shape)."""

    __tablename__ = "floors"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    min_build: Mapped[int] = mapped_column(unique=True)
    note: Mapped[str] = mapped_column(String, default="")


class Watch(Base):
    """Composite unique (the watchlist / lesson-progress shape)."""

    __tablename__ = "watch"
    __table_args__ = (UniqueConstraint("user_id", "ticker", name="uq_watch"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String)
    ticker: Mapped[str] = mapped_column(String)


class Ticker(Base):
    """Natural primary key with no default (the TickerReferenceRow shape)."""

    __tablename__ = "tickers"
    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, default="")


class Handle(Base):
    """Unique INDEX rather than a constraint."""

    __tablename__ = "handles"
    __table_args__ = (Index("uq_handles_h", "handle", unique=True),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    handle: Mapped[str] = mapped_column(String)


class Device(Base):
    """A business-unique key with NO constraint (ensure_anonymous's shape)."""

    __tablename__ = "devices"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    device_user_id: Mapped[str] = mapped_column(String, index=True)


class Log(Base):
    """Append-only, surrogate uuid PK, nothing unique: must NOT be flagged."""

    __tablename__ = "logs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    msg: Mapped[str] = mapped_column(String)


@pytest.fixture()
def factory(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path/'t.db'}")
    Base.metadata.create_all(eng)
    return sessionmaker(eng, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def tripwire(factory):
    off = ac.install_tripwire(Base.metadata, engine=factory.kw["bind"], mode="raise")
    yield
    off()


def _count(factory, model) -> int:
    with factory() as s:
        return s.scalar(select(func.count()).select_from(model))


# ---- the problem, reproduced --------------------------------------------------------------


def test_naive_pattern_on_vacuous_constraint_writes_two_rows_silently(factory):
    """DEF499: two readers both see nothing, both insert. NULL run_id => the constraint never fires."""
    a, b = factory(), factory()
    ra = a.execute(select(Portfolio).filter_by(user_id="u", kind="training", run_id=None)).scalar_one_or_none()
    rb = b.execute(select(Portfolio).filter_by(user_id="u", kind="training", run_id=None)).scalar_one_or_none()
    assert ra is None and rb is None
    a.add(Portfolio(user_id="u")); a.commit()
    b.add(Portfolio(user_id="u")); b.commit()          # no exception. That is the bug.
    assert _count(factory, Portfolio) == 2


def test_naive_pattern_on_real_constraint_raises_on_the_loser(factory):
    a, b = factory(), factory()
    assert a.execute(select(Floor).filter_by(min_build=7)).scalar_one_or_none() is None
    assert b.execute(select(Floor).filter_by(min_build=7)).scalar_one_or_none() is None
    a.add(Floor(min_build=7)); a.commit()
    b.add(Floor(min_build=7))
    with pytest.raises(IntegrityError):
        b.commit()


# ---- canaries: one per constraint kind ---------------------------------------------------


@pytest.mark.parametrize(
    "model, kwargs",
    [
        pytest.param(Watch, {"user_id": "u", "ticker": "AAPL"}, id="composite-unique"),
        pytest.param(Floor, {"min_build": 1}, id="unique-column"),
        pytest.param(Ticker, {"symbol": "AAPL"}, id="natural-pk"),
        pytest.param(Handle, {"handle": "h"}, id="unique-index"),
        pytest.param(Portfolio, {"user_id": "u", "run_id": None}, id="null-key-vacuous-composite"),
        pytest.param(PortfolioFixed, {"user_id": "u", "run_id": None}, id="null-key-partial-index"),
    ],
)
def test_canary_bare_insert_of_every_constraint_kind_raises(factory, tripwire, model, kwargs):
    with factory() as s:
        s.add(model(**kwargs))
        with pytest.raises(ac.UnclaimedInsert):
            s.flush()


def test_canary_is_not_vacuous_without_the_hook_the_same_insert_passes(factory):
    """The canaries above discriminate: with no tripwire installed, the identical insert is silent."""
    with factory() as s:
        s.add(Watch(user_id="u", ticker="AAPL"))
        s.commit()


def test_canary_uninstall_removes_the_hook(factory):
    off = ac.install_tripwire(Base.metadata, engine=factory.kw["bind"], mode="raise")
    assert ac.tripwire_installed(factory.kw["bind"])
    off()
    assert not ac.tripwire_installed(factory.kw["bind"])


@pytest.mark.parametrize("how", ["core", "text", "bulk"])
def test_tripwire_sees_inserts_the_orm_never_saw(factory, tripwire, how):
    """No model inference to be taught: the driver boundary sees every API."""
    with factory() as s:
        with pytest.raises(ac.UnclaimedInsert):
            if how == "core":
                s.execute(insert(Floor.__table__).values(id=uuid.uuid4(), min_build=2, note=""))
            elif how == "text":
                s.execute(text("INSERT INTO floors (id, min_build, note) VALUES ('x', 3, '')"))
            else:
                s.execute(insert(Floor), [{"min_build": 4}, {"min_build": 5}])


def test_tripwire_leaves_append_only_tables_alone(factory, tripwire):
    with factory() as s:
        s.add(Log(msg="hi"))
        s.commit()


def test_tripwire_allows_claim_and_unclaimed(factory, tripwire):
    with factory() as s:
        ac.claim(s, Floor, key={"min_build": 9})
        with ac.unclaimed(Floor, why="retry-then-raise version sequence"):
            s.add(Floor(min_build=10))
            s.flush()
        s.commit()


def test_unclaimed_needs_a_reason():
    with pytest.raises(ValueError):
        with ac.unclaimed(Floor, why=" "):
            pass


def test_tripwire_log_mode_reports_and_does_not_raise(factory):
    seen: list[ac.Violation] = []
    off = ac.install_tripwire(Base.metadata, engine=factory.kw["bind"], mode="log", on_violation=seen.append)
    try:
        with factory() as s:
            s.add(Floor(min_build=11))
            s.commit()
    finally:
        off()
    assert [(v.table, v.reason) for v in seen] == [("floors", "unclaimed")]


def test_baselined_site_is_reported_not_raised_and_an_unlisted_one_still_raises(factory):
    """A baseline entry is keyed on (table, site); the same table at another site still raises."""
    seen: list[tuple[str, bool]] = []
    remove = ac.add_violation_sink(lambda v, baselined: seen.append((v.table, baselined)))
    off = ac.install_tripwire(
        Base.metadata, engine=factory.kw["bind"], mode="raise", baseline={("floors", "<non-app>"): "t"},
    )
    try:
        with factory() as s:
            s.add(Floor(min_build=12))
            s.flush()                                    # baselined: no raise
            s.add(Watch(user_id="u", ticker="X"))
            with pytest.raises(ac.UnclaimedInsert):
                s.flush()                                # watch is not baselined
    finally:
        off()
        remove()
    assert ("floors", True) in seen and ("watch", False) in seen


# ---- hand-written ON CONFLICT must target an arbiter (VERDICT 6.3) -----------------------


def test_hand_written_on_conflict_with_the_wrong_target_is_a_violation(factory, tripwire):
    with factory() as s:
        with pytest.raises(ac.UnclaimedInsert):
            s.execute(text(
                "INSERT INTO watch (id, user_id, ticker) VALUES ('a', 'u', 'T') "
                "ON CONFLICT (user_id) DO NOTHING"
            ))


def test_hand_written_on_conflict_with_an_arbiter_target_passes(factory, tripwire):
    with factory() as s:
        s.execute(text(
            "INSERT INTO watch (id, user_id, ticker) VALUES ('a', 'u', 'T') "
            "ON CONFLICT (user_id, ticker) DO NOTHING"
        ))
        s.execute(text(
            "INSERT INTO floors (id, min_build, note) VALUES ('f', 1, '') ON CONFLICT DO NOTHING"
        ))
        s.commit()


def test_partial_arbiter_needs_its_where_clause_in_a_hand_written_conflict(factory, tripwire):
    with factory() as s:
        with pytest.raises(ac.UnclaimedInsert):          # (user_id, kind) is the partial index's key, no WHERE
            s.execute(text(
                "INSERT INTO portfolios_fixed (id, user_id, kind) VALUES ('a', 'u', 'k') "
                "ON CONFLICT (user_id, kind) DO NOTHING"
            ))
        s.execute(text(
            "INSERT INTO portfolios_fixed (id, user_id, kind) VALUES ('b', 'u', 'k') "
            "ON CONFLICT (user_id, kind) WHERE run_id IS NULL DO NOTHING"
        ))
        s.commit()


# ---- claim() ------------------------------------------------------------------------------


def test_claim_refuses_a_key_nothing_enforces(factory):
    with factory() as s:
        with pytest.raises(ac.NoArbiter):
            ac.claim(s, Device, key={"device_user_id": "d1"})            # no constraint at all
        with pytest.raises(ac.NoArbiter):
            ac.claim(s, Portfolio, key={"user_id": "u", "kind": "training", "run_id": None})  # vacuous


def test_claim_on_partial_index_is_atomic_for_the_null_case(factory):
    a, b = factory(), factory()
    ca = ac.claim(a, PortfolioFixed, key={"user_id": "u", "kind": "training", "run_id": None})
    a.commit()
    cb = ac.claim(b, PortfolioFixed, key={"user_id": "u", "kind": "training", "run_id": None})
    b.commit()
    assert (ca.created, cb.created) == (True, False)
    assert ca.row.id == cb.row.id
    assert _count(factory, PortfolioFixed) == 1


def test_claim_policies_cover_the_outcomes(factory):
    with factory() as s:
        first = ac.claim(s, Floor, key={"min_build": 7}, values={"note": "a"})
        assert first.created
        s.commit()
    with factory() as s:
        assert ac.claim(s, Floor, key={"min_build": 7}, values={"note": "b"}).or_skip().note == "a"
        row = ac.claim(s, Floor, key={"min_build": 7}, values={"note": "b"}).or_update(lambda r: setattr(r, "note", "b"))
        assert row.note == "b"
        with pytest.raises(ac.Collision):
            ac.claim(s, Floor, key={"min_build": 7}).or_raise()
        with pytest.raises(KeyError):
            ac.claim(s, Floor, key={"min_build": 7}).or_raise(KeyError("custom"))


def test_claim_under_eight_real_threads_yields_one_row_and_one_creator(factory):
    n, rounds = 8, 15
    for r in range(rounds):
        barrier, results, errors = threading.Barrier(n), [], []

        def work():
            try:
                with factory() as s:
                    barrier.wait()
                    c = ac.claim(s, PortfolioFixed, key={"user_id": f"u{r}", "kind": "training", "run_id": None})
                    s.commit()
                    results.append(c.created)
            except Exception as e:  # pragma: no cover - would fail the assert below
                errors.append(e)

        ts = [threading.Thread(target=work) for _ in range(n)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        assert errors == []
        assert results.count(True) == 1 and len(results) == n
    with factory() as s:
        assert s.scalar(select(func.count()).select_from(PortfolioFixed)) == rounds


# ---- schema_truth on synthetic metadata ---------------------------------------------------


def test_schema_truth_flags_the_vacuous_unique_key_and_only_that():
    found = ac.schema_truth(Base.metadata)
    assert any("portfolios_bad" in f and "run_id" in f for f in found)
    assert not any("floors" in f or "logs" in f or "devices" in f or "watch" in f for f in found)


def test_schema_truth_accepts_a_partial_index_that_covers_the_null_rows():
    """DEF499's fix shape: the full constraint stays, a partial unique index covers run_id IS NULL."""
    assert not any("portfolios_fixed" in f for f in ac.schema_truth(Base.metadata))


def test_schema_truth_accepts_a_declared_null_semantic():
    class M(DeclarativeBase):
        pass

    class Evt(M):
        __tablename__ = "evt"
        __table_args__ = (UniqueConstraint("user_id", "ref"),)
        id: Mapped[int] = mapped_column(primary_key=True)
        user_id: Mapped[str] = mapped_column(String)
        ref: Mapped[Optional[str]] = mapped_column(String, nullable=True,
                                                   info={"null_means_no_key": "NULL ref = no dedupe wanted"})

    assert ac.schema_truth(M.metadata) == []
