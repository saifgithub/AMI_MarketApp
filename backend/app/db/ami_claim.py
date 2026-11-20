"""ISS001 — `claim()`, the insert tripwire and the schema-truth check.

Why this exists. "SELECT to see whether a row exists, INSERT if absent" was written 21 times in
this backend despite a documented failure class (P15), an AST guard and two defects (DEF220,
DEF308). The AST guard checks that a handler *exists*; DEF499 (the 21st) had a unique constraint
whose nullable column made it vacuous, so a handler could never have run. The invariant is not
"handle IntegrityError": it is "a unique key the database really enforces for THIS row's values,
and an insert that goes through it atomically". Dilemma record and verdict:
`docs/dilemmas/ISS001_DB_INSERT_RACE/` (winner: sonnet5.5, plus kimi-k2's canaries).

Three parts, each answering a different question:

1. `schema_truth(metadata)`  Is every composite unique key real? Exact, from live metadata, no AST.
2. `claim(...)`             The sanctioned way to insert a row that can collide. Atomic
                            (INSERT .. ON CONFLICT DO NOTHING), refuses to run without an arbiter
                            that actually deduplicates this key (NULLs included), and makes the
                            caller choose what a collision means (skip / update / raise).
3. `install_tripwire(...)`  Hooks the driver boundary (`before_cursor_execute`). Every INSERT into
                            a collidable table, from ANY API (ORM, Core, text, bulk), must be
                            sanctioned or it is reported (log mode) / refused (raise mode). A
                            hand-written ON CONFLICT whose target matches no arbiter is reported
                            too.

Rollout (ISS001 Phase 1): the tripwire is installed on the app engine in
`app/db/session.py::get_engine`. Production runs `log`, the unit suite runs `raise`. Sites that
predate the control are pinned in `app/db/insert_baseline.py` (an owned list, not a silent
allowlist): a new unclaimed site fails the suite, a converted one must leave the list.

Install on the engine INSTANCE, never the `Engine` class, so alembic's own engine (data
migrations legitimately INSERT) is not policed.

What this does not see (named in the verdict, not hidden): an INSERT no test ever executes, a
business key with no constraint and no same-session read, raw driver writes (COPY, other roles),
and a wrong outcome choice. See VERDICT.md section 6.
"""

from __future__ import annotations

import contextvars
import os
import re
import sys
import threading
import weakref
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Generic, Iterable, Iterator, TypeVar

from sqlalchemy import Table, UniqueConstraint, event, select, text
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.logging import logger

T = TypeVar("T")

TRIPWIRE_MODES = ("off", "log", "raise")


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


def normalize_sql(sql: str) -> str:
    return re.sub(r"[\s\"`]+", " ", sql).strip().upper()


def arbiters(table: Table) -> list[Arbiter]:
    """Every uniqueness the DB will enforce on `table`: unique constraints, unique indexes
    (partial ones carry their predicate), single-column unique=True, and the primary key."""
    seen: dict[tuple, Arbiter] = {}

    def add(name: str | None, cols: list[str], where: str | None) -> None:
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
            w = normalize_sql(arb.where)
            if all(f"{c.upper()} IS NULL" in w for c in null_cols):
                return arb
    return None


# --------------------------------------------------------------------------- 1. schema truth


def schema_truth(metadata) -> list[str]:
    """Findings for composite unique keys that do not mean what their name says.

    A composite unique key with a nullable column silently stops deduplicating for rows where
    that column is NULL. `Column.info["null_means_no_key"] = "<why>"` is the declaration that the
    NULL rows are intentionally exempt; a partial index whose predicate says `<col> IS NOT NULL`
    is the same declaration made in DDL. Anything else is a finding. Single-column nullable
    unique keys (email, phone) are exempt by construction: NULL there means "no value".

    A finding is silenced only by a *different* object the database enforces: a partial unique
    index over the remaining columns `WHERE <col> IS NULL` covers the NULL rows (DEF499), so the
    full constraint's nullable column stops being vacuous for the NULL case.
    """
    out: list[str] = []
    for t in metadata.tables.values():
        for arb in arbiters(t):
            if arb.name == "PRIMARY" or len(arb.columns) < 2:
                continue
            for c in arb.columns:
                col = t.c[c]
                if not col.nullable:
                    continue
                if arb.where and f"{c.upper()} IS NOT NULL" in normalize_sql(arb.where):
                    continue
                if col.info.get("null_means_no_key"):
                    continue
                if _null_case_covered(t, arb, c):
                    continue
                out.append(f"{t.name}.{arb.name or arb.columns}: nullable `{c}` — rows with {c} IS NULL are not deduplicated")
    return out


