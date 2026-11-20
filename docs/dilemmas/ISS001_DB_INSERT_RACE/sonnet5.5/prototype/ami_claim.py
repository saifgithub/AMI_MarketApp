"""ISS001 prototype — `claim()`, the insert tripwire, the schema-truth check and the
check-then-insert observer, in one importable file.

Self-contained: depends only on SQLAlchemy 2.x. Nothing under backend/ imports it; the
demo (demo_race.py), the tests (test_prototype.py) and the suite-wide dry run
(observe_plugin.py) import it from this folder. If adopted, it becomes
`backend/app/db/claim.py` and the tripwire is installed in `app/db/session.py::get_engine`.

Four parts, each answering a different question:

1. schema_truth(metadata)   Is every unique key REAL?  (exact, introspected, no AST)
2. claim(...)               The one sanctioned way to insert a row that can collide.
                            Atomic (INSERT .. ON CONFLICT DO NOTHING), refuses to run without an
                            effective arbiter, makes the caller choose what a collision means.
3. install_tripwire(...)    Every INSERT into a collidable table, from ANY API (ORM, Core, text),
                            must be sanctioned or it raises (tests) / logs (prod).
4. install_observer(...)    TEST-ONLY. Watches reads and flushes; reports a SELECT-by-key followed
                            by an INSERT of that key, whatever helper the read hid inside.
"""

from __future__ import annotations

import contextvars
import re
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Generic, Iterator, TypeVar

from sqlalchemy import Table, UniqueConstraint, event, inspect, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.sql import operators
from sqlalchemy.sql.elements import BinaryExpression, BindParameter, BooleanClauseList, Null

T = TypeVar("T")


class NoArbiter(RuntimeError):
    """claim() was asked to arbitrate on a key the database does not enforce."""


class UnclaimedInsert(RuntimeError):
    """An INSERT into a collidable table that nobody declared a collision behaviour for."""


class Collision(RuntimeError):
    """Default exception for `.or_raise()`."""


class ClaimVanished(RuntimeError):
    """The conflicting row disappeared between the conflict and the re-read, twice."""


# --------------------------------------------------------------------------- arbiters


@dataclass(frozen=True)
class Arbiter:
    name: str | None
    columns: tuple[str, ...]
    where: str | None  # partial-index predicate text, if any


def _norm(sql: str) -> str:
    return re.sub(r"[\s\"`]+", " ", sql).strip().upper()


def arbiters(table: Table) -> list[Arbiter]:
    """Every uniqueness the DB will enforce on `table`: unique constraints, unique indexes
    (partial ones carry their predicate), single-column unique=True, and the primary key."""
    seen: dict[tuple, Arbiter] = {}

    def add(name, cols, where):
        seen.setdefault((tuple(sorted(cols)), where), Arbiter(name, tuple(cols), where))

    for c in table.constraints:
        if isinstance(c, UniqueConstraint):
            add(c.name, [x.name for x in c.columns], None)
    for i in table.indexes:
        if i.unique:
            where = None
            for dialect in ("postgresql", "sqlite"):
                w = i.dialect_options[dialect]["where"]
                if w is not None:
                    where = str(w)
                    break
            add(i.name, [x.name for x in i.columns], where)
    for col in table.columns:
        if col.unique:
            add(None, [col.name], None)
    pk = [c.name for c in table.primary_key.columns]
    if pk:
        add("PRIMARY", pk, None)
    return list(seen.values())


def _is_collidable(table: Table) -> bool:
    """A table can collide if it has any arbiter other than a defaulted surrogate PK."""
    for arb in arbiters(table):
        if arb.name == "PRIMARY":
            if any(table.c[c].default is None and table.c[c].server_default is None for c in arb.columns):
                return True
            continue
        return True
    return False


def collidable_tables(metadata) -> set[str]:
    return {t.name for t in metadata.tables.values() if _is_collidable(t)}


