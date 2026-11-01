"""SQLAlchemy engine, session factory and FastAPI dependencies."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_database_url


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models."""


def build_engine(database_url: str | None = None) -> Engine:
    """Create a configured SQLAlchemy engine.

    The URL comes from ``DATABASE_URL`` (see ``get_database_url``) unless one is
    supplied explicitly. No pool tuning is added because performance
    measurement has not justified it.
    """
    url = database_url or get_database_url()
    return create_engine(url, future=True, pool_pre_ping=True)


_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def get_engine() -> Engine:
    """Return the process-wide engine, creating it on first use.

    Creating the engine lazily means a missing or placeholder ``DATABASE_URL``
    raises a clear configuration error when a connection is needed, rather than
    at import time with a confusing database driver traceback.
    """
    global _engine
    if _engine is None:
        _engine = build_engine()
    return _engine


def get_session_factory() -> sessionmaker:
    """Return the process-wide session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(), autoflush=False, expire_on_commit=False, future=True
        )
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """Yield a database session, rolling back on error and always closing.

    Without the rollback, a request that fails mid-transaction returns a
    connection holding an aborted transaction to the pool.
    """
    session = get_session_factory()()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
