"""Database engine and session factory.

The engine is created lazily on first use. Tests override DATABASE_URL via
the WEBSITE_TEST_DATABASE_URL environment variable.
"""

import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_engine = None
_SessionLocal = None


def _get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        url = os.environ.get("WEBSITE_TEST_DATABASE_URL") or settings.database_url
        _engine = create_engine(url, pool_pre_ping=True)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=True, autocommit=False)
        # Create tables whenever a new engine is initialised (covers test resets too)
        from app.db.base import Base
        import app.models  # noqa: F401
        Base.metadata.create_all(bind=_engine)
        _add_missing_columns(_engine, Base)
    return _engine


def _add_missing_columns(engine, base) -> None:
    """Add model columns that an already-existing table lacks.

    `create_all` only creates absent tables, and this service has no alembic.
    Without this, a column added to a live table (CR267 WP-51 extended
    `waitlist`) would 500 on every query until someone ALTERed by hand.
    Additive and idempotent only; anything else is a deliberate manual step.
    """
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    for table in base.metadata.sorted_tables:
        if not insp.has_table(table.name):
            continue
        have = {c["name"] for c in insp.get_columns(table.name)}
        for col in table.columns:
            if col.name in have:
                continue
            ddl = col.type.compile(dialect=engine.dialect)
            with engine.begin() as conn:
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {ddl}'))


def init_schema():
    _get_engine()  # schema is created inside _get_engine on first call


@contextmanager
def get_session() -> Session:
    _get_engine()  # ensure engine + _SessionLocal are initialised
    session: Session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
