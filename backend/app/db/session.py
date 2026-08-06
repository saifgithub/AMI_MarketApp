"""Engine + session lifecycle.

We expose a process-singleton engine and sessionmaker, lazy-initialised the
first time `get_engine()` or `get_session()` is called. Tests reset this via
`reset_for_tests(url=...)` to point at a fresh sqlite DB and recreate the
schema.

`get_session()` is a contextmanager so callers do `with get_session() as s:` —
this matches the existing sync ergonomics of the in-memory stores.
"""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.logging import logger
from app.db.base import Base


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None
_schema_checked_for: Engine | None = None
_schema_lock = threading.Lock()


def _resolve_url() -> str:
    """Pick a DB URL. Test fixture wins; then env; then sqlite fallback."""
    test_url = os.environ.get("AMI_TEST_DATABASE_URL")
    if test_url:
        return test_url
    url = settings.database_url or ""
    # The .env.example shipped an async asyncpg URL while we lived in
    # in-memory mode. Convert to a sync driver so old configs still work.
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    if not url or url == "postgresql+psycopg2://postgres:postgres@localhost:5432/ami_trade":
        # No real DB configured — solo-dev sqlite next to the backend pkg
        local = Path(__file__).resolve().parent.parent.parent / ".local.db"
        return f"sqlite:///{local}"
    return url


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        url = _resolve_url()
        connect_args: dict = {}
        if url.startswith("sqlite"):
            # Multiple Sessions across threads (FastAPI uses a threadpool for
            # sync deps) — sqlite needs this opt-in.
            connect_args["check_same_thread"] = False
        _engine = create_engine(url, future=True, connect_args=connect_args)
        _SessionLocal = sessionmaker(
            bind=_engine, autoflush=False, autocommit=False, expire_on_commit=False,
        )
    return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


@contextmanager
def get_session() -> Iterator[Session]:
    """Open a session, commit on clean exit, rollback on error, always close."""
    SessionLocal = get_sessionmaker()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _alembic_config(engine: Engine):
    """The project's alembic.ini, pointed at this engine, or None if it isn't
    shipped (the slim test image does not carry it)."""
    from alembic.config import Config as AlembicConfig

    # alembic.ini lives at the backend package root, two parents up
    # from this file (db/session.py → db → app → backend).
    alembic_ini = Path(__file__).resolve().parent.parent.parent / "alembic.ini"
    if not alembic_ini.exists():
        return None
    cfg = AlembicConfig(str(alembic_ini))
    cfg.set_main_option("sqlalchemy.url", str(engine.url))
    return cfg


def _report_if_behind_head(engine: Engine) -> None:
    """Say so, loudly, when the DB is behind the code's own migration head.

    DEF215's outage was silent for exactly as long as it took someone to
    notice journal reads failing: the schema was old, the code was new, and
    nothing anywhere compared the two. This turns that into one named line
    with both revisions in it — the difference between reading a
    `UndefinedColumn` traceback and knowing which migration never ran.

    Never raises. A boot that refuses on a bad read here would convert a
    reporting problem into an outage, which is the wrong direction.
    """
    try:
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory

        cfg = _alembic_config(engine)
        if cfg is None:
            return
        head = ScriptDirectory.from_config(cfg).get_current_head()
        with engine.connect() as conn:
            current = MigrationContext.configure(conn).get_current_revision()
        if head is not None and current != head:
            logger.error(
                "db_schema_behind_head",
                current_revision=current,
                head_revision=head,
                hint="run `alembic upgrade head` — the running code expects head",
            )
    except Exception:
        logger.warn("db_schema_revision_check_failed", exc_info=True)


