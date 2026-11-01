"""Detects whether a dedicated PostgreSQL *test* database is reachable.

SAFETY CONTRACT
---------------
Tests that run ``drop_all``/``create_all`` must never touch the developer's
real database. This module therefore refuses to produce a URL unless it is
unambiguously a test database:

- ``TEST_DATABASE_URL`` is honoured only if its database name ends with
  ``_test``.
- Otherwise the URL is derived from the configured ``DATABASE_URL`` by
  appending ``_test`` to the database name (``spendwise_db`` -> ``spendwise_db_test``).
- If neither yields a name ending in ``_test``, no URL is produced and every
  database-backed test is skipped.

Database-backed tests import ``requires_db`` from here, so an unreachable or
unsafe database can never be reported as a pass.
"""

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

TEST_SUFFIX = "_test"


def _configured_url() -> str | None:
    """Return the developer's configured URL without ever printing it."""
    base = os.environ.get("DATABASE_URL")
    if base:
        return base
    try:
        from app.config import get_settings

        return get_settings().database_url
    except Exception:  # noqa: BLE001 - configuration may be absent in unit runs
        return None


def _derive_test_url() -> str:
    """Return a URL whose database name ends with ``_test``, or an empty string."""
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        try:
            url = make_url(explicit)
        except Exception:  # noqa: BLE001
            return ""
        # Refuse an explicit URL that is not obviously a test database.
        if (url.database or "").endswith(TEST_SUFFIX):
            return url.render_as_string(hide_password=False)
        return ""

    base = _configured_url()
    if not base:
        return ""
    try:
        url = make_url(base)
    except Exception:  # noqa: BLE001
        return ""
    database = url.database or ""
    if not database:
        return ""
    if not database.endswith(TEST_SUFFIX):
        database = f"{database}{TEST_SUFFIX}"
    return url.set(database=database).render_as_string(hide_password=False)


TEST_DATABASE_URL = _derive_test_url()


def _database_available() -> bool:
    if not TEST_DATABASE_URL:
        return False
    try:
        engine = create_engine(TEST_DATABASE_URL, future=True)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
    except Exception:  # noqa: BLE001 - any failure means unavailable
        return False
    return True


def _safe_target() -> str:
    """Describe the test database without exposing the password."""
    if not TEST_DATABASE_URL:
        return "no *_test database configured"
    try:
        url = make_url(TEST_DATABASE_URL)
        return f"{url.host}:{url.port or 5432}/{url.database}"
    except Exception:  # noqa: BLE001
        return "invalid URL"


def _assert_safe(url: str) -> None:
    """Last-line defence before any destructive operation."""
    database = make_url(url).database or ""
    if not database.endswith(TEST_SUFFIX):
        raise RuntimeError(
            f"Refusing to run destructive tests against '{database}': "
            f"database name must end with '{TEST_SUFFIX}'."
        )


DATABASE_AVAILABLE = _database_available()

requires_db = pytest.mark.skipif(
    not DATABASE_AVAILABLE,
    reason=f"PostgreSQL test database not reachable ({_safe_target()})",
)
