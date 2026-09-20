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
from psycopg import Connection
from sqlalchemy import Engine, event, text
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


@pytest.fixture
def connection_lifecycle() -> Iterator[None]:
    """Attribute leaked connections to their owning test, not later garbage collection."""
    opened: list[Connection] = []

    def remember(connection: Connection, record: object) -> None:
        opened.append(connection)

    event.listen(Engine, "connect", remember)
    try:
        yield
    finally:
        event.remove(Engine, "connect", remember)
        leaked = [connection for connection in opened if not connection.closed]
        # Fail before losing the references; closing here only prevents a second,
        # misleading destructor warning from surfacing in an unrelated test.
        for connection in leaked:
            connection.close()
        assert not leaked, f"{len(leaked)} PostgreSQL connections left open after test cleanup"


@pytest.fixture(autouse=True)
def isolated_configuration(
    monkeypatch: pytest.MonkeyPatch, connection_lifecycle: None
) -> Iterator[None]:
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
    "ue_current_cost_settings",
    # Retained reporting documents require privileged test lifecycle cleanup.
    # Do not rely on their foreign keys making an unrelated TRUNCATE cascade to
    # them: migration tests must start with no retained history. TRUNCATE is
    # confined to this throwaway database fixture, never an application bypass.
    "management_report_snapshot_projects",
    "management_report_snapshots",
    "unit_stage_events",
    "construction_stages",
    "audit_events",
    "installment_trigger_events",
    "payment_plan_installments",
    "payment_plan_versions",
    "payment_plans",
    "user_sessions",
    "user_roles",
    "unit_custom_field_values",
    "land_parcel_custom_field_values",
    "project_custom_field_values",
    "custom_field_options",
    "custom_field_definitions",
    "handover_clearances",
    "handover_records",
    "sale_cancellations",
    "sale_legal_events",
    "sale_contract_tax_lines",
    "sale_contract_parties",
    "sale_contracts",
    "reservation_status_events",
    "reservation_adjustments",
    "reservations",
    "client_parties",
    "clients",
    "sales_project_policies",
    "unit_features",
    "unit_documents",
    "unit_status_events",
    "unit_area_values",
    "unit_area_schedules",
    "inventory_common_areas",
    "technical_specifications",
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


#: Which of the data tables actually hold a row, answered in one round trip.
#:
#: ``TRUNCATE`` costs roughly the same whether a table has a million rows or
#: none: it takes a lock and rewrites the file. Naming all fifty-six of them
#: therefore cost about 0.8 of a second per test whatever the test did, and
#: with three and a half thousand tests that is most of an hour of CI spent
#: emptying tables that were already empty. A typical test touches a handful.
#:
#: Asking first costs about a millisecond, because every branch is an
#: ``EXISTS`` that stops at the first row.
_OCCUPIED_TABLES = text(
    " UNION ALL ".join(
        f"SELECT '{table}' AS occupied WHERE EXISTS (SELECT 1 FROM {table})"
        for table in _DATA_TABLES
    )
)


@pytest.fixture(autouse=True)
def clean_database(migrated_schema: None, isolated_configuration: None) -> None:
    """Empty every data table before each test.

    The guarantee is unchanged — no test begins with another test's rows — and
    so is the mechanism where it matters: one statement, so foreign keys
    between the tables are not an ordering problem, and seeded roles survive.
    What changed is that the statement names only the tables that have
    something in them.

    ``RESTART IDENTITY`` stays although this schema has no sequences at all —
    every key is a UUID — so it is a no-op today and a correct instruction on
    the day someone adds one. That is also why skipping an empty table is safe:
    with nothing to restart, an empty table and a truncated one are the same
    table.

    ``CASCADE`` reaches no further than before. It follows references INTO what
    is named, and a subset of these tables can only be referenced by a subset
    of what the whole list could reach — so anything the old statement spared,
    including the seeded roles, this one spares too.
    """
    empty_data_tables()


def empty_data_tables() -> list[str]:
    """Empty the data tables that hold anything; report which those were.

    Separate from the fixture so the guarantee can be tested directly rather
    than inferred from tests that happen to pass.
    """
    engine = get_engine()
    with engine.begin() as connection:
        occupied = [row[0] for row in connection.execute(_OCCUPIED_TABLES)]
        if occupied:
            connection.execute(text(f"TRUNCATE {', '.join(occupied)} RESTART IDENTITY CASCADE"))
    return occupied


@pytest.fixture
def db() -> Iterator[Session]:
    """A database session for arranging test state directly."""
    # A TestClient lifespan or migration can dispose the cached engine before
    # this fixture tears down. A checked-out connection survives that disposal;
    # Session.close() then returns it to the old pool, not the replacement pool.
    # Retain ownership so the old pool is closed after its session returns.
    engine = get_engine()
    pool = engine.pool
    session = get_session_factory()()
    try:
        yield session
    finally:
        try:
            session.close()
        finally:
            pool.dispose()
            # The session still binds its original Engine after the global cache
            # is cleared. Reusing it opens a replacement pool on that uncached
            # engine, which the global configuration reset cannot reach.
            engine.dispose()
