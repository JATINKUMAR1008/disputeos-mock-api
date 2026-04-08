"""
Alembic environment.

Resolves the database URL from the environment (DIRECT_DATABASE_URL
preferred, falling back to DATABASE_URL) and points autogenerate at the
SQLAlchemy metadata declared in `models.py`.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

# Pull values from .env so `alembic upgrade head` works from a plain shell.
load_dotenv()

from models import Base  # noqa: E402  — must come after load_dotenv

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _resolve_url() -> str:
    """Pick the URL Alembic should connect with.

    Prefer the direct connection because some DDL fails under
    transaction-mode pooling; fall back to DATABASE_URL for environments
    that only set one variable.
    """
    url = os.environ.get("DIRECT_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "Neither DIRECT_DATABASE_URL nor DATABASE_URL is set. Copy "
            ".env.example to .env and fill in the Supabase connection "
            "strings before running Alembic."
        )
    return url


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting to the DB."""
    context.configure(
        url=_resolve_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Open a real DB connection and apply migrations."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _resolve_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
