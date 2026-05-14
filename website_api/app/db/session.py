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
    return _engine


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
