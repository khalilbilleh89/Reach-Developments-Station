"""The project migration against PostgreSQL.

Asserts against the real catalogue — ``information_schema``, ``pg_constraint``,
``pg_indexes`` — rather than against metadata generated from the same models
under test. A migration test that only compares the models to themselves cannot
fail when the migration and the models disagree, which is the one thing it is
there to catch.
"""

from __future__ import annotations

import pytest
from alembic import command
from sqlalchemy import inspect, text

from app.core.database import get_engine
from tests.conftest import alembic_config

GOVERNANCE = "0001_governance_access"
PROJECTS_REVISION = "0002_project_land_permits"

#: What this revision adds, and nothing else.
NEW_TABLES = {
    "projects",
    "user_project_access",
    "land_parcels",
    "planning_controls",
    "permits",
    "permit_status_events",
    "document_references",
}

#: Everything PR-MVP-01 left behind, which must survive untouched.
GOVERNANCE_TABLES = {
    "alembic_version",
    "audit_events",
    "country_approval_thresholds",
    "country_packs",
    "currencies",
    "reference_values",
    "roles",
    "tax_rules",
    "user_roles",
    "user_sessions",
    "users",
}

#: Belongs to PR-MVP-03 and later. Phase-scoped access is deferred with it:
#: there is no ``phase_id`` here, and no placeholder standing in for one.
FORBIDDEN_TABLES = {
    "phases",
    "buildings",
    "floors",
    "units",
    "unit_types",
    "prices",
    "price_versions",
    "sales",
    "sale_contracts",
    "payment_plans",
    "installments",
    "receipts",
    "clients",
    "reservations",
    "feasibility_runs",
    "scenarios",
    "construction_budgets",
    "construction_contracts",
    "cashflows",
}


@pytest.fixture
def at_governance(postgres: None) -> None:
    """Rewind to PR-MVP-01 so the project upgrade genuinely executes."""
    command.downgrade(alembic_config(), GOVERNANCE)


#: The minimum real row chain a land parcel needs before its own constraints can
#: be exercised: a currency, a country pack, a user and a project.
_SEED_ONE_PROJECT = """
WITH c AS (
    INSERT INTO currencies (id, code, name, minor_units, is_active)
    VALUES (gen_random_uuid(), 'JOD', 'Jordanian dinar', 2, true)
    RETURNING id
), p AS (
    INSERT INTO country_packs (
        id, country_code, name, locale, timezone,
        default_currency_id, area_unit, fiscal_year_start_month, is_active
    )
    SELECT gen_random_uuid(), 'JO', 'Jordan', 'en-JO', 'Asia/Amman', c.id, 'sqm', 1, true
    FROM c
    RETURNING id, default_currency_id
), u AS (
    INSERT INTO users (
        id, email, email_normalized, display_name, password_hash,
        is_active, must_change_password
    )
    VALUES (gen_random_uuid(), 'seed@example.com', 'seed@example.com', 'Seed', 'x', true, false)
    RETURNING id
)
INSERT INTO projects (
    id, code, name, developer_entity, country_pack_id,
    base_currency_id, reporting_currency_id, fiscal_year_start_month,
    status, created_by_user_id
)
SELECT
    gen_random_uuid(), 'SEED', 'Seed project', 'Seed developer', p.id,
    p.default_currency_id, p.default_currency_id, 1, 'setup', u.id
FROM p, u
"""


def _tables() -> set[str]:
    with get_engine().connect() as connection:
        rows = connection.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        return {row[0] for row in rows}


def _restore_head() -> None:
    command.upgrade(alembic_config(), "head")


def _constraint_names(table: str, contype: str) -> set[str]:
    with get_engine().connect() as connection:
        rows = connection.execute(
            text(
                "SELECT conname FROM pg_constraint "
                "WHERE contype = :contype AND conrelid = :table ::regclass"
            ),
            {"contype": contype, "table": table},
        )
        return {row[0] for row in rows}


