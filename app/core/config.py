"""
Core configuration module.

Loads application settings from environment variables.
All runtime-sensitive values come from the environment — never hardcode secrets.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    APP_NAME: str = "Reach Developments Station"
    APP_ENV: str = "development"
    APP_DEBUG: bool = False
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    DATABASE_URL: str = "postgresql://user:pass@localhost:5432/reach_developments"

    LOG_LEVEL: str = "INFO"

    API_V1_PREFIX: str = "/api/v1"


settings = Settings()