def init_schema() -> None:
    """Bring the configured DB up to the schema this code expects. Idempotent.

    **On a FRESH DB** (no `alembic_version`): `Base.metadata.create_all()` and
    then a self-stamp to `head`, so a later `alembic upgrade head` is a clean
    no-op. That is what makes a sqlite tempfile fixture cost milliseconds
    instead of a per-migration replay, and it is the case this function
    exists for.

    **On an EXISTING DB: it creates nothing.** Alembic owns the schema, and
    the only thing this function does is report whether the DB has caught up.

    That second paragraph is DEF215, and it is worth spelling out why, because
    the old ordering looked harmless. `create_all` ran FIRST and the
    `alembic_version` check guarded only the stamp below it. On an existing DB
    `create_all` still fired and built exactly the tables the incoming CR had
    just added — correctly, since it reads the same `Base.metadata` the
    migrations were autogenerated from — and then returned without stamping,
    because `alembic_version` was already there. Alembic was now behind
    reality with no record of it, so the first migration that CREATEd one of
    those tables died on `DuplicateTable`, and Alembic aborts the whole chain.

    **The damage was never the table it failed on.** Measured on Alpha
    2026-08-04: two CR136 tables were created this way, `alembic upgrade head`
    died on the first of them, and the two migrations AFTER it in the chain —
    which only ALTER `journal_entries`, a table `create_all` will never touch
    because it already exists — never ran. The promoted code mapped
    `JournalEntryRow.dedupe_key`, the column was absent, and every journal
    read on live Alpha failed. A create-table migration failing masked an
    ALTER the running code depended on, so the outage surfaced in an
    unrelated, already-shipped feature rather than in the new one.

    The check moving ABOVE `create_all` is the entire fix. `create_all` goes
    back to being what it is actually for — fresh databases, which in practice
    means test fixtures — and a real deployment is migration-only.
    """
    global _schema_checked_for

    from app.db import models as _models  # noqa: F401
    engine = get_engine()

    # Every store calls this from its constructor (13 sites), so without the
    # guard a process pays two extra round trips per store for a question whose
    # answer cannot change while the engine lives. Keyed on the engine OBJECT,
    # not a bool: `reset_for_tests` builds a new one, which re-arms the check
    # for free rather than needing its own reset line.
    if _schema_checked_for is engine:
        return

    # DEF215 audit r1, MINOR m1. The first submission called the concurrent
    # case "benign — checkfirst=True". `checkfirst` is not atomic: the auditor
    # put two threads on a barrier against a stripped DB and measured
    # `['OperationalError']` raising OUT of `init_schema`, with the DB itself
    # left coherent (one `alembic_version` row, 35 tables). So it corrupted
    # nothing, but one caller ate an exception at boot — which is not benign,
    # it is just survivable. FastAPI runs sync deps in a threadpool, so it is
    # reachable. The lock makes the whole check-and-build one critical section;
    # it is taken at most once per engine, so it costs nothing after the first
    # call and the fast path above never reaches it.
    with _schema_lock:
        if _schema_checked_for is engine:
            return
        _init_schema_locked(engine)


def _init_schema_locked(engine: Engine) -> None:
    global _schema_checked_for

    from sqlalchemy import inspect

    fresh = "alembic_version" not in inspect(engine).get_table_names()
    if not fresh:
        _report_if_behind_head(engine)
        _schema_checked_for = engine
        return

    Base.metadata.create_all(engine)

    # Self-stamp so the schema we just produced is recognised as up-to-date.
    # Best-effort: if alembic isn't installed (older dev environments, the
    # slim test image) the schema is still correct, only the migration
    # tracking is unset — never let it break boot.
    try:
        from alembic import command as alembic_command

        cfg = _alembic_config(engine)
        if cfg is not None:
            alembic_command.stamp(cfg, "head")
    except Exception:
        pass
    _schema_checked_for = engine


def reset_for_tests(url: str | None = None) -> None:
    """Tear down the singleton engine, swap URL, recreate schema.

    Pass an explicit `url` (typically `sqlite:///:memory:` or a tempfile) and
    the next `get_session()` will use it.
    """
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
    if url is not None:
        os.environ["AMI_TEST_DATABASE_URL"] = url
    elif "AMI_TEST_DATABASE_URL" in os.environ:
        del os.environ["AMI_TEST_DATABASE_URL"]
    init_schema()
