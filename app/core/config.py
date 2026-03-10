"""
Core configuration module.

Loads application settings from environment variables.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "Reach Developments Station"
    debug: bool = False
    database_url: str = "postgresql+asyncpg://localhost/reach_developments"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60 * 8  # 8 hours

    class Config:
        env_file = ".env"


settings = Settings()
