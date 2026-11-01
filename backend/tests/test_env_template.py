"""Contract tests between the settings model and the .env template.

Only active (uncommented) template entries are treated as configuration.
Deferred placeholders are intentionally not asserted as active settings.
"""

import re
from pathlib import Path

import pytest

from app.config import PROJECT_ROOT, Settings

ENV_EXAMPLE = Path(PROJECT_ROOT) / ".env.example"
COMPOSE_FILE = Path(PROJECT_ROOT) / "docker-compose.yml"


def read_active_entries() -> dict[str, str]:
    """Return the active KEY=value pairs from the template, in file order."""
    entries: dict[str, str] = {}
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        entries[key.strip()] = value.strip()
    return entries


def test_env_example_exists() -> None:
    assert ENV_EXAMPLE.is_file()


def test_template_has_active_settings() -> None:
    # Guards against every entry being commented out, which would silently
    # disable the checks below.
    assert read_active_entries(), "template has no active settings"


def test_app_env_is_documented() -> None:
    assert "APP_ENV" in read_active_entries()


def test_app_env_value_is_supported() -> None:
    allowed = set(Settings.model_fields["app_env"].annotation.__args__)
    assert read_active_entries()["APP_ENV"] in allowed


def _known_setting_names() -> set[str]:
    """Every configuration name the template is allowed to document.

    The template serves three consumers, so three sources are checked:
    - backend application settings (``app.config.Settings``)
    - frontend settings (``settings.Settings``)
    - Docker Compose substitutions (``docker-compose.yml``), which are read by
      Compose itself and are not application settings at all.

    Anything outside all three is genuinely unknown and still fails.
    """
    known = {field.upper() for field in Settings.model_fields}

    try:
        from settings import Settings as FrontendSettings  # noqa: PLC0415

        known |= {field.upper() for field in FrontendSettings.model_fields}
    except ImportError:  # pragma: no cover - frontend always present in-repo
        pass

    known |= _compose_variable_names()
    return known


def _compose_variable_names() -> set[str]:
    """Names substituted by docker-compose.yml via ``${NAME}``.

    Returned from the Compose file itself rather than hard-coded, so the
    contract tracks the real deployment definition.
    """
    if not COMPOSE_FILE.is_file():  # pragma: no cover - compose always present
        return set()
    return set(re.findall(r"\$\{([A-Z][A-Z0-9_]*)[:}]", COMPOSE_FILE.read_text(encoding="utf-8")))


def test_active_keys_are_known_settings() -> None:
    known = _known_setting_names()
    unknown = set(read_active_entries()) - known
    assert not unknown, f"template documents unknown settings: {sorted(unknown)}"


def test_compose_variables_are_documented() -> None:
    # The reverse direction: a Compose variable absent from the template is a
    # missing instruction for anyone starting the stack.
    template_keys = set(read_active_entries())
    missing = _compose_variable_names() - template_keys
    assert not missing, f"docker-compose.yml uses undocumented variables: {sorted(missing)}"


def test_unknown_keys_are_still_rejected() -> None:
    # Guards the guard: the known-name set must not be unbounded.
    assert "SOME_UNRELATED_VARIABLE" not in _known_setting_names()


def test_active_secrets_use_placeholders() -> None:
    # Any active key that holds a credential must carry a visible placeholder.
    secret_keys = {"JWT_SECRET", "DATABASE_URL"}
    for key, value in read_active_entries().items():
        if key in secret_keys:
            assert "CHANGE_ME" in value, f"{key} must use a CHANGE_ME placeholder"


@pytest.mark.parametrize("key", ["DATABASE_URL", "JWT_SECRET", "BACKEND_API_URL"])
def test_implemented_settings_are_active(key: str) -> None:
    # The database, auth and frontend settings are all in use, so they must be
    # present in the template rather than commented out.
    assert key in read_active_entries()
