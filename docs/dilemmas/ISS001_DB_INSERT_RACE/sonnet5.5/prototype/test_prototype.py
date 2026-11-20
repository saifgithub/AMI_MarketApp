"""ISS001 prototype tests — each claim in SOLUTION.md §"How a reviewer verifies" has one here.

Run:  python -m pytest docs/dilemmas/ISS001_DB_INSERT_RACE/sonnet5.5/prototype -q
(any Python with SQLAlchemy >= 2.0 and pytest; no repo imports, no Postgres).

The race is interleaved deterministically on two real connections to one sqlite file: both
sessions SELECT before either INSERTs. sqlite's default (legacy) transaction mode opens no
transaction on SELECT, so nothing serialises the two readers — the same window Postgres has.
"""

from __future__ import annotations

import uuid
from typing import Optional

import pytest
from sqlalchemy import (
    Index, String, UniqueConstraint, create_engine, func, select, text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

import ami_claim as ac


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
    """The same table with the missing partial unique index."""

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
    """A plain NOT NULL unique key (the client_release_floor shape)."""

    __tablename__ = "floors"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    min_build: Mapped[int] = mapped_column(unique=True)
    note: Mapped[str] = mapped_column(String, default="")


class Device(Base):
    """device_user_id: a business-unique key with NO constraint (ensure_anonymous's shape)."""

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


def _count(factory, model) -> int:
    with factory() as s:
        return s.scalar(select(func.count()).select_from(model))


# ---- the problem, reproduced ------------------------------------------------------------


def _naive_get_or_create(s: Session, model, **key):
    row = s.execute(select(model).filter_by(**key)).scalar_one_or_none()
    if row is None:
        row = model(**key)
        s.add(row)
        s.flush()
    return row


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
    from sqlalchemy.exc import IntegrityError

    a, b = factory(), factory()
    assert a.execute(select(Floor).filter_by(min_build=7)).scalar_one_or_none() is None
    assert b.execute(select(Floor).filter_by(min_build=7)).scalar_one_or_none() is None
    a.add(Floor(min_build=7)); a.commit()
    b.add(Floor(min_build=7))
    with pytest.raises(IntegrityError):
        b.commit()


# ---- 1. schema truth --------------------------------------------------------------------


def test_schema_truth_flags_the_vacuous_unique_key_and_only_that():
    found = ac.schema_truth(Base.metadata)
    assert any("portfolios_bad" in f and "run_id" in f for f in found)
    # the fixed table has the partial index but ALSO still carries the full constraint, whose
    # nullable run_id is still a finding unless declared — the finding is about the constraint.
    assert not any("floors" in f or "logs" in f or "devices" in f for f in found)


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


# ---- 2. claim() -------------------------------------------------------------------------


def test_claim_refuses_a_key_nothing_enforces(factory):
    with factory() as s:
        with pytest.raises(ac.NoArbiter):
            ac.claim(s, Device, key={"device_user_id": "d1"})            # no constraint at all
        with pytest.raises(ac.NoArbiter):
            ac.claim(s, Portfolio, key={"user_id": "u", "kind": "training", "run_id": None})  # vacuous


def test_claim_on_partial_index_is_atomic_for_the_null_case(factory):
    a, b = factory(), factory()
    # interleave: both sessions are open before either inserts
    ca = ac.claim(a, PortfolioFixed, key={"user_id": "u", "kind": "training", "run_id": None})
    a.commit()
    cb = ac.claim(b, PortfolioFixed, key={"user_id": "u", "kind": "training", "run_id": None})
    b.commit()
    assert (ca.created, cb.created) == (True, False)
    assert ca.row.id == cb.row.id
    assert _count(factory, PortfolioFixed) == 1


def test_claim_policies_cover_the_four_outcomes(factory):
    with factory() as s:
        first = ac.claim(s, Floor, key={"min_build": 7}, values={"note": "a"})
        assert first.created
        s.commit()
    with factory() as s:
        # skip: the row existing is the goal
        assert ac.claim(s, Floor, key={"min_build": 7}, values={"note": "b"}).or_skip().note == "a"
        # update: the loser applies its change to the existing row
        row = ac.claim(s, Floor, key={"min_build": 7}, values={"note": "b"}).or_update(lambda r: setattr(r, "note", "b"))
        assert row.note == "b"
        # raise
        with pytest.raises(ac.Collision):
            ac.claim(s, Floor, key={"min_build": 7}).or_raise()


# ---- 3. tripwire ------------------------------------------------------------------------


@pytest.fixture()
def tripwire():
    off = ac.install_tripwire(Base.metadata, mode="raise")
    yield
    off()


def test_tripwire_stops_a_naked_orm_insert_of_a_collidable_model(factory, tripwire):
    with factory() as s:
        s.add(Floor(min_build=1))
        with pytest.raises(ac.UnclaimedInsert):
            s.flush()


@pytest.mark.parametrize("how", ["core", "text", "bulk"])
def test_tripwire_sees_inserts_the_orm_never_saw(factory, tripwire, how):
    """No model inference to be taught: the driver boundary sees every API."""
    from sqlalchemy import insert

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
    seen: list[tuple] = []
    off = ac.install_tripwire(Base.metadata, mode="log", on_violation=lambda *a: seen.append(a))
    try:
        with factory() as s:
            s.add(Floor(min_build=11))
            s.commit()
    finally:
        off()
    assert seen and seen[0][0] == "floors"


# ---- 4. observer ------------------------------------------------------------------------


@pytest.fixture()
def observed():
    sink: list[dict] = []
    off = ac.install_observer(sink.append)
    yield sink
    off()


def _helper_read(s, user):            # the read hides inside a helper, as in sim_engine._load_portfolio_row
    return s.execute(select(Device).where(Device.device_user_id == user)).scalar_one_or_none()


def test_observer_finds_check_then_insert_through_a_helper_with_no_arbiter(factory, observed):
    with factory() as s:
        if _helper_read(s, "d1") is None:
            s.add(Device(device_user_id="d1"))
        s.commit()
    assert [(o["table"], o["status"]) for o in observed] == [("devices", "NO-ARBITER")]


def test_observer_reports_vacuous_null_key_as_no_arbiter(factory, observed):
    with factory() as s:
        row = s.execute(select(Portfolio).where(
            Portfolio.user_id == "u", Portfolio.kind == "training", Portfolio.run_id.is_(None))).scalar_one_or_none()
        if row is None:
            s.add(Portfolio(user_id="u"))
        s.commit()
    assert [(o["table"], o["status"]) for o in observed] == [("portfolios_bad", "VACUOUS")]


def test_observer_is_quiet_for_an_unrelated_read_then_insert(factory, observed):
    with factory() as s:
        s.execute(select(Log).where(Log.msg == "a")).scalar_one_or_none()
        s.add(Log(msg="b"))
        s.commit()
    assert observed == []


# ---- real threads ----------------------------------------------------------------------


def test_claim_under_eight_real_threads_yields_one_row_and_one_creator(factory):
    import threading

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
