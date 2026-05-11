"""Declarative base + cross-dialect type helpers.

We keep the schema portable across two dialects:
  - Postgres (production / docker-compose dev) — native JSONB + UUID
  - SQLite   (zero-config solo-dev + test fallback) — JSON-as-TEXT + UUID-as-CHAR

`JsonB` and `Uuid` here pick the right column type at create-table time
so the same ORM models work in both.
"""

from __future__ import annotations

from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import CHAR, JSON, TypeDecorator
from uuid import UUID


class Base(DeclarativeBase):
    """Project-wide SQLAlchemy declarative base."""


class JsonB(TypeDecorator):  # type: ignore[type-arg]
    """JSONB on Postgres, JSON on SQLite. Stores dicts/lists either way."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


class Uuid(TypeDecorator):  # type: ignore[type-arg]
    """UUID on Postgres, CHAR(36) on SQLite — both round-trip Python UUIDs."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value if isinstance(value, UUID) else UUID(str(value))
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, UUID):
            return value
        return UUID(str(value))
