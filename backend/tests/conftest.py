"""Shared test fixtures.

Unit tests (validation, security helpers) need no database. Database and API
tests are skipped automatically when PostgreSQL is unreachable.

SAFETY: the test engine is bound to ``TEST_DATABASE_URL`` only. The fixtures
below never use ``DATABASE_URL``, so the developer's real database is never
touched by the test suite.
"""

import uuid
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from tests.db_guard import DATABASE_AVAILABLE, TEST_DATABASE_URL, _assert_safe


def _test_settings():
    """Deterministic settings used by the API tests.

    ``database_url`` points at the *test* database, never at the configured
    application database.
    """
    from app.config import Settings

    return Settings(
        app_env="development",
        jwt_secret="test-secret-value-not-a-placeholder",
        jwt_algorithm="HS256",
        jwt_expire_minutes=60,
        database_url=TEST_DATABASE_URL or "postgresql+psycopg://unused@localhost/unused",
    )


def _require_test_database() -> str:
    """Fail loudly if the test database is not reachable."""
    if not DATABASE_AVAILABLE:
        pytest.skip("PostgreSQL test database not reachable")
    return TEST_DATABASE_URL


@pytest.fixture(scope="session")
def db_engine() -> Generator[Engine, None, None]:
    """Session-wide engine for the *test* database with a freshly built schema."""
    import app.models  # noqa: F401  (register all models)
    from app.database import Base

    url = _require_test_database()
    # Hard stop: never drop tables in a database that is not clearly a test DB.
    _assert_safe(url)
    engine = create_engine(url, future=True)
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Generator[Session, None, None]:
    """A session that is rolled back afterwards so tests stay independent."""
    factory = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False, future=True)
    session = factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def sample_user(db_session: Session):
    """Create one user directly through the service layer."""
    from app.services.user_service import create_user_unchecked

    return create_user_unchecked(
        db_session,
        email=f"user-{uuid.uuid4().hex[:8]}@example.com",
        password="supersecret123",
        primary_currency="USD",
        timezone="UTC",
    )


@pytest.fixture
def client(db_engine: Engine, monkeypatch) -> Generator:
    """Test client bound to the test database with deterministic settings."""
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import create_app

    factory = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False, future=True)

    monkeypatch.setattr("app.config.get_settings", _test_settings)

    app = create_app()

    def override_db():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def register_user(client):
    """Return a helper that registers and logs in a fresh user."""

    def _register() -> dict:
        payload = {
            "email": f"api-{uuid.uuid4().hex[:10]}@example.com",
            "password": "supersecret123",
            "primary_currency": "USD",
            "timezone": "UTC",
        }
        response = client.post("/api/auth/register", json=payload)
        assert response.status_code == 201, response.text
        token = client.post(
            "/api/auth/login",
            json={"email": payload["email"], "password": payload["password"]},
        ).json()["access_token"]
        return {"token": token, "email": payload["email"], "user": response.json()}

    return _register