def _null_case_covered(table: Table, arb: Arbiter, null_col: str) -> bool:
    """True when a partial unique index over the other columns enforces uniqueness for the rows
    where `null_col IS NULL` — the DEF499 shape."""
    others = set(arb.columns) - {null_col}
    for other in arbiters(table):
        if other is arb or not other.where:
            continue
        if set(other.columns) == others and f"{null_col.upper()} IS NULL" in normalize_sql(other.where):
            return True
    return False


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
    """The ONE in-code escape hatch. A site that handles its own collision (retry-then-raise
    version sequences, a fresh-uuid mint) says so here, with a reason. Usages are counted by a
    test (a literal grep, not an inference) and each must carry a non-empty `why`."""
    if not why.strip():
        raise ValueError("unclaimed() needs a reason")
    with _sanction(model.__table__.name):  # type: ignore[attr-defined]
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
    first, happy-path execution, not on a race that may never come. The caller must pick an
    outcome (`.or_skip()` / `.or_update(fn)` / `.or_raise(exc)`); there is no default.
    """
    table: Table = model.__table__  # type: ignore[attr-defined]
    arb = _effective_arbiter(table, key)
    if arb is None:
        have = [(a.name, a.columns, a.where) for a in arbiters(table)]
        raise NoArbiter(f"{table.name}: nothing enforces uniqueness of {key.keys()} for this key. Arbiters: {have}")

    ins = _dialect_insert(session)(table).values(**{**key, **(values or {})})
    kw: dict[str, Any] = {"index_elements": list(arb.columns)}
    if arb.where:
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
_ON_CONFLICT_RE = re.compile(r"\bON\s+CONFLICT\b", re.I)
_ON_CONSTRAINT_RE = re.compile(r"\bON\s+CONFLICT\s+ON\s+CONSTRAINT\s+[\"`]?(\w+)[\"`]?", re.I)

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_APP_PREFIX = _APP_DIR + os.sep
_DB_PREFIX = os.path.join(_APP_DIR, "db") + os.sep


@dataclass(frozen=True)
class Violation:
    table: str
    reason: str  # "unclaimed" | "conflict-target" | "unparseable"
    statement: str
    stack: tuple[str, ...]  # outermost-first, innermost application frames
    site: str  # innermost app frame as "<path under app/>::<function>", or "<non-app>"


_sinks: list[Callable[[Violation, bool], None]] = []
_installed: "weakref.WeakKeyDictionary[Engine, Callable]" = weakref.WeakKeyDictionary()


def add_violation_sink(fn: Callable[[Violation, bool], None]) -> Callable[[], None]:
    """Register `fn(violation, baselined)`, called for every violation the tripwire sees in any
    mode (the opt-in observer report uses it). Returns the remover."""
    _sinks.append(fn)
    return lambda: _sinks.remove(fn)


def app_frames(n: int, *, skip: int = 1) -> list[tuple[str, int, str]]:
    """Innermost `n` application frames (excluding `app/db/`) as (path under app/, line, function),
    outermost-first. Uses sys._getframe — no linecache I/O (traceback.extract_stack made the
    suite ~4x slower)."""
    out: list[tuple[str, int, str]] = []
    f = sys._getframe(skip)
    while f is not None and len(out) < n:
        fn = f.f_code.co_filename
        if fn.startswith(_APP_PREFIX) and not fn.startswith(_DB_PREFIX):
            out.append((fn[len(_APP_PREFIX):], f.f_lineno, f.f_code.co_name))
        f = f.f_back
    return out[::-1]


def _split_top(s: str) -> list[str]:
    parts, depth, cur = [], 0, []
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur).strip())
    return parts


def _conflict_target_ok(statement: str, table: Table) -> bool:
    """A hand-written ON CONFLICT is trusted only when its target is an arbiter of the table.

    `ON CONFLICT DO NOTHING` with no target matches any arbiter and is accepted. A target that is
    not a plain column list (an expression index) cannot be verified here and fails closed.
    """
    m = _ON_CONSTRAINT_RE.search(statement)
    if m:
        return m.group(1).lower() in {(a.name or "").lower() for a in arbiters(table)}
    m = _ON_CONFLICT_RE.search(statement)
    assert m
    rest = statement[m.end():].lstrip()
    if not rest.startswith("("):
        return True
    depth, end = 0, None
    for i, ch in enumerate(rest):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end is None:
        return False
    cols = [c.strip().strip('"`').lower() for c in _split_top(rest[1:end])]
    if not all(re.fullmatch(r"\w+", c) for c in cols):
        return False
    tail = normalize_sql(rest[end + 1:end + 200])
    has_where = tail.startswith("WHERE")
    for arb in arbiters(table):
        if {c.lower() for c in arb.columns} == set(cols) and bool(arb.where) == has_where:
            return True
    return False


def install_tripwire(
    metadata,
    *,
    engine: Engine,
    mode: str = "raise",
    baseline: Iterable[tuple[str, str]] | dict[tuple[str, str], str] = (),
    on_violation: Callable[[Violation], None] | None = None,
    app_frames_only: bool = False,
) -> Callable[[], None]:
    """Hook the driver boundary of `engine` (an instance). Returns an uninstall function.

    Every INSERT from every API funnels through before_cursor_execute, so there is no model-
    inference step to be taught a new construction. An INSERT that parses to no table fails
    CLOSED (reported with table '?').

    Allowed: table not collidable; statement has an ON CONFLICT whose target is an arbiter; table
    sanctioned by claim()/unclaimed(). A violation at a `baseline` site, a (table, site) pair
    from `app.db.insert_baseline`, is reported but never raised; anything else raises in `raise`
    mode and is logged at ERROR in `log` mode.

    `app_frames_only` skips statements with no frame under `app/` — test fixtures seeding rows
    directly, not application code.
    """
    if mode not in ("log", "raise"):
        raise ValueError(f"install_tripwire mode must be 'log' or 'raise', got {mode!r}")
    pinned = frozenset(baseline)
    state: dict[str, Any] = {"coll": None, "tables": None}
    announced: set[tuple[str, str, str]] = set()
    lock = threading.Lock()

    def _collidable() -> tuple[set[str], dict[str, Table]]:
        if state["coll"] is None:
            import app.db.models  # noqa: F401  (register every mapped table)

            with lock:
                state["coll"] = collidable_tables(metadata)
                state["tables"] = {t.name: t for t in metadata.tables.values()}
        return state["coll"], state["tables"]

    def handler(conn, cursor, statement, parameters, context, executemany):
        head = statement[:24].lstrip().upper()
        if not head.startswith(("INSERT", "WITH")):
            return                      # the 99% path: one slice + one startswith
        up = statement.upper()
        if head.startswith("WITH") and " INSERT " not in up:
            return
        m = _INSERT_RE.search(statement)
        table = m.group(1) if m else "?"
        coll, tables = _collidable()
        if m and table not in coll:
            return
        if table in _scope.get():
            return
        reason = "unclaimed"
        if _ON_CONFLICT_RE.search(statement):
            if table in tables and _conflict_target_ok(statement, tables[table]):
                return
            reason = "conflict-target" if table in tables else "unparseable"
        elif not m:
            reason = "unparseable"
        frames = app_frames(3, skip=2)
        if app_frames_only and not frames:
            return
        stack = tuple(f"{p}:{ln} {fn}" for p, ln, fn in frames)
        site = f"{frames[-1][0]}::{frames[-1][2]}" if frames else "<non-app>"
        v = Violation(table, reason, statement[:160], stack, site)
        baselined = (table, site) in pinned
        for sink in tuple(_sinks):
            sink(v, baselined)
        if on_violation:
            on_violation(v)
        if mode == "raise":
            if baselined:
                return
            raise UnclaimedInsert(
                f"INSERT INTO {table} ({reason}): no declared collision behaviour. Use claim(...) "
                f"(.or_skip/.or_update/.or_raise) or unclaimed(Model, why=...). Site: {list(stack)}"
            )
        mark = (table, site, reason)
        if mark in announced:
            return
        announced.add(mark)
        if baselined:
            logger.warning("unclaimed_insert_baselined", table=table, site=site, reason=reason)
        else:
            logger.error("unclaimed_insert", table=table, site=site, reason=reason, frames=list(stack))

    event.listen(engine, "before_cursor_execute", handler)
    _installed[engine] = handler

    def uninstall() -> None:
        event.remove(engine, "before_cursor_execute", handler)
        _installed.pop(engine, None)

    return uninstall


def tripwire_installed(engine: Engine) -> bool:
    """True when the handler `install_tripwire` registered is still listening on `engine`."""
    handler = _installed.get(engine)
    return handler is not None and event.contains(engine, "before_cursor_execute", handler)
