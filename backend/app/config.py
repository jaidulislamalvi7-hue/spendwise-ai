"""Typed application settings loaded from environment variables.

Values are read from process environment variables and, for local development,
from the project-root ``.env`` file. Environment variables take precedence.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root (<repo>/backend/app/config.py -> <repo>). Used so the .env file is
# found regardless of the working directory the process is started from.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Environment-backed configuration for the backend."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "SpendWise AI"
    app_env: Literal["development", "staging", "production"] = "development"

    # Database (Batch 2). Read from DATABASE_URL; there is deliberately no
    # functional default, so a missing configuration fails loudly instead of
    # silently pointing at a database that does not exist.
    database_url: str = Field(
        default="postgresql+psycopg://postgres:CHANGE_ME@localhost:5432/spendwise_db"
    )

    # Authentication (Batch 3). The secret must be provided outside production.
    # SecretStr keeps the value out of repr output and accidental logging.
    jwt_secret: SecretStr = SecretStr("CHANGE_ME_GENERATE_A_RANDOM_SECRET")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(default=60, gt=0, le=1440)

    # CORS. Empty by default: the Streamlit server calls the API server-side, so
    # no browser origin is involved. Set a comma-separated list only if a
    # browser client calls this API directly. Never use "*" with credentials.
    cors_allow_origins: str = ""

    # Logging: DEBUG | INFO | WARNING | ERROR
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @property
    def cors_origins(self) -> list[str]:
        """Parsed list of allowed origins (empty means CORS is not enabled)."""
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]

    @field_validator("cors_allow_origins")
    @classmethod
    def _reject_wildcard(cls, value: str) -> str:
        if "*" in value:
            raise ValueError(
                "cors_allow_origins must list explicit origins; a wildcard would "
                "let any site call the API."
            )
        return value

    @field_validator("jwt_algorithm")
    @classmethod
    def _only_hmac_algorithms(cls, value: str) -> str:
        # Restricting to HMAC prevents algorithm-confusion attacks with symmetric secrets.
        if not value.upper().startswith("HS"):
            raise ValueError("jwt_algorithm must be an HMAC algorithm (HS256/HS384/HS512)")
        return value

    @field_validator("jwt_secret")
    @classmethod
    def _reject_placeholder_outside_development(cls, value: SecretStr, info):
        env = info.data.get("app_env", "development")
        if env != "development" and "CHANGE_ME" in value.get_secret_value():
            raise ValueError("JWT_SECRET must be set to a real random value outside development")
        return value


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance read from the environment."""
    return Settings()


def get_jwt_secret() -> str:
    """Return the JWT signing secret, refusing the development placeholder."""
    secret = get_settings().jwt_secret.get_secret_value()
    if "CHANGE_ME" in secret:
        raise RuntimeError(
            "JWT_SECRET is still the placeholder value. Set a real secret "
            '(python -c "import secrets; print(secrets.token_urlsafe(32))").'
        )
    return secret


def get_database_url() -> str:
    """Return the configured database URL, rejecting the template placeholder.

    Raises a clear error rather than letting SQLAlchemy attempt a connection
    with an obviously unconfigured password.
    """
    url = get_settings().database_url
    if "CHANGE_ME" in url:
        raise RuntimeError(
            "DATABASE_URL is still the template placeholder. Create .env from "
            ".env.example and replace CHANGE_ME with your PostgreSQL password."
        )
    return url
