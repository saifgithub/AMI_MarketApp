"""ISS001 prototype — the flush-chokepoint guard + declared-policy `put()` helper.

Self-contained proof of the mechanism proposed in SOLUTION.md, using synthetic
models that mirror the constraint kinds in `backend/app/db/models.py`:

  BadgeLike      composite UniqueConstraint            (→ SKIP class)
  DeviceLike     unique=True column                    (→ RE_READ_AND_UPDATE class)
  VersionedLike  composite unique on (user, version)   (→ RETRY_THEN_RAISE class)
  RefLike        natural primary key, no default       (→ SKIP class)
  AppendOnly     uuid4-defaulted PK, no uniques        (→ NOT collidable)
  AutoInc        integer autoincrement PK              (→ NOT collidable)

Run:
    backend/.venv/bin/python docs/dilemmas/ISS001_DB_INSERT_RACE/kimi-k2/prototype_guard.py

Exit 0 and "ALL CHECKS PASSED" = every claim below verified. No repo code is
imported; nothing outside this folder is touched.

The staged "race" uses the same deterministic mechanism as the shipped
DEF220 tests (`_BlindOnce`): the loser's pre-check SELECT is blinded once,
reproducing P15's read-to-commit gap without threads — threads are flaky-green
on this stack for the same reason the bug was invisible (0 races in 60 trials).
"""

from __future__ import annotations

import enum
import sys
import time
from typing import Any, Callable

from sqlalchemy import (
    Integer,
    String,
    UniqueConstraint,
    create_engine,
    event,
    insert,
    select,
)
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlalchemy.orm import Mapped, Session, declarative_base, mapped_column, sessionmaker

Base = declarative_base()
_uuid = lambda: __import__("uuid").uuid4().hex  # noqa: E731 — deterministic-free default


