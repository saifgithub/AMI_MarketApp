"""Alembic environment — single env that handles online + offline migrations
against whatever URL `app.db` resolves (Postgres in compose, sqlite in dev).

Autogenerate target is the project's `Base.metadata`, so adding a new ORM
model + running `alembic revision --autogenerate -m "..."` produces a diff
against the live DB.

Production deploys SHOULD use `alembic upgrade head`. Solo-dev + tests
short-circuit this with `Base.metadata.create_all()` via `init_schema()`
in `app.db.session` — both routes converge on the same schema.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.db import models as _models  # noqa: F401 — registers tables
from app.db.base import Base
from app.db.session import _resolve_url


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url from app config so we don't keep two sources of truth.
config.set_main_option("sqlalchemy.url", _resolve_url())

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
