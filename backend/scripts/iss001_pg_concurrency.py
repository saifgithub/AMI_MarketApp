"""ISS001 acceptance item 6 — `claim()` under real threads against real Postgres.

Why this exists. The `claim()` guard (`app/db/ami_claim.py`) was proved on sqlite only. Its
Postgres-specific parts are unmeasured: partial-index `ON CONFLICT` inference (the DEF499 NULL-key
shape), the READ COMMITTED re-read after a lost race, and a true multi-connection race. VERDICT.md
section 6.7 makes this run a gate before Phase 3 converts any production path.

Safety contract. Everything happens inside ONE throwaway schema `iss001_test_<random>`: every
pooled connection pins `search_path` to that schema alone, the tables are created there, and the
schema is dropped CASCADE in a `finally`. No application table is read, altered or written. The
final check verifies no `iss001_test_%` schema remains.

Run (inside the API container, so DATABASE_URL and packages are the real ones):
    docker cp backend/scripts/iss001_pg_concurrency.py ami_api_alpha:/tmp/
    docker cp backend/app/db/ami_claim.py ami_api_alpha:/tmp/
    docker exec -w /app ami_api_alpha python /tmp/iss001_pg_concurrency.py
`ami_claim.py` is loaded from /tmp when present (the code under test, whatever the image shipped),
else from `app.db.ami_claim`. DATABASE_URL is never printed.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import secrets
import sys
import threading
import uuid
from collections import Counter
from typing import Optional

from sqlalchemy import (
    Index, String, UniqueConstraint, create_engine, event, func, select, text,
)
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

THREADS = 8
ROUNDS = 15


def _load_claim():
    path = "/tmp/ami_claim.py"
    if os.path.exists(path):
        spec = importlib.util.spec_from_file_location("ami_claim_under_test", path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["ami_claim_under_test"] = mod
        spec.loader.exec_module(mod)
        return mod, path
    from app.db import ami_claim as mod  # type: ignore

    return mod, "app.db.ami_claim"


ac, AC_SOURCE = _load_claim()


class Base(DeclarativeBase):
    pass


class Plain(Base):
    """Plain NOT NULL unique key (the client_release_floor shape)."""

    __tablename__ = "t_plain"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    k: Mapped[str] = mapped_column(String, unique=True)
    n: Mapped[int] = mapped_column(default=0)


class NullKey(Base):
    """DEF499 shape: unique (user, kind, run_id) with nullable run_id + partial unique index."""

    __tablename__ = "t_nullkey"
    __table_args__ = (
        UniqueConstraint("user_id", "kind", "run_id", name="uq_nullkey"),
        Index("uq_nullkey_null_run", "user_id", "kind", unique=True,
              postgresql_where=text("run_id IS NULL")),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String, default="training")
    run_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    n: Mapped[int] = mapped_column(default=0)


class Updatable(Base):
    """The `.or_update` path: losers bump `n` with a server-side expression."""

    __tablename__ = "t_update"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    k: Mapped[str] = mapped_column(String, unique=True)
    n: Mapped[int] = mapped_column(default=0)


class CtlNull(Base):
    """CONTROL: the DEF499 table WITHOUT the partial index (NULL run_id is not deduplicated)."""

    __tablename__ = "t_ctl_null"
    __table_args__ = (UniqueConstraint("user_id", "kind", "run_id", name="uq_ctl_null"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String, default="training")
    run_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class CtlPlain(Base):
    """CONTROL: plain unique key, old read-then-insert pattern (expects IntegrityError)."""

    __tablename__ = "t_ctl_plain"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    k: Mapped[str] = mapped_column(String, unique=True)


def _scrub(msg: str, url: str) -> str:
    out = msg.replace(url, "<DATABASE_URL>")
    try:
        pw = make_url(url).password
        if pw:
            out = out.replace(pw, "***")
    except Exception:
        pass
    return out


def _sync_url(raw: str) -> str:
    u = make_url(raw)
    if "asyncpg" in u.drivername:
        return u.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)
    return raw


def _engine(url: str, schema: str, pool: int):
    eng = create_engine(url, pool_size=pool, max_overflow=0)

    @event.listens_for(eng, "connect")
    def _pin(dbapi_conn, _rec):
        cur = dbapi_conn.cursor()
        cur.execute(f'SET search_path TO "{schema}"')
        cur.execute("SET statement_timeout = '30s'")
        cur.execute("SET lock_timeout = '20s'")
        cur.close()
        dbapi_conn.commit()

    return eng


def _race(eng, work, n=THREADS) -> list:
    """Run `work(session, idx)` on `n` real threads released by one barrier; return per-thread
    ('ok', result) or ('exc', exception)."""
    barrier = threading.Barrier(n, timeout=30)
    out: list = [None] * n

    def run(i):
        try:
            with Session(eng, expire_on_commit=False) as s:
                barrier.wait()
                try:
                    res = work(s, i)
                    s.commit()
                    out[i] = ("ok", res)
                except BaseException as e:  # noqa: BLE001 - classified by the caller, never dropped
                    s.rollback()
                    out[i] = ("exc", e)
        except BaseException as e:  # noqa: BLE001
            out[i] = ("exc", e)

    ts = [threading.Thread(target=run, args=(i,)) for i in range(n)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(60)
    assert all(not t.is_alive() for t in ts), "thread hung"
    return out


def _count(eng, model, **eq) -> int:
    with Session(eng) as s:
        q = select(func.count()).select_from(model)
        for c, v in eq.items():
            col = getattr(model, c)
            q = q.where(col.is_(None) if v is None else col == v)
        return s.execute(q).scalar_one()


def run_claim_mode(eng, model, mode: str, keyfn, label: str) -> dict:
    stats: Counter = Counter()
    failures: list[str] = []
    for r in range(ROUNDS):
        key = keyfn(r)

        def work(s, i, key=key):
            c = ac.claim(s, model, key=key, values={})
            if mode == "skip":
                row = c.or_skip()
            elif mode == "update":
                row = c.or_update(lambda x: setattr(x, "n", model.n + 1))
            else:
                row = c.or_raise()
            return c.created, row.id

        res = _race(eng, work)
        oks = [p for k, p in res if k == "ok"]
        excs = [p for k, p in res if k == "exc"]
        ints = [e for e in excs if isinstance(e, IntegrityError)]
        collisions = [e for e in excs if isinstance(e, ac.Collision)]
        other = [e for e in excs if not isinstance(e, ac.Collision)]
        creators = sum(1 for c, _ in oks if c)
        ids = {i for _, i in oks}
        rows = _count(eng, model, **key)

        stats["rounds"] += 1
        stats["creators"] += creators
        stats["integrity_errors"] += len(ints)
        stats["other_errors"] += len(other)
        stats["collisions_raised"] += len(collisions)
        stats["losers_got_winner_row"] += sum(1 for c, i in oks if not c and len(ids) == 1)

        if creators != 1:
            failures.append(f"r{r}: creators={creators}")
        if len(ids) != 1:
            failures.append(f"r{r}: distinct returned row ids={len(ids)}")
        if mode == "raise":
            if len(collisions) != THREADS - 1:
                failures.append(f"r{r}: collisions={len(collisions)}")
        elif len(oks) != THREADS:
            failures.append(f"r{r}: returned={len(oks)}")
        if ints:
            failures.append(f"r{r}: IntegrityError escaped x{len(ints)}")
        if other:
            failures.append(f"r{r}: other errors {[type(e).__name__ for e in other]}")
        if rows != 1:
            failures.append(f"r{r}: rows for key={rows}")
        if mode == "update" and ids:
            with Session(eng) as s:
                n = s.execute(select(model.n).where(model.id == next(iter(ids)))).scalar_one()
            if n != THREADS - 1:
                failures.append(f"r{r}: n={n} expected {THREADS - 1}")
    return {"label": label, "table": model.__tablename__, "mode": mode, **stats,
            "pass": not failures, "failures": failures[:5]}


def run_controls(eng) -> dict:
    dup_rounds = dup_rows = 0
    for r in range(ROUNDS):
        uid = f"ctl-null-{r}"

        def work(s, i, uid=uid):
            existing = s.execute(select(CtlNull).where(
                CtlNull.user_id == uid, CtlNull.kind == "training", CtlNull.run_id.is_(None))).scalars().first()
            if existing is None:
                s.add(CtlNull(user_id=uid, kind="training", run_id=None))
                s.flush()
            return None

        _race(eng, work)
        n = _count(eng, CtlNull, user_id=uid)
        if n > 1:
            dup_rounds += 1
            dup_rows += n - 1
    ie_rounds = ie_total = 0
    for r in range(ROUNDS):
        k = f"ctl-plain-{r}"

        def work2(s, i, k=k):
            existing = s.execute(select(CtlPlain).where(CtlPlain.k == k)).scalars().first()
            if existing is None:
                s.add(CtlPlain(k=k))
                s.flush()
            return None

        res = _race(eng, work2)
        ie = sum(1 for kind, p in res if kind == "exc" and isinstance(p, IntegrityError))
        if ie:
            ie_rounds += 1
            ie_total += ie
    return {
        "null_key_no_partial_index": {"rounds_with_duplicates": dup_rounds, "extra_rows": dup_rows, "rounds": ROUNDS},
        "plain_key_read_then_insert": {"rounds_with_integrity_error": ie_rounds, "integrity_errors": ie_total, "rounds": ROUNDS},
        "pass": dup_rounds > 0,
    }


def main() -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("FAIL: DATABASE_URL not set")
        return 2
    url = _sync_url(url)
    schema = f"iss001_test_{secrets.token_hex(4)}"
    assert re.fullmatch(r"iss001_test_[0-9a-f]{8}", schema)
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    report: dict = {"schema": schema, "threads": THREADS, "rounds": ROUNDS, "claim_source": AC_SOURCE}
    rc = 1
    try:
        with admin.connect() as c:
            report["postgres_version"] = c.execute(text("select version()")).scalar_one()
            c.execute(text(f'CREATE SCHEMA "{schema}"'))
        eng = _engine(url, schema, THREADS + 2)
        with eng.connect() as c:
            assert c.execute(text("select current_schema()")).scalar_one() == schema
            assert c.execute(text("select current_schemas(false)")).scalar_one() == [schema], "search_path leaks"
        Base.metadata.create_all(eng)
        with admin.connect() as c:
            tabs = {r[0] for r in c.execute(text(
                "select table_name from information_schema.tables where table_schema=:s"), {"s": schema})}
        assert tabs == {t.name for t in Base.metadata.sorted_tables}, tabs
        report["tables"] = sorted(tabs)

        null_lbl = "nullable composite, run_id NULL (partial-index arbiter)"
        modes = [
            run_claim_mode(eng, Plain, "skip", lambda r: {"k": f"p-skip-{r}"}, "plain unique key"),
            run_claim_mode(eng, Plain, "raise", lambda r: {"k": f"p-raise-{r}"}, "plain unique key"),
            run_claim_mode(eng, Updatable, "update", lambda r: {"k": f"c-upd-{r}"}, "plain unique key + counter"),
            run_claim_mode(eng, NullKey, "skip", lambda r: {"user_id": f"u-skip-{r}", "kind": "training", "run_id": None}, null_lbl),
            run_claim_mode(eng, NullKey, "update", lambda r: {"user_id": f"u-upd-{r}", "kind": "training", "run_id": None}, null_lbl),
            run_claim_mode(eng, NullKey, "raise", lambda r: {"user_id": f"u-raise-{r}", "kind": "training", "run_id": None}, null_lbl),
            run_claim_mode(eng, NullKey, "skip", lambda r: {"user_id": f"u-nn-{r}", "kind": "training", "run_id": f"run{r}"},
                           "nullable composite, run_id NOT NULL (full-constraint arbiter)"),
        ]
        report["modes"] = modes

        with Session(eng) as s:
            try:
                ac.claim(s, CtlNull, key={"user_id": "x", "kind": "training", "run_id": None}).or_skip()
                report["noarbiter_refused"] = False
            except ac.NoArbiter:
                report["noarbiter_refused"] = True
            s.rollback()

        report["control"] = run_controls(eng)
        ok = all(m["pass"] for m in modes) and report["control"]["pass"] and report["noarbiter_refused"]
        report["verdict"] = "PASS" if ok else "FAIL"
        rc = 0 if ok else 1
        eng.dispose()
    except BaseException as e:  # noqa: BLE001
        report["error"] = f"{type(e).__name__}: {_scrub(str(e), url)[:500]}"
        report["verdict"] = "ERROR"
        rc = 3
    finally:
        try:
            with admin.connect() as c:
                c.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
                left = c.execute(text(
                    "select count(*) from information_schema.schemata where schema_name like 'iss001_test_%'")).scalar_one()
            report["leftover_iss001_test_schemas"] = left
            if left != 0:
                rc = rc or 4
        except BaseException as e:  # noqa: BLE001
            report["drop_error"] = f"{type(e).__name__}: {_scrub(str(e), url)[:300]}"
            rc = rc or 5
        admin.dispose()
    print(json.dumps(report, indent=2, default=str))
    return rc


if __name__ == "__main__":
    sys.exit(main())