def _effective_arbiter(table: Table, key: dict[str, Any]) -> Arbiter | None:
    """The arbiter that actually deduplicates THIS key, or None.

    A unique key over a nullable column does not constrain rows where that column is NULL
    (Postgres < 15 default, SQLite always). So a key containing None is only arbitrated by a
    PARTIAL unique index over the non-None columns whose predicate says `<col> IS NULL`."""
    non_null = {k for k, v in key.items() if v is not None}
    null_cols = set(key) - non_null
    for arb in arbiters(table):
        cols = set(arb.columns)
        if not null_cols and cols == set(key):
            return arb
        if null_cols and arb.where and cols == non_null:
            w = _norm(arb.where)
            if all(f"{c.upper()} IS NULL" in w for c in null_cols):
                return arb
    return None


# --------------------------------------------------------------------------- 1. schema truth


def schema_truth(metadata) -> list[str]:
    """Findings for unique keys that do not mean what their name says.

    A composite unique key with a nullable column silently stops deduplicating for rows where
    that column is NULL. `Column.info["null_means_no_key"] = "<why>"` is the declaration that the
    NULL rows are intentionally exempt; anything else is a finding. Single-column nullable unique
    keys (email, phone) are exempt by construction: NULL there means "no value"."""
    out: list[str] = []
    for t in metadata.tables.values():
        for arb in arbiters(t):
            if arb.name == "PRIMARY" or len(arb.columns) < 2:
                continue
            for c in arb.columns:
                col = t.c[c]
                if not col.nullable:
                    continue
                if arb.where and f"{c.upper()} IS NOT NULL" in _norm(arb.where):
                    continue
                if col.info.get("null_means_no_key"):
                    continue
                out.append(f"{t.name}.{arb.name or arb.columns}: nullable `{c}` — rows with {c} IS NULL are not deduplicated")
    return out


# --------------------------------------------------------------------------- 2. claim

_scope: contextvars.ContextVar[frozenset[str]] = contextvars.ContextVar("ami_claim_scope", default=frozenset())


@contextmanager
def _sanction(table: str) -> Iterator[None]:
    tok = _scope.set(_scope.get() | {table})
    try:
        yield
    finally:
        _scope.reset(tok)


@contextmanager
def unclaimed(model: type, *, why: str) -> Iterator[None]:
    """The ONE escape hatch. A site that handles its own collision (retry-then-raise version
    sequences) says so here, with a reason. Usages are counted by a test (a literal grep, not an
    inference) and each must carry a non-empty `why`."""
    if not why.strip():
        raise ValueError("unclaimed() needs a reason")
    with _sanction(model.__table__.name):
        yield


@dataclass
class Claimed(Generic[T]):
    row: T
    created: bool

    def or_skip(self) -> T:
        """The row existing IS the goal (badge, cache)."""
        return self.row

    def or_update(self, apply: Callable[[T], None]) -> T:
        """The loser still has a change to apply (device re-key, edit counter)."""
        if not self.created:
            apply(self.row)
        return self.row

    def or_raise(self, exc: BaseException | None = None) -> T:
        """A collision means something is genuinely wrong, or the caller wants a 409."""
        if not self.created:
            raise exc if exc is not None else Collision("row already existed")
        return self.row


def _dialect_insert(session: Session):
    name = session.get_bind().dialect.name
    if name == "postgresql":
        return postgresql.insert
    if name == "sqlite":
        return sqlite.insert
    raise NotImplementedError(f"claim() has no INSERT..ON CONFLICT for dialect {name!r}")