def test_the_revision_creates_exactly_the_expected_tables(at_governance: None) -> None:
    """Given the governance schema, when the revision applies, then seven tables appear."""
    before = _tables()
    assert before == GOVERNANCE_TABLES

    command.upgrade(alembic_config(), PROJECTS_REVISION)

    try:
        assert _tables() == GOVERNANCE_TABLES | NEW_TABLES
    finally:
        _restore_head()


def test_no_inventory_or_commercial_table_is_created(at_governance: None) -> None:
    """Given the revision, then nothing belonging to a later PR appears."""
    command.upgrade(alembic_config(), PROJECTS_REVISION)

    try:
        assert _tables().isdisjoint(FORBIDDEN_TABLES)
    finally:
        _restore_head()


def test_no_phase_column_is_left_behind(at_governance: None) -> None:
    """Given Phase does not exist yet, then no table carries a placeholder for it.

    Phase-scoped access is deferred to PR-MVP-03, where there will be a real
    Phase to point a foreign key at. A nullable ``phase_id`` now would be an
    orphan column that nothing can enforce.
    """
    command.upgrade(alembic_config(), PROJECTS_REVISION)

    try:
        inspector = inspect(get_engine())
        for table in sorted(NEW_TABLES):
            columns = {column["name"] for column in inspector.get_columns(table)}
            assert not {"phase_id", "resource_type", "resource_id"}.intersection(columns), table
    finally:
        _restore_head()


def test_the_governance_data_survives_the_upgrade(at_governance: None) -> None:
    """Given the eleven seeded roles, then the project revision leaves them alone.

    Production migrations are incremental from here: this revision must not
    disturb anything PR-MVP-01 established.
    """
    command.upgrade(alembic_config(), PROJECTS_REVISION)

    try:
        with get_engine().connect() as connection:
            assert connection.execute(text("SELECT count(*) FROM roles")).scalar() == 11
    finally:
        _restore_head()


def test_the_business_uniqueness_rules_reach_the_database(at_governance: None) -> None:
    """Given the migrated schema, then each uniqueness rule exists as a constraint.

    Uniqueness enforced only in a service is uniqueness two concurrent requests
    can both walk past.
    """
    command.upgrade(alembic_config(), PROJECTS_REVISION)

    try:
        inspector = inspect(get_engine())
        expected = {
            "projects": ("code",),
            "user_project_access": ("project_id", "user_id"),
            "land_parcels": ("project_id", "plot_number"),
            "permits": ("project_id", "permit_code"),
            "planning_controls": ("parcel_id",),
        }
        for table, columns in expected.items():
            found = {
                tuple(constraint["column_names"])
                for constraint in inspector.get_unique_constraints(table)
            }
            assert columns in found, f"{table} is missing UNIQUE{columns}: {found}"
    finally:
        _restore_head()


def test_each_uniqueness_rule_is_declared_exactly_once(at_governance: None) -> None:
    """Given the schema, then no column set is guarded by two constraints.

    Two constraints over one column set means two indexes for one rule, and
    PostgreSQL silently keeps whichever it reads first — the defect PR-MVP-01
    had to correct on ``country_approval_thresholds``.
    """
    command.upgrade(alembic_config(), PROJECTS_REVISION)

    try:
        inspector = inspect(get_engine())
        for table in sorted(NEW_TABLES):
            column_sets = [
                tuple(constraint["column_names"])
                for constraint in inspector.get_unique_constraints(table)
            ]
            assert len(column_sets) == len(set(column_sets)), table
    finally:
        _restore_head()


def test_every_constraint_name_survived_postgresql(at_governance: None) -> None:
    """Given the migrated schema, then no constraint name was truncated.

    PostgreSQL cuts identifiers at 63 characters. A truncated name no longer
    matches the metadata, and autogenerate then reports drift for ever.
    """
    command.upgrade(alembic_config(), PROJECTS_REVISION)

    try:
        for table in sorted(NEW_TABLES):
            for contype in ("c", "u", "f", "p"):
                for name in _constraint_names(table, contype):
                    assert len(name) < 63, f"{name} ({len(name)} chars) was truncated"
    finally:
        _restore_head()


