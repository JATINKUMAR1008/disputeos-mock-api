"""
Database engine + session factory.

The rest of the app talks to Postgres through `SessionLocal()` — a
SQLAlchemy sessionmaker bound to a single module-level `Engine`. The
engine is created lazily so importing this module doesn't force a
connection attempt (useful for Alembic autogenerate and for unit tests
that stub out the store).

Environment variables:

- `DATABASE_URL`        — connection string used by the running app.
                          Typically points at the Supabase Supavisor
                          pooler (transaction mode, port 6543).
- `DIRECT_DATABASE_URL` — optional, used by Alembic only. Points at
                          the direct Postgres endpoint (port 5432)
                          because some DDL doesn't play well with
                          transaction-mode pooling.

Both URLs should use the `postgresql+psycopg://` scheme so SQLAlchemy
picks the psycopg (v3) driver.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

# Load .env on import so local dev doesn't need to export vars by hand.
# In containers the env is set directly and load_dotenv is a no-op.
load_dotenv()


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _build_engine() -> Engine:
    """Create the SQLAlchemy engine from DATABASE_URL.

    `pool_pre_ping=True` catches connections that the Supavisor pooler
    has silently recycled, which otherwise surface as "server closed
    the connection unexpectedly" on the first query after idle.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env and fill "
            "in the Supabase pooler connection string, or export it in "
            "your environment."
        )
    return create_engine(
        url,
        future=True,
        pool_pre_ping=True,
    )


def get_engine() -> Engine:
    """Return the module-level engine, creating it on first call."""
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    """Return the module-level sessionmaker, creating it on first call."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            future=True,
        )
    return _SessionLocal


def SessionLocal() -> Session:
    """Open a new SQLAlchemy session. Caller is responsible for closing."""
    return get_sessionmaker()()
