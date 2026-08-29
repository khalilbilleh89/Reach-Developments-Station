"""Shared test fixtures.

The suite pins its own configuration so that a developer's shell, a stray
``.env`` file or a CI job's environment cannot change what the tests assert.
``DATABASE_URL`` is the single intentional external input: it must point at a
reachable throwaway PostgreSQL database.

Applications under test are built through :func:`app.main.create_app` rather
than the module-level instance, so each test sees the configuration pinned
below instead of whatever was in scope at import time.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import (
    check_database_connection,
    dispose_engine,
    get_engine,
    get_session_factory,
)
from app.main import create_app

PINNED_TEST_CONFIG = {
    "APP_NAME": "reach-developments-station",
    "APP_ENV": "test",
    "APP_DEBUG": "false",
    "API_V1_PREFIX": "/api/v1",
}

#: A deliberately unroutable PostgreSQL target with distinctive credentials, so
#: that leak assertions have something unmistakable to look for.
UNREACHABLE_DATABASE_URL = (
    "postgresql+psycopg://probe_user:pr0be-s3cret@127.0.0.1:59999/probe_database"
)
UNREACHABLE_DATABASE_SECRETS = (
    "probe_user",
    "pr0be-s3cret",
    "59999",
    "probe_database",
)


def _reset_configuration() -> None:
    get_settings.cache_clear()
    dispose_engine()


@pytest.fixture(autouse=True)
def isolated_configuration(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Pin configuration and clear cached settings and engine around every test."""
    for name, value in PINNED_TEST_CONFIG.items():
        monkeypatch.setenv(name, value)
    _reset_configuration()
    yield
    _reset_configuration()


@pytest.fixture
def client() -> Iterator[TestClient]:
    """An HTTP client bound to a freshly built application."""
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def postgres() -> None:
    """Require a reachable test database.

    Fails rather than skips: a silently skipped database test in CI is worse
    than a red build.
    """
    try:
        check_database_connection()
    except SQLAlchemyError as exc:
        pytest.fail(
            "This test requires PostgreSQL. Point DATABASE_URL at a reachable test "
            f"database before running pytest (got {type(exc).__name__})."
        )


# --------------------------------------------------------------------------- #
# Governance schema and data isolation
# --------------------------------------------------------------------------- #

#: Emptied before every test. `roles` is excluded: it is seeded by migration and
#: is reference data, not test state.
_DATA_TABLES = (
    "audit_events",
    "user_sessions",
    "user_roles",
    "unit_custom_field_values",
    "land_parcel_custom_field_values",
    "project_custom_field_values",
    "custom_field_options",
    "custom_field_definitions",
    "unit_status_events",
    "unit_area_values",
    "unit_area_schedules",
    "inventory_sub_assets",
    "units",
    "floors",
    "buildings",
    "user_phase_access",
    "phases",
    "area_types",
    "document_references",
    "permit_status_events",
    "permits",
    "planning_controls",
    "land_parcels",
    "user_project_access",
    "projects",
    "users",
    "country_approval_thresholds",
    "tax_rules",
    "reference_values",
    "country_packs",
    "currencies",
)


def alembic_config() -> Config:
    """Alembic configuration pointed at this repository."""
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "app" / "db" / "migrations"))
    return config


@pytest.fixture(scope="session", autouse=True)
def migrated_schema() -> None:
    """Bring the test database to head once for the whole session."""
    command.upgrade(alembic_config(), "head")


@pytest.fixture(autouse=True)
def clean_database(migrated_schema: None, isolated_configuration: None) -> None:
    """Empty every data table before each test.

    One TRUNCATE covers all of them, so foreign keys between them are not an
    ordering problem. Seeded roles survive.
    """
    engine = get_engine()
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {', '.join(_DATA_TABLES)} RESTART IDENTITY CASCADE"))


@pytest.fixture
def db() -> Iterator[Session]:
    """A database session for arranging test state directly."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
