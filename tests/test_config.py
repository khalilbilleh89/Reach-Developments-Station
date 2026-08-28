"""Configuration contract and database URL normalisation."""

from __future__ import annotations

import pytest

from app.core.config import DEV_DATABASE_URL, Settings, normalize_database_url


def test_defaults_describe_the_service() -> None:
    """Given no overrides, then the documented development defaults apply."""
    settings = Settings(DATABASE_URL=DEV_DATABASE_URL)

    assert settings.APP_NAME == "reach-developments-station"
    assert settings.APP_ENV == "development"
    assert settings.APP_DEBUG is False
    assert settings.API_V1_PREFIX == "/api/v1"


def test_development_falls_back_to_the_local_database() -> None:
    """Given no DATABASE_URL outside production, then the local default is used."""
    settings = Settings(APP_ENV="development", DATABASE_URL="")

    assert settings.DATABASE_URL == DEV_DATABASE_URL


def test_production_requires_an_explicit_database_url() -> None:
    """Given production without DATABASE_URL, then startup configuration fails."""
    with pytest.raises(ValueError, match="DATABASE_URL must be set"):
        Settings(APP_ENV="production", DATABASE_URL="")


def test_production_forbids_debug_mode() -> None:
    """Given production with debug enabled, then startup configuration fails."""
    with pytest.raises(ValueError, match="APP_DEBUG must be false"):
        Settings(
            APP_ENV="production",
            APP_DEBUG=True,
            DATABASE_URL="postgresql://user:pw@db.internal:5432/reach",
        )


def test_production_accepts_a_render_style_database_url() -> None:
    """Given a Render PostgreSQL URL in production, then configuration succeeds."""
    settings = Settings(
        APP_ENV="production",
        DATABASE_URL="postgres://reach_user:pw@dpg-internal:5432/reach",
    )

    assert settings.is_production is True
    assert settings.sqlalchemy_database_url.drivername == "postgresql+psycopg"


@pytest.mark.parametrize(
    "raw_url",
    [
        "postgres://user:pw@host:5432/reach",
        "postgresql://user:pw@host:5432/reach",
        "postgresql+psycopg://user:pw@host:5432/reach",
    ],
)
def test_supported_postgresql_urls_normalise_to_psycopg(raw_url: str) -> None:
    """Given any supported PostgreSQL scheme, then it resolves to the Psycopg 3 driver."""
    assert normalize_database_url(raw_url).drivername == "postgresql+psycopg"


def test_normalisation_preserves_every_url_component() -> None:
    """Given credentials that contain 'postgres', then naive string replacement is ruled out."""
    url = normalize_database_url("postgres://postgres:postgresql@postgres-db.example:5433/postgres")

    assert url.drivername == "postgresql+psycopg"
    assert url.username == "postgres"
    assert url.password == "postgresql"
    assert url.host == "postgres-db.example"
    assert url.port == 5433
    assert url.database == "postgres"


def test_non_postgresql_backends_are_rejected() -> None:
    """Given a non-PostgreSQL URL, then configuration refuses it."""
    with pytest.raises(ValueError, match="Unsupported database backend"):
        normalize_database_url("mysql://user:pw@host:3306/reach")


def test_other_postgresql_drivers_are_rejected() -> None:
    """Given a driver that is not installed, then configuration refuses it loudly."""
    with pytest.raises(ValueError, match="Unsupported PostgreSQL driver"):
        normalize_database_url("postgresql+psycopg2://user:pw@host:5432/reach")


def test_malformed_database_urls_fail_at_startup() -> None:
    """Given an unparseable URL, then Settings construction fails rather than a request."""
    with pytest.raises(ValueError):
        Settings(DATABASE_URL="not-a-database-url")


def test_safe_database_url_redacts_the_password() -> None:
    """Given a log-bound summary, then the password is never rendered."""
    settings = Settings(DATABASE_URL="postgres://reach_user:sup3rs3cret@host:5432/reach")

    assert "sup3rs3cret" not in settings.safe_database_url
    assert settings.safe_database_url.startswith("postgresql+psycopg://reach_user:")


@pytest.mark.parametrize("prefix", ["api/v1", "/api/v1/", ""])
def test_api_prefix_must_be_a_rooted_path(prefix: str) -> None:
    """Given a malformed API prefix, then configuration refuses it."""
    with pytest.raises(ValueError, match="API_V1_PREFIX"):
        Settings(API_V1_PREFIX=prefix, DATABASE_URL=DEV_DATABASE_URL)