def claim(session: Session, model: type[T], *, key: dict[str, Any], values: dict[str, Any] | None = None) -> Claimed[T]:
    """Insert `{**key, **values}` unless a row with `key` exists; return it either way.

    `key` is {column: value}. It is validated against the live metadata on EVERY call: if no
    unique arbiter deduplicates exactly this key (including its NULLs), raises NoArbiter — on the
    first, happy-path execution, not on a race that may never come.
    """
    table: Table = model.__table__  # type: ignore[attr-defined]
    arb = _effective_arbiter(table, key)
    if arb is None:
        have = [(a.name, a.columns, a.where) for a in arbiters(table)]
        raise NoArbiter(f"{table.name}: nothing enforces uniqueness of {key.keys()} for this key. Arbiters: {have}")

    ins = _dialect_insert(session)(table).values(**{**key, **(values or {})})
    kw: dict[str, Any] = {"index_elements": list(arb.columns)}
    if arb.where:
        from sqlalchemy import text

        kw["index_where"] = text(arb.where)
    pk_cols = list(table.primary_key.columns)
    stmt = ins.on_conflict_do_nothing(**kw).returning(*pk_cols)

    with _sanction(table.name):
        got = session.execute(stmt).first()
    if got is not None:
        return Claimed(session.get(model, tuple(got) if len(got) > 1 else got[0]), True)

    for _ in range(2):  # the conflicting row can be deleted between conflict and re-read
        cond = [(getattr(model, c).is_(None) if v is None else getattr(model, c) == v) for c, v in key.items()]
        row = session.execute(select(model).where(*cond)).scalars().first()
        if row is not None:
            return Claimed(row, False)
    raise ClaimVanished(f"{table.name} {key}")


# --------------------------------------------------------------------------- 3. tripwire

_INSERT_RE = re.compile(r"\bINSERT\s+(?:OR\s+\w+\s+)?INTO\s+[\"`]?([\w.]+)[\"`]?", re.I)


def _app_frames(n: int) -> list[str]:
    """Innermost `n` frames under /app/ (excluding /db/), via sys._getframe — no linecache I/O,
    which made a first version (traceback.extract_stack) 4x slower over the whole suite."""
    out: list[str] = []
    f = sys._getframe(2)
    while f is not None and len(out) < n:
        fn = f.f_code.co_filename
        if "/app/" in fn and "/db/" not in fn:
            out.append(f"{fn.split('/backend/')[-1]}:{f.f_lineno} {f.f_code.co_name}")
        f = f.f_back
    return out[::-1]


def install_tripwire(
    metadata, *, mode: str = "raise", on_violation: Callable[[str, str, list[str]], None] | None = None,
    engine: type[Engine] | Engine = Engine, app_frames_only: bool = False,
) -> Callable[[], None]:
    """Hook the driver boundary. Returns an uninstall function.

    Every INSERT from every API funnels through before_cursor_execute, so there is no model-
    inference step to be taught a new construction. A statement that begins like an INSERT but
    whose table cannot be parsed fails CLOSED (reported with table '?').

    Allowed: table not collidable; statement has ON CONFLICT; table sanctioned by claim()/unclaimed().
    Install on the APP engine INSTANCE (`engine=`), not the Engine class, so alembic's own
    engine (data migrations legitimately INSERT) is not policed.
    """
    coll = collidable_tables(metadata)

    def handler(conn, cursor, statement, parameters, context, executemany):
        head = statement[:24].lstrip().upper()
        if not head.startswith(("INSERT", "WITH")):
            return                      # the 99% path: one slice + one startswith
        up = statement.upper()
        if head.startswith("WITH") and " INSERT " not in up:
            return
        m = _INSERT_RE.search(statement)
        table = m.group(1) if m else "?"
        if m and table not in coll:
            return
        if " ON CONFLICT" in up or table in _scope.get():
            return
        stack = _app_frames(3)
        if app_frames_only and not stack:
            return          # a test fixture seeding rows directly, not application code
        if on_violation:
            on_violation(table, statement[:120], stack)
        if mode == "raise":
            raise UnclaimedInsert(
                f"INSERT INTO {table} with no declared collision behaviour. Use claim(...) "
                f"(.or_skip/.or_update/.or_raise) or unclaimed(Model, why=...). Site: {stack}"
            )

    event.listen(engine, "before_cursor_execute", handler)
    return lambda: event.remove(engine, "before_cursor_execute", handler)


# --------------------------------------------------------------------------- 4. observer (test-only)


