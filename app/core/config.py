"""Environment-driven application configuration.

This module is the single place where the process learns what it is and which
database it talks to. Nothing else in the codebase reads ``os.environ`` and
nothing else rewrites database URL schemes.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

AppEnv = Literal["development", "test", "staging", "production"]

#: Convenience default used for local development and CI only. Production must
#: always supply ``DATABASE_URL`` explicitly.
DEV_DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/reach_station"

#: Query keys libpq accepts as a password. SQLAlchemy's ``hide_password`` masks
#: only the userinfo password, so these would otherwise be logged in cleartext.
_CREDENTIAL_QUERY_KEYS = frozenset({"password", "sslpassword"})

#: The only PostgreSQL driver this application ships (Psycopg 3).
_SUPPORTED_DRIVER = "psycopg"
_SUPPORTED_BACKENDS = frozenset({"postgres", "postgresql"})


def normalize_database_url(raw_url: str) -> URL:
    """Return ``raw_url`` as a SQLAlchemy URL bound to the Psycopg 3 driver.

    Render exposes PostgreSQL connection strings as ``postgres://…`` or
    ``postgresql://…``. SQLAlchemy 2.x needs an explicit driver, so the scheme is
    normalised here — centrally — instead of by ad-hoc string replacement at
    each call site.

    Raises:
        ValueError: if the URL is unparseable, is not a PostgreSQL URL, or names
            a PostgreSQL driver other than Psycopg 3.
    """
    try:
        url = make_url(raw_url)
    except ArgumentError as exc:  # pragma: no cover - exercised via Settings
        raise ValueError("DATABASE_URL is not a valid database URL.") from exc

    # URI schemes are case-insensitive (RFC 3986 section 3.1).
    backend, _, driver = url.drivername.lower().partition("+")
    if backend not in _SUPPORTED_BACKENDS:
        raise ValueError(
            f"Unsupported database backend '{backend}'. "
            "Reach Developments Station runs on PostgreSQL only."
        )
    if driver and driver != _SUPPORTED_DRIVER:
        raise ValueError(
            f"Unsupported PostgreSQL driver '{driver}'. "
            f"Only '{_SUPPORTED_DRIVER}' (Psycopg 3) is installed."
        )
    return url.set(drivername=f"postgresql+{_SUPPORTED_DRIVER}")


class Settings(BaseSettings):
    """Runtime configuration, read from the environment and optionally ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    APP_NAME: str = "reach-developments-station"
    APP_ENV: AppEnv = "development"
    APP_DEBUG: bool = False
    DATABASE_URL: str = ""
    API_V1_PREFIX: str = "/api/v1"

    @field_validator("API_V1_PREFIX")
    @classmethod
    def _validate_api_prefix(cls, value: str) -> str:
        if not value.startswith("/") or value.endswith("/"):
            raise ValueError("API_V1_PREFIX must start with '/' and must not end with '/'.")
        return value

    @model_validator(mode="after")
    def _apply_environment_policy(self) -> Settings:
        if not self.DATABASE_URL:
            if self.APP_ENV == "production":
                raise ValueError("DATABASE_URL must be set when APP_ENV=production.")
            self.DATABASE_URL = DEV_DATABASE_URL

        if self.APP_ENV == "production" and self.APP_DEBUG:
            raise ValueError("APP_DEBUG must be false when APP_ENV=production.")

        # Fail fast at startup rather than at the first database request.
        normalize_database_url(self.DATABASE_URL)
        return self

    @property
    def is_production(self) -> bool:
        """Whether this process is running under production rules."""
        return self.APP_ENV == "production"

    @property
    def sqlalchemy_database_url(self) -> URL:
        """The canonical Psycopg 3 URL handed to :func:`sqlalchemy.create_engine`."""
        return normalize_database_url(self.DATABASE_URL)

    @property
    def safe_database_url(self) -> str:
        """Password-redacted connection target, safe for server-side logs.

        Never return this to an HTTP client — it still names the host and user.
        """
        url = self.sqlalchemy_database_url
        if url.query:
            url = url.set(
                query={
                    key: ("***" if key in _CREDENTIAL_QUERY_KEYS else value)
                    for key, value in url.query.items()
                }
            )
        return url.render_as_string(hide_password=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings instance.

    Cached so that configuration is parsed and validated exactly once. Tests that
    change the environment must call ``get_settings.cache_clear()``.

    Raises:
        RuntimeError: if configuration is invalid. Pydantic echoes the offending
            input into its own error, which would put a live ``DATABASE_URL`` —
            password and all — into the deploy log. The error is re-raised here
            with the field names and reasons only, and ``from None`` keeps the
            original values out of the traceback.
    """
    try:
        return Settings()
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in error['loc']) or 'configuration'}: {error['msg']}"
            for error in exc.errors()
        )
        raise RuntimeError(f"Invalid application configuration. {problems}") from None
