"""ISS001 — the opt-in check-then-insert observer (`tests/iss001_observer.py`).

The observer is a report, not a control: it finds a SELECT-by-key followed by an INSERT of that
key whatever helper the read hid inside, and classifies how well a unique key backs it. Only
`VACUOUS` gates (and only with ISS001_GATE=1). These tests pin its verdicts and the property
opus5.0 warned about: a verdict that depends on which branch ran first is worse than an
incomplete one, so statuses aggregate by worst severity.
"""

from __future__ import annotations

import itertools
import uuid
from typing import Optional

import pytest
from sqlalchemy import Index, String, UniqueConstraint, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from tests import iss001_observer as obs


class Base(DeclarativeBase):
    pass


class Portfolio(Base):
    __tablename__ = "obs_portfolios_bad"
    __table_args__ = (UniqueConstraint("user_id", "kind", "run_id", name="uq_obs_bad"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String, default="training")
    run_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class Device(Base):
    __tablename__ = "obs_devices"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    device_user_id: Mapped[str] = mapped_column(String, index=True)


class Handle(Base):
    __tablename__ = "obs_handles"
    __table_args__ = (Index("uq_obs_h", "handle", unique=True),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    handle: Mapped[str] = mapped_column(String)


class Log(Base):
    __tablename__ = "obs_logs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    msg: Mapped[str] = mapped_column(String)


@pytest.fixture()
def factory(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path/'o.db'}")
    Base.metadata.create_all(eng)
    return sessionmaker(eng, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def observed():
    sink: list[dict] = []
    off = obs.install_observer(sink.append)
    yield sink
    off()


def _helper_read(s, user):          # the read hides inside a helper, as in sim_engine._load_portfolio_row
    return s.execute(select(Device).where(Device.device_user_id == user)).scalar_one_or_none()


def test_observer_finds_check_then_insert_through_a_helper_with_no_arbiter(factory, observed):
    with factory() as s:
        if _helper_read(s, "d1") is None:
            s.add(Device(device_user_id="d1"))
        s.commit()
    assert [(o["table"], o["status"]) for o in observed] == [("obs_devices", "NO-ARBITER")]


def test_observer_reports_vacuous_null_key(factory, observed):
    with factory() as s:
        row = s.execute(select(Portfolio).where(
            Portfolio.user_id == "u", Portfolio.kind == "training", Portfolio.run_id.is_(None))).scalar_one_or_none()
        if row is None:
            s.add(Portfolio(user_id="u"))
        s.commit()
    assert [(o["table"], o["status"]) for o in observed] == [("obs_portfolios_bad", "VACUOUS")]


def test_observer_calls_a_real_unique_key_covered(factory, observed):
    with factory() as s:
        if s.execute(select(Handle).where(Handle.handle == "h")).scalar_one_or_none() is None:
            s.add(Handle(handle="h"))
        s.commit()
    assert [(o["table"], o["status"]) for o in observed] == [("obs_handles", "covered")]


def test_observer_is_quiet_for_an_unrelated_read_then_insert(factory, observed):
    with factory() as s:
        s.execute(select(Log).where(Log.msg == "a")).scalar_one_or_none()
        s.add(Log(msg="b"))
        s.commit()
    assert observed == []


def test_aggregate_verdict_is_the_worst_status_whatever_the_order():
    """The same site reached on a covered branch and a VACUOUS branch reports VACUOUS in either order."""
    a = {"table": "t", "site": "s::f", "status": "covered", "cols": ["a"], "hits": 3}
    b = {"table": "t", "site": "s::f", "status": "VACUOUS", "cols": ["a", "b"], "hits": 1}
    c = {"table": "t", "site": "s::f", "status": "PARTIAL-KEY", "cols": ["a"], "hits": 2}
    verdicts = {tuple(sorted((r["status"], r["hits"], tuple(r["cols"])) for r in obs.aggregate(list(p))))
                for p in itertools.permutations([a, b, c])}
    assert len(verdicts) == 1
    only = obs.aggregate([a, b, c])
    assert [(r["status"], r["hits"]) for r in only] == [("VACUOUS", 6)]


def test_aggregate_keeps_distinct_sites_apart():
    rows = obs.aggregate([
        {"table": "t", "site": "x::f", "status": "covered", "cols": ["a"], "hits": 1},
        {"table": "t", "site": "y::g", "status": "NO-ARBITER", "cols": ["a"], "hits": 1},
    ])
    assert {(r["site"], r["status"]) for r in rows} == {("x::f", "covered"), ("y::g", "NO-ARBITER")}
