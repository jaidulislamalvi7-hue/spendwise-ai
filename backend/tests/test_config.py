"""Tests for backend configuration loading."""

from pathlib import Path

from app.config import PROJECT_ROOT, Settings, get_settings


def test_env_file_points_at_project_root() -> None:
    # The .env path is configured explicitly, so it does not depend on the
    # working directory the process was started from.
    env_file = Settings.model_config["env_file"]
    assert Path(env_file) == PROJECT_ROOT / ".env"


def test_default_app_env_is_development(monkeypatch) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    settings = Settings()
    assert settings.app_env == "development"


def test_app_env_is_read_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "staging")
    settings = Settings()
    assert settings.app_env == "staging"


def test_invalid_app_env_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "not-an-env")
    try:
        Settings()
    except ValueError:
        return
    raise AssertionError("Invalid APP_ENV should have raised a validation error")


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()