class BadgeLike(Base):
    __tablename__ = "badges"
    __table_args__ = (UniqueConstraint("user_id", "badge_key", name="uq_badge_user_key"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String)
    badge_key: Mapped[str] = mapped_column(String)


class DeviceLike(Base):
    __tablename__ = "devices"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    install_id: Mapped[str] = mapped_column(String, unique=True)
    owner: Mapped[str | None] = mapped_column(String, nullable=True)


class VersionedLike(Base):
    __tablename__ = "docs"
    __table_args__ = (UniqueConstraint("user_id", "version", name="uq_doc_user_version"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String)
    version: Mapped[int] = mapped_column(Integer)
    body: Mapped[str] = mapped_column(String)


class RefLike(Base):
    __tablename__ = "ref"
    symbol: Mapped[str] = mapped_column(String, primary_key=True)  # natural key, no default
    name: Mapped[str] = mapped_column(String)


class AppendOnly(Base):
    __tablename__ = "events"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    payload: Mapped[str] = mapped_column(String)


class AutoInc(Base):
    __tablename__ = "autoinc"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payload: Mapped[str] = mapped_column(String)


# ── errors ─────────────────────────────────────────────────────────────────────


class UnmanagedCollidableInsertError(RuntimeError):
    """A bare session.add() reached the flush for a model with unique keys."""


class CoreInsertBlockedError(RuntimeError):
    """A Core/bulk INSERT targeted a collidable table without an explicit opt-in."""


class CollisionConflictError(RuntimeError):
    """RETRY_THEN_RAISE exhausted its retry."""


# ── piece 1: schema-derived collidable registry ────────────────────────────────


def derive_collidable_table_keys(metadata) -> dict[str, list[tuple[str, ...]]]:
    """Every table whose INSERT can raise on a duplicate, with its key columns.

    UniqueConstraint, unique Index, unique=True column, or a primary key with no
    default (the natural-key case). A uuid4-defaulted or autoincrement PK cannot
    collide client-side and is excluded — the same rule the AST guard encodes,
    but derived from the schema itself, so it cannot drift from models.py and
    widens itself the day anyone adds a model.
    """
    out: dict[str, list[tuple[str, ...]]] = {}
    for table in metadata.tables.values():
        keys: set[tuple[str, ...]] = set()
        for c in table.constraints:
            if isinstance(c, UniqueConstraint):
                keys.add(tuple(sorted(col.name for col in c.columns)))
        for idx in table.indexes:
            if idx.unique:
                keys.add(tuple(sorted(col.name for col in idx.columns)))
        for col in table.columns:
            if col.unique:
                keys.add((col.name,))
        pk = list(table.primary_key.columns)
        natural_pk = (
            pk
            and all(c.default is None and c.server_default is None for c in pk)
            and not (
                len(pk) == 1
                and isinstance(pk[0].type, Integer)
                and pk[0].autoincrement in (True, "auto")
            )
        )
        if natural_pk:
            keys.add(tuple(sorted(c.name for c in pk)))
        if keys:
            out[table.name] = sorted(keys)
    return out


def collidable_classes(base, table_keys) -> dict[type, list[tuple[str, ...]]]:
    out = {}
    for m in base.registry.mappers:
        name = m.persist_selectable.name
        if name in table_keys:
            out[m.class_] = table_keys[name]
    return out


# ── piece 2: the flush-chokepoint guard ────────────────────────────────────────

_STAMP = "_ami_put_managed"
_CORE_OK = "ami_allow_core_collidable_insert"


def attach_guard(sm: sessionmaker, by_class: dict, table_names: set[str]) -> None:
    """One registration point. In the real backend this is three lines in
    `app/db/session.py:get_engine()` next to the only sessionmaker — which the
    test fixture also rebuilds, so the whole suite runs guarded for free."""

    @event.listens_for(sm, "before_flush")
    def _guard(session, flush_context, instances) -> None:
        for obj in session.new:
            keys = by_class.get(type(obj))
            if keys is None:
                continue
            if getattr(obj, _STAMP, False):
                delattr(obj, _STAMP)  # one stamp = one insert attempt
                continue
            raise UnmanagedCollidableInsertError(
                f"{type(obj).__name__} has unique keys {keys}; a bare session.add() "
                "into it is a check-then-INSERT race under two writers (P15). Go "
                f"through put(session, {type(obj).__name__}, key=..., on_collision=...) "
                "and declare the outcome."
            )

    @event.listens_for(sm, "do_orm_execute")
    def _block_core(orm_execute_state) -> None:
        if not orm_execute_state.is_insert:
            return
        session = orm_execute_state.session
        if session is not None and session.info.get(_CORE_OK):
            return
        table = getattr(orm_execute_state.statement, "table", None)
        if getattr(table, "name", None) in table_names:
            raise CoreInsertBlockedError(
                f"Core INSERT into collidable table {table.name!r}. Use put(), "
                f"or set session.info[{_CORE_OK!r}] = True in a reviewed script."
            )

    # Bulk APIs (`bulk_insert_mappings`, `bulk_save_objects`) are banned on
    # GuardedSession by METHOD OVERRIDE below, not by an event — measured on
    # 2.0.49: they fire no session event at all, and `after_bulk_insert` was
    # removed in 2.0. A lint rule would be grammar; an override is structural.


# ── piece 3: put() — one helper, four declared outcomes ────────────────────────


class OnCollision(enum.Enum):
    SKIP = "skip"                                  # row existing is the goal
    RE_READ_AND_UPDATE = "re_read_and_update"      # loser still applies a change
    RETRY_THEN_RAISE = "retry_then_raise"          # version sequences
    RAISE = "raise"                                # collision means something is wrong


def _by_key(Model, key: dict):
    return select(Model).where(*[getattr(Model, k) == v for k, v in key.items()])


def _drop_loser(session, failed) -> None:
    """Ensure the loser's INSERT is never re-attempted by a later flush/commit."""
    try:
        session.expunge(failed)
    except InvalidRequestError:
        pass  # already gone from the session — nothing to drop


def put(
    session,
    Model,
    *,
    key: dict[str, Any],
    values: dict[str, Any] | None = None,
    on_collision: OnCollision,                    # mandatory, no default: the policy IS the point
    on_update: Callable[[Any], None] | None = None,
    retry: Callable[[Any], tuple[dict, dict | None]] | None = None,
    conflict_error: Exception = CollisionConflictError("collision survived retry"),
):
    """Get-or-insert with a declared collision outcome, savepoint-wrapped so a
    lost race can never poison uncommitted work elsewhere in the transaction."""
    row = session.execute(_by_key(Model, key)).scalar_one_or_none()
    if row is not None:
        if on_collision is OnCollision.RE_READ_AND_UPDATE and on_update is not None:
            on_update(row)
        return row, False

    try:
        with session.begin_nested():
            row = Model(**{**key, **(values or {})})
            setattr(row, _STAMP, True)
            session.add(row)
            session.flush()
        return row, True
    except IntegrityError:
        _drop_loser(session, row)
        if on_collision is OnCollision.RAISE:
            raise conflict_error
        if on_collision is OnCollision.RETRY_THEN_RAISE:
            assert retry is not None, "RETRY_THEN_RAISE needs a retry(session) callable"
            key2, values2 = retry(session)
            try:
                with session.begin_nested():
                    row2 = Model(**{**key2, **(values2 or {})})
                    setattr(row2, _STAMP, True)
                    session.add(row2)
                    session.flush()
                return row2, True
            except IntegrityError:
                _drop_loser(session, row2)
                raise conflict_error
        won = session.execute(_by_key(Model, key)).scalar_one()
        if on_collision is OnCollision.RE_READ_AND_UPDATE and on_update is not None:
            on_update(won)
        return won, False


# ── test rig ───────────────────────────────────────────────────────────────────

_RESULTS: list[tuple[str, bool, str]] = []


def check(name: str):
    def deco(fn):
        try:
            fn()
            _RESULTS.append((name, True, ""))
        except Exception as e:  # the point of the run is which check failed
            _RESULTS.append((name, False, f"{type(e).__name__}: {e}"))
    return deco


class GuardedSession(Session):
    """The session class the guarded factory mints.

    Bulk APIs are overridden here because they are provably invisible to the
    event system (measured 2.0.49: no session event fires for either method).
    Overriding two named, grep-stable methods is a structural ban, not a
    grammar rule. Legitimate bulk paths (backfill scripts) opt in via
    `session.info["ami_allow_core_collidable_insert"] = True`.
    """

    def bulk_insert_mappings(self, *a, **k):
        if not self.info.get(_CORE_OK):
            raise CoreInsertBlockedError(
                "bulk_insert_mappings bypasses every session event (measured); "
                "banned on guarded sessions. Use put(), or opt in via "
                f"session.info[{_CORE_OK!r}] in a reviewed script."
            )
        return super().bulk_insert_mappings(*a, **k)

    def bulk_save_objects(self, *a, **k):
        if not self.info.get(_CORE_OK):
            raise CoreInsertBlockedError(
                "bulk_save_objects bypasses every session event (measured); "
                "banned on guarded sessions. Use put(), or opt in via "
                f"session.info[{_CORE_OK!r}] in a reviewed script."
            )
        return super().bulk_save_objects(*a, **k)


def make_factory(guarded: bool):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    cls = GuardedSession if guarded else None
    sm = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, **({"class_": cls} if cls else {}))
    if guarded:
        attach_guard(sm, COLLIDABLE_BY_CLASS, COLLIDABLE_TABLE_NAMES)
    return sm


TABLE_KEYS = derive_collidable_table_keys(Base.metadata)
COLLIDABLE_BY_CLASS = collidable_classes(Base, TABLE_KEYS)
COLLIDABLE_TABLE_NAMES = set(TABLE_KEYS)
G = make_factory(guarded=True)
UG = make_factory(guarded=False)  # the "before" picture: same code, no control


def s_count(session, Model, key: dict | None = None) -> int:
    stmt = _by_key(Model, key) if key else select(Model)
    return len(session.execute(stmt).scalars().all())


class BlindOnce:
    """DEF220's deterministic read-to-commit gap: the first pre-check SELECT
    reports nothing found; everything else delegates to the genuine session."""

    def __init__(self, session):
        self._s = session
        self._blinded = False

    def execute(self, *a, **k):
        if not self._blinded:
            self._blinded = True

            class _Empty:
                def scalar_one_or_none(self):
                    return None

            return _Empty()
        return self._s.execute(*a, **k)

    def __getattr__(self, name):
        return getattr(self._s, name)


def expect(exc_type, fn):
    try:
        fn()
    except exc_type:
        return
    raise AssertionError(f"expected {exc_type.__name__}, got none")


# ── checks ─────────────────────────────────────────────────────────────────────


@check("A. registry derived from schema == expected set (append-only/autoinc excluded)")
def _():
    assert set(COLLIDABLE_TABLE_NAMES) == {"badges", "devices", "docs", "ref"}, TABLE_KEYS
    assert set(COLLIDABLE_BY_CLASS) == {BadgeLike, DeviceLike, VersionedLike, RefLike}
    assert TABLE_KEYS["docs"] == [("user_id", "version")]
    assert TABLE_KEYS["devices"] == [("install_id",)]
    assert TABLE_KEYS["ref"] == [("symbol",)]


@check("B1. unmanaged insert blocked — inline add(Model(...))")
def _():
    s = G()
    expect(UnmanagedCollidableInsertError, lambda: (s.add(BadgeLike(user_id="u", badge_key="b")), s.flush()))
    s.rollback()


@check("B2. unmanaged insert blocked — row = Model(...); s.add(row)  [v3 grammar]")
def _():
    s = G()
    row = BadgeLike(user_id="u", badge_key="b")
    expect(UnmanagedCollidableInsertError, lambda: (s.add(row), s.flush()))
    s.rollback()


@check("B3. unmanaged insert blocked — built by a factory function  [no v4 grammar exists]")
def _():
    def make_badge():
        return BadgeLike(user_id="u", badge_key="b")

    s = G()
    expect(UnmanagedCollidableInsertError, lambda: (s.add(make_badge()), s.flush()))
    s.rollback()


@check("B4. unmanaged insert blocked — comprehension + add_all")
def _():
    s = G()
    rows = [BadgeLike(user_id="u", badge_key=f"b{i}") for i in range(3)]
    expect(UnmanagedCollidableInsertError, lambda: (s.add_all(rows), s.flush()))
    s.rollback()


@check("B5. unmanaged insert blocked at COMMIT, not only at explicit flush")
def _():
    s = G()
    s.add(DeviceLike(install_id="i1", owner="a"))
    expect(UnmanagedCollidableInsertError, s.commit)
    s.rollback()


@check("C. the bug, reproduced on the UNGUARDED factory: read-to-commit gap → IntegrityError")
def _():
    key = {"install_id": "dev-1"}
    winner = UG()
    loser = UG()
    # both pre-checks land before either commits
    assert loser.execute(_by_key(DeviceLike, key)).scalar_one_or_none() is None
    winner.add(DeviceLike(**key, owner="first"))
    winner.commit()
    loser.add(DeviceLike(**key, owner="second"))
    expect(IntegrityError, loser.flush)  # ← the 500 users would eat today
    loser.rollback()


@check("D. put() happy path: creates once, second call returns (row, False)")
def _():
    s = G()
    row, created = put(s, BadgeLike, key={"user_id": "u", "badge_key": "b"}, on_collision=OnCollision.SKIP)
    assert created and row.id
    again, created2 = put(s, BadgeLike, key={"user_id": "u", "badge_key": "b"}, on_collision=OnCollision.SKIP)
    assert not created2 and again.id == row.id
    s.commit()


@check("E. put(SKIP) loses the staged race: one row, loser gets the winner")
def _():
    key = {"user_id": "u", "badge_key": "race"}
    winner = G()
    loser = G()
    blind = BlindOnce(loser)
    put(winner, BadgeLike, key=key, on_collision=OnCollision.SKIP)
    winner.commit()
    row, created = put(blind, BadgeLike, key=key, on_collision=OnCollision.SKIP)
    assert not created
    loser.commit()  # loser's outer transaction still commits clean
    assert s_count(loser, BadgeLike, key) == 1


@check("F. put(RE_READ_AND_UPDATE): the loser still applies its change (device re-key analogue)")
def _():
    key = {"install_id": "dev-9"}
    winner = G()
    loser = G()
    blind = BlindOnce(loser)
    put(winner, DeviceLike, key=key, values={"owner": "anon"}, on_collision=OnCollision.RE_READ_AND_UPDATE)
    winner.commit()
    row, created = put(
        blind, DeviceLike, key=key, values={"owner": "claimed"},
        on_collision=OnCollision.RE_READ_AND_UPDATE,
        on_update=lambda r: setattr(r, "owner", "claimed"),
    )
    assert not created and row.owner == "claimed"
    loser.commit()
    check_s = G()
    assert check_s.execute(_by_key(DeviceLike, key)).scalar_one().owner == "claimed"


@check("G. put(RETRY_THEN_RAISE): version sequence lands loser at v+1; double collision raises named error")
def _():
    def next_version(session):
        top = session.execute(
            select(VersionedLike.version).where(VersionedLike.user_id == "u").order_by(VersionedLike.version.desc())
        ).scalars().first() or 0
        return {"user_id": "u", "version": top + 1}, {"body": "loser text"}

    winner = G()
    loser = G()
    blind = BlindOnce(loser)
    put(winner, VersionedLike, key={"user_id": "u", "version": 1}, values={"body": "v1"}, on_collision=OnCollision.SKIP)
    winner.commit()
    row, created = put(
        blind, VersionedLike, key={"user_id": "u", "version": 1}, values={"body": "loser text"},
        on_collision=OnCollision.RETRY_THEN_RAISE, retry=next_version,
    )
    assert created and row.version == 2
    loser.commit()

    # forced double collision: the retry's recomputed version is taken too
    class ConflictEx(CollisionConflictError):
        pass

    winner2 = G()
    loser2 = G()
    blind2 = BlindOnce(loser2)
    put(winner2, VersionedLike, key={"user_id": "u", "version": 3}, values={"body": "x"}, on_collision=OnCollision.SKIP)
    put(winner2, VersionedLike, key={"user_id": "u", "version": 4}, values={"body": "y"}, on_collision=OnCollision.SKIP)
    winner2.commit()

    def retry_into_wall(session):
        return {"user_id": "u", "version": 4}, {"body": "z"}  # stale recompute hits v4

    expect(
        ConflictEx,
        lambda: put(
            blind2, VersionedLike, key={"user_id": "u", "version": 3}, values={"body": "z"},
            on_collision=OnCollision.RETRY_THEN_RAISE, retry=retry_into_wall,
            conflict_error=ConflictEx("doc version conflict"),
        ),
    )
    loser2.rollback()


@check("H. put(RAISE): the domain error surfaces, not a raw IntegrityError (release-floor analogue)")
def _():
    class DuplicateFloorError(Exception):
        pass

    winner = G()
    put(winner, RefLike, key={"symbol": "AAPL"}, values={"name": "Apple"}, on_collision=OnCollision.SKIP)
    winner.commit()
    loser = G()
    blind = BlindOnce(loser)
    err = DuplicateFloorError("AAPL already floored")
    try:
        put(blind, RefLike, key={"symbol": "AAPL"}, values={"name": "Apple"},
            on_collision=OnCollision.RAISE, conflict_error=err)
        raise AssertionError("expected DuplicateFloorError")
    except DuplicateFloorError:
        pass
    loser.rollback()


@check("I. Core insert() into a collidable table is blocked; opt-in flag allows it; non-collidable Core insert untouched")
def _():
    s = G()
    expect(CoreInsertBlockedError, lambda: s.execute(insert(DeviceLike).values(install_id="x", owner="a")))
    s.rollback()
    s.info[_CORE_OK] = True
    s.execute(insert(DeviceLike).values(install_id="x", owner="a"))
    s.commit()
    s2 = G()
    s2.execute(insert(AppendOnly).values(payload="fine"))
    s2.commit()


@check("J. UPDATE of a persistent collidable row is not flagged (only session.new is checked)")
def _():
    s = G()
    row, _ = put(s, DeviceLike, key={"install_id": "upd"}, values={"owner": "a"}, on_collision=OnCollision.SKIP)
    s.commit()
    row.owner = "b"
    s.flush()
    s.commit()


@check("K. after put() recovery, the outer commit is clean — no lingering duplicate (savepoint placement is load-bearing)")
def _():
    s = G()
    row, _ = put(s, BadgeLike, key={"user_id": "u", "badge_key": "poison"}, on_collision=OnCollision.SKIP)
    s.flush()  # outer transaction now holds state worth protecting
    key = {"user_id": "u", "badge_key": "poison"}
    other = G()
    blind = BlindOnce(other)
    # other session loses the race against the row `s` has not committed yet is
    # impossible (invisible), so commit first — the staged gap is the blind:
    s.commit()
    r2, created = put(blind, BadgeLike, key=key, on_collision=OnCollision.SKIP)
    assert not created
    other.commit()  # would IntegrityError here if the loser's INSERT lingered pending
    assert s_count(other, BadgeLike, key) == 1


@check("L. overhead of the guard on ordinary inserts (append-only, unguarded vs guarded)")
def _():
    N = 3000

    def bench(sm):
        s = sm()
        t0 = time.perf_counter()
        for i in range(N):
            s.add(AppendOnly(payload=str(i)))
            s.flush()
        s.commit()
        return (time.perf_counter() - t0) / N

    base = bench(UG)
    guarded = bench(G)
    ratio = guarded / base if base else 0
    print(f"      per-insert+flush: unguarded {base*1e6:.1f}µs, guarded {guarded*1e6:.1f}µs, x{ratio:.2f}")
    assert ratio < 2.0


@check("M1. bulk_insert_mappings is banned structurally (method override — it fires no event), nothing lands")
def _():
    s = G()
    expect(CoreInsertBlockedError, lambda: s.bulk_insert_mappings(DeviceLike, [{"install_id": "bulk1", "owner": "a"}]))
    s.rollback()
    probe = G()
    assert probe.execute(_by_key(DeviceLike, {"install_id": "bulk1"})).scalar_one_or_none() is None


@check("M2. bulk_save_objects is banned the same way")
def _():
    s = G()
    expect(CoreInsertBlockedError, lambda: s.bulk_save_objects([DeviceLike(install_id="bulk2", owner="a")]))
    s.rollback()
    probe = G()
    assert probe.execute(_by_key(DeviceLike, {"install_id": "bulk2"})).scalar_one_or_none() is None


@check("M3. session.merge() — check-then-insert as an API — is caught when its insert arm hits a collidable model")
def _():
    s = G()
    expect(UnmanagedCollidableInsertError, lambda: (s.merge(DeviceLike(install_id="merged", owner="a")), s.flush()))
    s.rollback()


def main() -> int:
    print(f"collidable tables derived from schema: {sorted(COLLIDABLE_TABLE_NAMES)}")
    for name, ok, detail in _RESULTS:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        if not ok:
            print(f"        {detail}")
    failed = [n for n, ok, _ in _RESULTS if not ok]
    print("ALL CHECKS PASSED" if not failed else f"{len(failed)} CHECK(S) FAILED")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
