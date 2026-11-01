"""Environment-backed configuration for the frontend."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Backend connection settings for the Streamlit app."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    backend_api_url: str = "http://localhost:8000"


def get_settings() -> Settings:
    """Return a Settings instance read from the environment."""
    return Settings()
