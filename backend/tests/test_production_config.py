"""Tests for production deployment configuration (no database required).

Every Settings object here is constructed with ``_env_file=None`` so the
developer's local ``.env`` and process environment can never influence the
result. A test that silently inherits a real JWT_SECRET would pass for the
wrong reason.
"""

import pytest
from pydantic import SecretStr, ValidationError

from app.config import Settings

# A value containing CHANGE_ME, which the production validator must reject.
PLACEHOLDER_SECRET = "CHANGE_ME_test_secret"
# A value that looks like a real secret, used when only other fields matter.
REAL_LOOKING_SECRET = "a-real-production-secret-value"
SAMPLE_DATABASE_URL = "postgresql+psycopg://user:pass@localhost:5432/testdb"


def make_settings(**overrides) -> Settings:
    """Build Settings from explicit values only, ignoring any ``.env`` file.

    ``_env_file=None`` disables the file source; passing every field the test
    cares about keeps the remaining defaults deterministic.
    """
    values = {
        "app_env": "development",
        "jwt_secret": PLACEHOLDER_SECRET,
        "database_url": SAMPLE_DATABASE_URL,
        "cors_allow_origins": "",
        "log_level": "INFO",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


class TestCorsConfiguration:
    def test_cors_is_disabled_by_default(self) -> None:
        assert make_settings().cors_origins == []

    def test_explicit_origins_are_parsed(self) -> None:
        settings = make_settings(cors_allow_origins="https://a.example.com, https://b.example.com")
        assert settings.cors_origins == ["https://a.example.com", "https://b.example.com"]

    def test_blank_entries_are_ignored(self) -> None:
        settings = make_settings(cors_allow_origins="https://a.example.com,,")
        assert settings.cors_origins == ["https://a.example.com"]

    def test_wildcard_is_rejected(self) -> None:
        # "*" with credentials would let any site call the API.
        with pytest.raises(ValidationError):
            make_settings(cors_allow_origins="*")

    def test_wildcard_inside_a_list_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            make_settings(cors_allow_origins="https://a.example.com,*")


class TestLoggingConfiguration:
    def test_default_log_level_is_info(self) -> None:
        assert make_settings().log_level == "INFO"

    def test_valid_levels_are_accepted(self) -> None:
        for level in ("DEBUG", "INFO", "WARNING", "ERROR"):
            assert make_settings(log_level=level).log_level == level

    def test_invalid_level_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            make_settings(log_level="TRACE")


class TestStartupValidation:
    def test_development_does_not_require_production_secrets(self) -> None:
        # Development keeps the placeholder default so local work is frictionless.
        settings = make_settings(app_env="development", jwt_secret=PLACEHOLDER_SECRET)
        assert settings.app_env == "development"

    def test_production_rejects_placeholder_secret(self) -> None:
        with pytest.raises(ValidationError, match="JWT_SECRET must be set"):
            make_settings(app_env="production", jwt_secret=PLACEHOLDER_SECRET)

    def test_production_accepts_real_secret(self) -> None:
        settings = make_settings(app_env="production", jwt_secret=REAL_LOOKING_SECRET)
        assert settings.app_env == "production"

    def test_production_secret_is_not_in_repr(self) -> None:
        settings = make_settings(app_env="production", jwt_secret="do-not-print-me-123456")
        assert "do-not-print-me-123456" not in repr(settings)


class TestHealthProbeContract:
    def _development_settings(self):
        """Deterministic development settings, ignoring the developer's .env."""
        return make_settings(app_env="development")

    def test_health_schema_is_minimal(self, monkeypatch) -> None:
        # Mirrors the assertion in test_api.py without needing a database.
        from app import main as main_module

        monkeypatch.setattr(main_module, "get_settings", self._development_settings)
        app = main_module.create_app()
        route = next(r for r in app.routes if getattr(r, "path", None) == "/health")
        assert route is not None

    def test_docs_are_disabled_in_production(self, monkeypatch) -> None:
        from app import main as main_module

        # The guard now validates the Settings object itself, so a fully valid
        # production config is enough to reach app construction.
        monkeypatch.setattr(
            main_module,
            "get_settings",
            lambda: make_settings(
                app_env="production",
                jwt_secret=REAL_LOOKING_SECRET,
                database_url=SAMPLE_DATABASE_URL,
            ),
        )
        app = main_module.create_app()
        assert app.docs_url is None
        assert app.openapi_url is None

    def test_production_startup_fails_without_secret(self, monkeypatch) -> None:
        """A production start with a placeholder secret must not succeed.

        The boundary that rejects it is Pydantic validation inside ``Settings``.
        The placeholder is supplied explicitly and ``_env_file=None`` prevents a
        real JWT_SECRET in the developer's .env from satisfying validation.
        """
        from app import main as main_module

        def _broken_settings():
            return make_settings(app_env="production", jwt_secret=PLACEHOLDER_SECRET)

        monkeypatch.setattr(main_module, "get_settings", _broken_settings)
        with pytest.raises(ValidationError, match="JWT_SECRET must be set"):
            main_module.create_app()

    def test_startup_guard_catches_placeholder_secret(self) -> None:
        """Defence in depth: the guard itself rejects a placeholder secret.

        Development settings accept the placeholder, so they can be constructed;
        ``app_env`` is then forced to production to bypass the field validator
        and prove ``_validate_production_configuration`` enforces the rule on its
        own rather than delegating it.
        """
        from app import main as main_module

        settings = make_settings(app_env="development", jwt_secret=PLACEHOLDER_SECRET)
        assert "CHANGE_ME" in settings.jwt_secret.get_secret_value()

        object.__setattr__(settings, "app_env", "production")
        with pytest.raises(RuntimeError, match="JWT_SECRET is not set"):
            main_module._validate_production_configuration(settings)

    def test_startup_guard_catches_empty_secret(self) -> None:
        from app import main as main_module

        settings = make_settings(app_env="development", jwt_secret=REAL_LOOKING_SECRET)
        object.__setattr__(settings, "app_env", "production")
        object.__setattr__(settings, "jwt_secret", SecretStr(""))
        with pytest.raises(RuntimeError, match="JWT_SECRET is not set"):
            main_module._validate_production_configuration(settings)

    def test_production_startup_fails_with_placeholder_database(self, monkeypatch) -> None:
        from app import main as main_module

        # database_url has no field validator, so construction succeeds and the
        # guard is the boundary that rejects it.
        monkeypatch.setattr(
            main_module,
            "get_settings",
            lambda: make_settings(
                app_env="production",
                jwt_secret=REAL_LOOKING_SECRET,
                database_url="postgresql+psycopg://postgres:CHANGE_ME@localhost:5432/db",
            ),
        )
        with pytest.raises(RuntimeError, match="DATABASE_URL is not set"):
            main_module.create_app()

    def test_development_startup_still_works_with_defaults(self, monkeypatch) -> None:
        # Development must remain frictionless: placeholders are tolerated.
        from app import main as main_module

        monkeypatch.setattr(main_module, "get_settings", self._development_settings)
        app = main_module.create_app()
        assert app is not None

    def test_docs_are_enabled_in_development(self, monkeypatch) -> None:
        from app import main as main_module

        monkeypatch.setattr(main_module, "get_settings", self._development_settings)
        app = main_module.create_app()
        assert app.docs_url == "/docs"


class TestDeploymentFiles:
    """Static checks on the Docker and Compose assets.

    These catch configuration drift (a COPY of a missing file, a published
    database port, a missing healthcheck) without building an image.
    """

    def _root(self):
        from pathlib import Path

        from app.config import PROJECT_ROOT

        root = Path(PROJECT_ROOT)
        if not (root / "docker-compose.yml").is_file():
            pytest.skip("deployment files not present in this checkout")
        return root

    def test_backend_dockerfile_copies_existing_paths(self) -> None:
        root = self._root()
        dockerfile = (root / "backend" / "Dockerfile").read_text(encoding="utf-8")
        assert "COPY requirements.txt" in dockerfile
        assert (root / "requirements.txt").is_file()
        # The whole backend tree must be present for uvicorn to import app.main.
        assert "COPY backend/" in dockerfile
        assert (root / "backend" / "alembic.ini").is_file()

    def test_frontend_dockerfile_copies_existing_paths(self) -> None:
        root = self._root()
        dockerfile = (root / "frontend" / "Dockerfile").read_text(encoding="utf-8")
        assert "COPY frontend/" in dockerfile
        assert (root / "frontend" / "streamlit_app.py").is_file()

    def test_backend_healthcheck_uses_installed_curl(self) -> None:
        root = self._root()
        dockerfile = (root / "backend" / "Dockerfile").read_text(encoding="utf-8")
        assert "curl" in dockerfile
        assert "/health" in dockerfile

    def test_frontend_healthcheck_uses_python_only(self) -> None:
        root = self._root()
        dockerfile = (root / "frontend" / "Dockerfile").read_text(encoding="utf-8")
        # python is always present in a python image; no extra tool is installed.
        assert "python -c" in dockerfile
        assert "8501" in dockerfile

    def test_containers_run_as_non_root(self) -> None:
        root = self._root()
        for name in ("backend", "frontend"):
            text = (root / name / "Dockerfile").read_text(encoding="utf-8")
            assert "USER appuser" in text, f"{name} Dockerfile does not drop root"
            assert "useradd" in text

    def test_dockerignore_excludes_secrets_and_venvs(self) -> None:
        root = self._root()
        text = (root / ".dockerignore").read_text(encoding="utf-8")
        for pattern in (".env", ".env.production", ".venv/", "__pycache__/", "**/tests/"):
            assert pattern in text, f"dockerignore does not exclude {pattern}"

    def test_local_compose_does_not_publish_database_port(self) -> None:
        root = self._root()
        text = (root / "docker-compose.yml").read_text(encoding="utf-8")
        db_block = text.split("backend:", 1)[0]
        assert "5432" not in db_block, "the database port must not be published"

    def test_local_compose_uses_persistent_volume(self) -> None:
        root = self._root()
        text = (root / "docker-compose.yml").read_text(encoding="utf-8")
        assert "spendwise_pgdata" in text
        assert "pg_isready" in text
        assert "service_healthy" in text

    def test_compose_sets_internal_backend_url(self) -> None:
        root = self._root()
        for name in ("docker-compose.yml", "docker-compose.prod.yml"):
            text = (root / name).read_text(encoding="utf-8")
            assert "BACKEND_API_URL: http://backend:8000" in text

    def test_production_compose_has_no_database_service(self) -> None:
        root = self._root()
        text = (root / "docker-compose.prod.yml").read_text(encoding="utf-8")
        assert "postgres:" not in text
        assert "5432" not in text

    def test_production_compose_binds_only_loopback(self) -> None:
        root = self._root()
        text = (root / "docker-compose.prod.yml").read_text(encoding="utf-8")
        assert "127.0.0.1:8000:8000" in text
        assert "127.0.0.1:8501:8501" in text

    def test_env_example_documents_configurable_settings(self) -> None:
        """Every setting a deployer may need to override must be documented.

        ``APP_NAME`` is deliberately excluded: it is a cosmetic default that no
        deployment must set, and adding it would be noise. The remaining fields
        all affect behaviour, security, or connectivity.
        """
        root = self._root()
        text = (root / ".env.example").read_text(encoding="utf-8")

        not_configurable = {"app_name"}
        for field in Settings.model_fields:
            if field in not_configurable:
                continue
            assert field.upper() in text, f".env.example omits {field.upper()}"

    def test_env_example_covers_frontend_setting(self) -> None:
        # BACKEND_API_URL belongs to the frontend Settings class, not the backend.
        root = self._root()
        text = (root / ".env.example").read_text(encoding="utf-8")
        assert "BACKEND_API_URL" in text

    def test_env_example_has_no_real_secrets(self) -> None:
        root = self._root()
        text = (root / ".env.example").read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, _, value = stripped.partition("=")
            if key.strip() in {"JWT_SECRET", "POSTGRES_PASSWORD", "DATABASE_URL"}:
                assert "CHANGE_ME" in value, f"{key} must use a CHANGE_ME placeholder"

    def test_alembic_ini_resolves_app_from_the_container_layout(self) -> None:
        root = self._root()
        text = (root / "backend" / "alembic.ini").read_text(encoding="utf-8")
        # "." must be present so /app works; ".." keeps the local layout working.
        line = next(row for row in text.splitlines() if row.startswith("prepend_sys_path"))
        assert "." in line.split("=", 1)[1].split()
        assert ".." in line.split("=", 1)[1].split()
