"""SQLAlchemy declarative base with a portable UUID column type.

Works with both Postgres (native UUID) and SQLite (CHAR 36) so unit tests
run without a Postgres instance.
"""

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator


class Uuid(TypeDecorator):
    """UUID stored as native UUID on Postgres, CHAR(36) on SQLite."""

    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        import uuid
        return uuid.UUID(str(value))


class Base(DeclarativeBase):
    pass