def _eq_preds(clause) -> dict[tuple[str, str], Any]:
    out: dict[tuple[str, str], Any] = {}
    if clause is None:
        return out
    if isinstance(clause, BooleanClauseList) and clause.operator is operators.and_:
        for c in clause.clauses:
            out.update(_eq_preds(c))
    elif isinstance(clause, BinaryExpression) and clause.operator in (operators.eq, operators.is_):
        left, right = clause.left, clause.right
        tbl = getattr(left, "table", None)
        if tbl is not None and hasattr(left, "name"):
            if isinstance(right, BindParameter):
                out[(tbl.name, left.name)] = right.value
            elif isinstance(right, Null):
                out[(tbl.name, left.name)] = None
    return out


def _real_arbiters(table: Table) -> list[Arbiter]:
    return [a for a in arbiters(table)
            if not (a.name == "PRIMARY" and all(table.c[c].default is not None or table.c[c].server_default is not None
                                                  for c in a.columns))]


def _classify(table: Table, cols: dict[str, Any]) -> tuple[str, Arbiter | None]:
    """How well does a unique key back a read-by-`cols`?  covered | VACUOUS | PARTIAL-KEY | NO-ARBITER."""
    real = _real_arbiters(table)
    vacuous = False
    for a in real:
        if not set(a.columns) <= set(cols):
            continue
        extra = [c for c in cols if c not in a.columns]
        if a.where:
            w = _norm(a.where)
            if all(cols[c] is None and f"{c.upper()} IS NULL" in w for c in extra):
                return "covered", a
        elif all(cols[c] is not None for c in a.columns if table.c[c].nullable):
            return "covered", a
        else:
            vacuous = True
    if vacuous:
        return "VACUOUS", None
    return ("PARTIAL-KEY" if real else "NO-ARBITER"), None


def install_observer(sink: Callable[[dict], None]) -> Callable[[], None]:
    """Report every (table, columns) that a session SELECTed by equality and then INSERTed with
    the same values — the shape P15 describes — regardless of how many helpers the read hides in.

    Test-only: it keeps a per-session read log and walks stacks. `status` is "arbiter" when an
    effective unique key covers (a subset of) those columns, "NO-ARBITER" when nothing does."""

    def on_exec(state):
        if not state.is_select:
            return
        stmt = state.statement
        try:
            preds = _eq_preds(stmt.whereclause)
        except Exception:
            return
        by_table: dict[str, dict[str, Any]] = {}
        for (t, c), v in preds.items():
            by_table.setdefault(t, {})[c] = v
        log = state.session.info.setdefault("_obs_reads", [])
        for t, cols in by_table.items():
            log.append((t, cols))

    def on_attach(session, instance):
        site = _app_frames(1)
        session.info.setdefault("_obs_sites", {})[id(instance)] = site

    def on_flush(session, ctx, instances):
        reads = session.info.get("_obs_reads", [])
        if not reads:
            return
        for obj in list(session.new):
            mapper = inspect(obj).mapper
            table = mapper.local_table
            for t, cols in reads:
                if t != table.name or not cols:
                    continue
                vals = {}
                ok = True
                for c in cols:
                    prop = mapper.get_property_by_column(table.c[c]) if c in table.c else None
                    if prop is None:
                        ok = False
                        break
                    v = getattr(obj, prop.key, None)
                    dflt = table.c[c].default
                    if v is None and dflt is not None and dflt.is_scalar:
                        v = dflt.arg
                    vals[c] = v
                if not ok or any(vals[c] != cols[c] for c in cols):
                    continue
                status, effective = _classify(table, cols)
                sink({
                    "table": table.name,
                    "cols": sorted(cols),
                    "status": status,
                    "arbiter": effective.name if effective else None,
                    "site": (session.info.get("_obs_sites", {}).get(id(obj)) or ["?"])[0],
                })

    event.listen(Session, "do_orm_execute", on_exec)
    event.listen(Session, "after_attach", on_attach)
    event.listen(Session, "before_flush", on_flush)

    def uninstall():
        event.remove(Session, "do_orm_execute", on_exec)
        event.remove(Session, "after_attach", on_attach)
        event.remove(Session, "before_flush", on_flush)

    return uninstall