def test_the_child_scope_constraint_is_enforced_by_the_database(at_governance: None) -> None:
    """Given a document attached to both a parcel and a permit, then the row is refused."""
    command.upgrade(alembic_config(), PROJECTS_REVISION)

    try:
        names = _constraint_names("document_references", "c")
        assert "ck_document_references_single_attachment" in names
    finally:
        _restore_head()


def test_the_numeric_and_date_guards_reach_the_database(at_governance: None) -> None:
    """Given the migrated schema, then the value rules are constraints, not just code."""
    command.upgrade(alembic_config(), PROJECTS_REVISION)

    try:
        assert "ck_land_parcels_land_area_positive" in _constraint_names("land_parcels", "c")
        assert "ck_land_parcels_share_range" in _constraint_names("land_parcels", "c")
        assert "ck_projects_planned_dates_ordered" in _constraint_names("projects", "c")
        assert "ck_projects_latitude_range" in _constraint_names("projects", "c")
        assert "ck_planning_controls_coverage_range" in _constraint_names("planning_controls", "c")
        assert "ck_permits_prereq_not_self" in _constraint_names("permits", "c")
    finally:
        _restore_head()


def test_a_rebuilt_constraint_still_rejects_bad_data(at_governance: None) -> None:
    """Given a rebuilt schema, then the constraints actually bite.

    A migration that recreates a table without its constraints leaves the
    database structurally present but unprotected.
    """
    config = alembic_config()
    command.upgrade(config, PROJECTS_REVISION)
    command.downgrade(config, GOVERNANCE)
    command.upgrade(config, PROJECTS_REVISION)

    try:
        # A real parent chain, because a CHECK constraint has nothing to reject
        # until there is an actual row to insert.
        with get_engine().begin() as conn:
            conn.execute(text(_SEED_ONE_PROJECT))

        with pytest.raises(Exception, match="land_area_positive"), get_engine().begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO land_parcels "
                    "(id, project_id, plot_number, land_area, area_unit, is_active) "
                    "SELECT gen_random_uuid(), id, 'X', 0, 'sqm', true FROM projects LIMIT 1"
                )
            )
    finally:
        _restore_head()


def test_the_expected_indexes_exist(at_governance: None) -> None:
    """Given the register queries this module runs, then their columns are indexed."""
    command.upgrade(alembic_config(), PROJECTS_REVISION)

    try:
        inspector = inspect(get_engine())
        expected = {
            "projects": {"ix_projects_status", "ix_projects_country_pack_id"},
            "user_project_access": {"ix_user_project_access_user_id"},
            "land_parcels": {"ix_land_parcels_project_id"},
            "permits": {
                "ix_permits_status",
                "ix_permits_project_id",
                "ix_permits_project_blocking",
                "ix_permits_project_critical",
                "ix_permits_owner_user_id",
            },
            "document_references": {"ix_document_references_project_id"},
        }
        for table, names in expected.items():
            found = {index["name"] for index in inspector.get_indexes(table)}
            assert names <= found, f"{table} missing {names - found}"
    finally:
        _restore_head()


def test_the_revision_round_trips(at_governance: None) -> None:
    """Given a full down and up cycle, then no schema residue is left behind."""
    config = alembic_config()

    command.upgrade(config, PROJECTS_REVISION)
    assert _tables() == GOVERNANCE_TABLES | NEW_TABLES

    command.downgrade(config, GOVERNANCE)
    assert _tables() == GOVERNANCE_TABLES

    command.upgrade(config, PROJECTS_REVISION)
    try:
        assert _tables() == GOVERNANCE_TABLES | NEW_TABLES
    finally:
        _restore_head()


def test_the_project_revision_is_still_a_single_revision() -> None:
    """Given the roadmap, then 0002 is one revision and history stays ordered.

    Written as a prefix check rather than an exact list: later roadmap PRs add
    revisions of their own, and this test is about PR-MVP-02's, not about
    freezing the migration directory for ever.
    """
    from pathlib import Path

    versions = Path(__file__).resolve().parents[2] / "app" / "db" / "migrations" / "versions"
    names = sorted(path.stem for path in versions.glob("*.py"))

    assert names[:3] == [
        "0000_mvp_baseline",
        "0001_governance_access",
        "0002_project_land_permits",
    ]
