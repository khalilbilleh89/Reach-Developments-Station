"""
Core configuration module.

Loads application settings from environment variables.
All runtime-sensitive values come from the environment — never hardcode secrets.
"""

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_SECRET = "change-me-in-production-use-a-long-random-secret"


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

    # JWT settings
    # SECRET_KEY must be overridden in production via the SECRET_KEY environment variable.
    # A short default is provided for local development only.
    SECRET_KEY: str = _DEFAULT_SECRET
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    @model_validator(mode="after")
    def _reject_default_secret_in_production(self) -> "Settings":
        if (self.APP_ENV or "").lower() == "production" and self.SECRET_KEY == _DEFAULT_SECRET:
            raise ValueError(
                "SECRET_KEY must be overridden in production. "
                "Set the SECRET_KEY environment variable to a strong random value."
            )
        return self


settings = Settings()
