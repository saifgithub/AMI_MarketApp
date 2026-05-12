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
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


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


def init_schema() -> None:
    """Create all tables in the configured DB. Idempotent.

    On a fresh DB, runs `Base.metadata.create_all()` AND stamps Alembic
    to `head` so subsequent `alembic upgrade head` is a no-op rather
    than a DuplicateTable error. If `alembic_version` already exists,
    we trust whatever's there and don't re-stamp — that preserves any
    in-progress upgrade state from a prior alembic run.

    Why both: solo-dev + tests use `create_all()` for speed (no
    per-migration step on a fresh sqlite tempfile); the production
    deploys want Alembic to be the formal record. Self-stamping
    bridges them — a fresh container can finish boot in milliseconds
    AND a /promote-to-alpha step 6 can run `alembic upgrade head`
    cleanly afterward.
    """
    from app.db import models as _models  # noqa: F401
    engine = get_engine()
    Base.metadata.create_all(engine)

    # Self-stamp Alembic so the schema we just produced is recognized
    # as up-to-date. Best-effort: if alembic isn't installed (older
    # dev environments, the slim test image) or the alembic.ini can't
    # be located, swallow the exception — the schema is correct, only
    # the migration-tracking is unset.
    try:
        from alembic import command as alembic_command
        from alembic.config import Config as AlembicConfig
        from sqlalchemy import inspect

        inspector = inspect(engine)
        if "alembic_version" in inspector.get_table_names():
            return  # Already stamped (or upgraded) — don't disturb.

        # alembic.ini lives at the backend package root, two parents up
        # from this file (db/session.py → db → app → backend).
        alembic_ini = Path(__file__).resolve().parent.parent.parent / "alembic.ini"
        if not alembic_ini.exists():
            return  # Test environments may not ship alembic.ini.
        cfg = AlembicConfig(str(alembic_ini))
        cfg.set_main_option("sqlalchemy.url", str(engine.url))
        alembic_command.stamp(cfg, "head")
    except Exception:
        # Schema is in place; Alembic stamp is a courtesy. Never let
        # this branch break boot.
        pass


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
