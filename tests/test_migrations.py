"""Alembic history behaviour against PostgreSQL.

PR-MVP-00 promises a fresh migration history whose baseline creates no business
schema and reverses cleanly. Everything after it promises something narrower and
harder: that the path an *already-deployed* database takes produces the same
schema as a fresh install.

That distinction is the point of the revision-path tests at the bottom of this
file. A migration test that only ever runs `empty -> head` cannot tell a
correction appended as a new revision from the same correction edited into a
revision that has already shipped: both leave a fresh database right, and only
one of them repairs a database that is already running.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.core.database import get_engine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASELINE_REVISION = "0000_mvp_baseline"
HEAD_REVISION = "0010_construction_source_kind"

#: The revision that shipped ``unit_economics_cost_pools`` wide enough to hold
#: ``construction_forecast`` while its CHECK still listed two sources, and the
#: revision that corrects it. Named because the tests below assert what each
#: one leaves behind, not merely that the history runs.
CONSTRUCTION_REVISION = "0009_construction"
SOURCE_KIND_REVISION = "0010_construction_source_kind"

#: The CHECK under test, and the row that distinguishes the two enumerations.
SOURCE_CONSTRAINT = "ck_unit_economics_cost_pools_source_ok"
_CONSTRUCTION_POOL = (
    "INSERT INTO unit_economics_cost_pools "
    "(id, project_id, allocation_version_id, pool_number, name, category, "
    " source_kind, amount, scope_kind, allocation_method, created_by_user_id, "
    " source_construction_forecast_version_id) "
    "VALUES (gen_random_uuid(), gen_random_uuid(), gen_random_uuid(), 'CX', 'CX', "
    " 'hard', 'construction_forecast', 1, 'project', 'unit_count', "
    " gen_random_uuid(), gen_random_uuid())"
)


def _alembic_config() -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "app" / "db" / "migrations"))
    return config


def _current_revision() -> str | None:
    with get_engine().connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def _public_tables() -> set[str]:
    with get_engine().connect() as connection:
        rows = connection.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        return {row[0] for row in rows}


@pytest.fixture
def empty_database(postgres: None) -> None:
    """Reverse every migration so the next upgrade genuinely executes.

    Without this, a database already stamped at head makes ``upgrade()`` a no-op,
    and any assertion about what the migration produced would pass no matter what
    the revision actually contains.
    """
    command.downgrade(_alembic_config(), "base")


def test_the_history_round_trips_from_empty_to_head_and_back(postgres: None) -> None:
    """Given PostgreSQL, when every revision is applied and reversed, then it round-trips."""
    config = _alembic_config()

    command.upgrade(config, "head")
    assert _current_revision() == HEAD_REVISION

    command.downgrade(config, "base")
    assert _current_revision() is None

    command.upgrade(config, "head")
    assert _current_revision() == HEAD_REVISION


def test_baseline_creates_no_business_schema(empty_database: None) -> None:
    """Given an empty database, when the baseline is applied, then it adds no tables.

    Targets the baseline revision by name rather than ``head``: the point is
    what *this* revision does, and that must stay true as later revisions land.

    The fixture guarantees the upgrade really runs, so this measures the
    revision's own effect rather than whatever was already in the database. The
    assertion is on the delta, so an unrelated table left in a developer's test
    database is reported as such instead of being blamed on the migration.
    """
    before = _public_tables()

    command.upgrade(_alembic_config(), BASELINE_REVISION)

    created = _public_tables() - before
    assert created <= {"alembic_version"}, (
        f"the baseline migration created business tables: {sorted(created)}"
    )
    assert "alembic_version" in _public_tables()

    # Restore head so the rest of the suite still has its schema.
    command.upgrade(_alembic_config(), "head")


def test_baseline_is_the_single_root_of_the_migration_history(postgres: None) -> None:
    """Given the new history, then the baseline is its only root revision."""
    script = ScriptDirectory.from_config(_alembic_config())
    revisions = list(script.walk_revisions())

    assert [revision.revision for revision in revisions if revision.down_revision is None] == [
        BASELINE_REVISION
    ]


# --------------------------------------------------------------------------- #
# The corrective revision, 0009 -> 0010
# --------------------------------------------------------------------------- #


def _source_constraint_expression() -> str:
    """The CHECK's expression as PostgreSQL now holds it.

    Read from the catalogue rather than inferred from a failed insert. An
    assertion that merely says "some integrity error occurred" passes when the
    *wrong* constraint refuses the row, which is exactly how the two-value
    enumeration survived a test suite once already.
    """
    with get_engine().connect() as connection:
        return connection.execute(
            text("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = :name"),
            {"name": SOURCE_CONSTRAINT},
        ).scalar_one()


def _refusal_for_a_construction_pool() -> str | None:
    """Which constraint refuses a construction-sourced pool, or ``None``.

    The row names a project, a version, a user and a forecast that do not
    exist, so once the source enumeration admits it the insert still fails — on
    a foreign key. That is the signal: the enumeration is no longer the thing
    standing in the way.
    """
    with get_engine().connect() as connection:
        try:
            connection.execute(text(_CONSTRUCTION_POOL))
        except Exception as caught:
            message = str(caught)
            for name in (SOURCE_CONSTRAINT, "cx_source_shape", "cx_provenance_shape"):
                if name in message:
                    return name
            return "foreign key" if "foreign key" in message else "other"
        return None


def _seed_a_construction_sourced_pool() -> None:
    """One cost pool genuinely sourced from a construction forecast.

    Every parent the row's foreign keys name is created for real — a currency, a
    country pack, a user, a project, an allocation version, a budget version and
    a forecast version — because the point of the test is the *downgrade guard*,
    and a row that failed a foreign key instead would prove nothing about it.

    Raw SQL rather than the ORM: this file drives Alembic between revisions, so
    the schema it is talking to is deliberately not the one the models describe.
    """
    with get_engine().begin() as connection:
        connection.execute(
            text(
                """
                WITH currency AS (
                  INSERT INTO currencies (id, code, name, minor_units, is_active)
                  VALUES (gen_random_uuid(), 'ZZZ', 'Test currency', 2, true)
                  RETURNING id
                ), pack AS (
                  INSERT INTO country_packs (
                    id, country_code, name, locale, timezone, default_currency_id,
                    area_unit, fiscal_year_start_month, is_active)
                  SELECT gen_random_uuid(), 'ZZ', 'Test pack', 'en-ZZ', 'UTC', currency.id,
                         'sqm', 1, true
                  FROM currency
                  RETURNING id
                ), operator AS (
                  INSERT INTO users (
                    id, email, email_normalized, display_name, password_hash,
                    is_active, must_change_password)
                  VALUES (gen_random_uuid(), 'migration@example.com',
                          'migration@example.com', 'Migration', 'x', true, false)
                  RETURNING id
                ), project AS (
                  INSERT INTO projects (
                    id, code, name, developer_entity, country_pack_id, status,
                    base_currency_id, reporting_currency_id, fiscal_year_start_month,
                    created_by_user_id)
                  SELECT gen_random_uuid(), 'MIG-01', 'Migration project', 'Reach',
                         pack.id, 'predevelopment', currency.id, currency.id, 1,
                         operator.id
                  FROM pack, currency, operator
                  RETURNING id, base_currency_id, created_by_user_id
                ), basis AS (
                  INSERT INTO unit_economics_allocation_versions (
                    id, project_id, version_number, currency_id, status,
                    finance_treatment, effective_from, change_reason, created_by_user_id)
                  SELECT gen_random_uuid(), project.id, 1, project.base_currency_id,
                         'draft', 'excluded', DATE '2026-01-01', 'Migration test',
                         project.created_by_user_id
                  FROM project
                  RETURNING id, project_id
                ), budget AS (
                  INSERT INTO construction_budget_versions (
                    id, project_id, version_number, currency_id, status,
                    effective_date, change_reason, created_by_user_id)
                  SELECT gen_random_uuid(), project.id, 1, project.base_currency_id,
                         'draft', DATE '2026-01-01', 'Migration test',
                         project.created_by_user_id
                  FROM project
                  RETURNING id, project_id
                ), forecast AS (
                  INSERT INTO construction_forecast_versions (
                    id, project_id, version_number, currency_id, budget_version_id,
                    as_of_date, status, change_reason, created_by_user_id)
                  SELECT gen_random_uuid(), project.id, 1, project.base_currency_id,
                         budget.id, DATE '2026-01-31', 'draft', 'Migration test',
                         project.created_by_user_id
                  FROM project, budget
                  RETURNING id, project_id
                )
                INSERT INTO unit_economics_cost_pools (
                  id, project_id, allocation_version_id, pool_number, name, category,
                  source_kind, amount, scope_kind, allocation_method,
                  created_by_user_id, source_construction_forecast_version_id)
                SELECT gen_random_uuid(), project.id, basis.id, 'HARD-CX',
                       'Construction hard cost', 'hard', 'construction_forecast',
                       1000, 'project', 'unit_count', project.created_by_user_id,
                       forecast.id
                FROM project, basis, forecast
                """
            )
        )


@pytest.fixture
def at_construction_revision(postgres: None) -> Iterator[None]:
    """A database standing exactly where a deployed one stands today.

    Downgrades to base first so the upgrade genuinely executes, then stops at
    0009 — the revision that has already been applied in production. Restores
    head afterwards so the rest of the suite keeps its schema.
    """
    config = _alembic_config()
    command.downgrade(config, "base")
    command.upgrade(config, CONSTRUCTION_REVISION)
    yield
    command.upgrade(config, "head")


class TestTheSourceEnumerationIsCorrectedByARevision:
    """The deployed path, proved as a path rather than as an end state.

    Each of these would pass if 0009 had simply been rewritten. Only the first
    would also pass if the correction had been rewritten *into* 0009 and the
    database were already stamped at it — which is why the second is here.
    """

    def test_0009_alone_leaves_the_two_source_enumeration(
        self, at_construction_revision: None
    ) -> None:
        """Given / When / Then: at 0009, construction_forecast is refused."""
        expression = _source_constraint_expression()
        assert "project_land" in expression
        assert "manual" in expression
        assert "construction_forecast" not in expression
        assert _refusal_for_a_construction_pool() == SOURCE_CONSTRAINT

    def test_0010_admits_the_construction_forecast(self, at_construction_revision: None) -> None:
        """The correction reaches a database that already ran 0009.

        This is the assertion that a rewritten 0009 could not satisfy: the
        database is stamped at 0009 before the upgrade runs, so nothing inside
        0009 executes again and only an appended revision can change anything.
        """
        assert "construction_forecast" not in _source_constraint_expression()

        command.upgrade(_alembic_config(), SOURCE_KIND_REVISION)

        expression = _source_constraint_expression()
        assert "project_land" in expression
        assert "manual" in expression
        assert "construction_forecast" in expression
        # Past the enumeration, and now refused by the provenance foreign key
        # instead — which is the proof that the enumeration is no longer what
        # stands in the way.
        assert _refusal_for_a_construction_pool() == "foreign key"

    def test_a_fresh_install_reaches_the_same_enumeration(self, empty_database: None) -> None:
        """A new database and a migrated one must not disagree about the schema."""
        command.upgrade(_alembic_config(), "head")

        assert _current_revision() == HEAD_REVISION
        assert "construction_forecast" in _source_constraint_expression()

    def test_the_downgrade_restores_the_enumeration_0009_shipped(
        self, at_construction_revision: None
    ) -> None:
        """0010 -> 0009 puts the two-source constraint back, then 0009 -> 0010 again."""
        config = _alembic_config()
        command.upgrade(config, SOURCE_KIND_REVISION)
        assert "construction_forecast" in _source_constraint_expression()

        command.downgrade(config, CONSTRUCTION_REVISION)
        assert _current_revision() == CONSTRUCTION_REVISION
        assert "construction_forecast" not in _source_constraint_expression()
        assert _refusal_for_a_construction_pool() == SOURCE_CONSTRAINT

        command.upgrade(config, SOURCE_KIND_REVISION)
        assert _current_revision() == SOURCE_KIND_REVISION
        assert "construction_forecast" in _source_constraint_expression()

    def test_the_downgrade_refuses_rather_than_lose_a_cost_basis(
        self, at_construction_revision: None, postgres: None
    ) -> None:
        """A pool the old enumeration forbids stops the downgrade, and says why.

        Deleting the row to make the constraint fit would remove a governed
        hard-cost basis, and the version it belongs to would still reconcile and
        still activate. So the downgrade refuses, names how many pools are in
        the way, and leaves the schema at 0010.
        """
        config = _alembic_config()
        command.upgrade(config, SOURCE_KIND_REVISION)

        _seed_a_construction_sourced_pool()

        with pytest.raises(RuntimeError, match="construction forecast"):
            command.downgrade(config, CONSTRUCTION_REVISION)

        assert _current_revision() == SOURCE_KIND_REVISION
        assert "construction_forecast" in _source_constraint_expression()
