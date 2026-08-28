"""Configuration contract and database URL normalisation.

These tests assert what the code does, never what the developer's shell or CI
job happens to export. Every ``Settings`` here is built from explicit values
with the ambient environment and ``.env`` removed.
"""

from __future__ import annotations

import traceback

import pytest

from app.core.config import DEV_DATABASE_URL, Settings, get_settings, normalize_database_url

CONFIG_ENV_VARS = ("APP_NAME", "APP_ENV", "APP_DEBUG", "DATABASE_URL", "API_V1_PREFIX")


@pytest.fixture(autouse=True)
def bare_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove every configuration variable this module reasons about."""
    for name in CONFIG_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def build_settings(**overrides: object) -> Settings:
    """Construct Settings from explicit values only, ignoring any .env file."""
    return Settings(_env_file=None, **overrides)


def test_defaults_describe_the_service() -> None:
    """Given a bare environment, then the documented development defaults apply."""
    settings = build_settings()

    assert settings.APP_NAME == "reach-developments-station"
    assert settings.APP_ENV == "development"
    assert settings.APP_DEBUG is False
    assert settings.API_V1_PREFIX == "/api/v1"
    assert settings.DATABASE_URL == DEV_DATABASE_URL


def test_development_falls_back_to_the_local_database() -> None:
    """Given no DATABASE_URL outside production, then the local default is used."""
    settings = build_settings(APP_ENV="development", DATABASE_URL="")

    assert settings.DATABASE_URL == DEV_DATABASE_URL


def test_production_requires_an_explicit_database_url() -> None:
    """Given production without DATABASE_URL, then startup configuration fails."""
    with pytest.raises(ValueError, match="DATABASE_URL must be set"):
        build_settings(APP_ENV="production", DATABASE_URL="")


def test_production_forbids_debug_mode() -> None:
    """Given production with debug enabled, then startup configuration fails."""
    with pytest.raises(ValueError, match="APP_DEBUG must be false"):
        build_settings(
            APP_ENV="production",
            APP_DEBUG=True,
            DATABASE_URL="postgresql://user:pw@db.internal:5432/reach",
        )


def test_production_accepts_a_render_style_database_url() -> None:
    """Given a Render PostgreSQL URL in production, then configuration succeeds."""
    settings = build_settings(
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


@pytest.mark.parametrize(
    "raw_url",
    [
        "POSTGRES://user:pw@host:5432/reach",
        "PostgreSQL+PsycoPG://user:pw@host:5432/reach",
    ],
)
def test_url_schemes_are_case_insensitive(raw_url: str) -> None:
    """Given an upper-cased scheme, then it is accepted (RFC 3986 section 3.1)."""
    assert normalize_database_url(raw_url).drivername == "postgresql+psycopg"


def test_normalisation_preserves_connection_query_parameters() -> None:
    """Given Render-style options such as sslmode, then they survive normalisation."""
    url = normalize_database_url("postgres://user:pw@host:5432/reach?sslmode=require")

    assert url.drivername == "postgresql+psycopg"
    assert url.query["sslmode"] == "require"


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
        build_settings(DATABASE_URL="not-a-database-url")


def test_safe_database_url_redacts_the_password() -> None:
    """Given a log-bound summary, then the password is never rendered."""
    settings = build_settings(DATABASE_URL="postgres://reach_user:sup3rs3cret@host:5432/reach")

    assert "sup3rs3cret" not in settings.safe_database_url
    assert settings.safe_database_url.startswith("postgresql+psycopg://reach_user:")


@pytest.mark.parametrize("prefix", ["api/v1", "/api/v1/", ""])
def test_api_prefix_must_be_a_rooted_path(prefix: str) -> None:
    """Given a malformed API prefix, then configuration refuses it."""
    with pytest.raises(ValueError, match="API_V1_PREFIX"):
        build_settings(API_V1_PREFIX=prefix)


def test_configuration_errors_never_echo_the_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Given an invalid DATABASE_URL, then nothing rendered from the error carries it.

    Pydantic reports the offending input inside its own ValidationError. Left
    alone, a startup failure would therefore write a live connection string —
    password included — straight into the deploy log.
    """
    secret = "sup3rs3cret-do-not-log"
    monkeypatch.setenv("DATABASE_URL", f"mysql://reach_user:{secret}@db.internal:3306/reach")
    get_settings.cache_clear()

    with pytest.raises(RuntimeError) as raised:
        get_settings()

    error = raised.value
    # What a logger actually renders: the message, plus the chained causes it
    # would follow. Frame source is excluded — this file contains the literal.
    rendered = "".join(traceback.format_exception_only(type(error), error))

    assert secret not in rendered
    assert "reach_user" not in rendered
    assert "Invalid application configuration" in rendered
    assert "Unsupported database backend" in rendered
    # `raise ... from None` — the pydantic error is never chained into the output.
    assert error.__cause__ is None
    assert error.__suppress_context__ is True


def test_safe_database_url_redacts_a_password_given_as_a_query_parameter() -> None:
    """Given libpq's query-parameter password form, then it is redacted too.

    SQLAlchemy's ``hide_password`` masks only the userinfo password, so this
    otherwise reaches the deploy log in cleartext.
    """
    secret = "R3nd3rSecret"
    settings = build_settings(
        DATABASE_URL=f"postgresql://reach_user@dpg-abc.render.com:5432/reach?password={secret}"
    )

    assert secret not in settings.safe_database_url
    assert "reach_user" in settings.safe_database_url
