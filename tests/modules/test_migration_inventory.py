"""The inventory migration against PostgreSQL.

Asserts against the real catalogue — ``information_schema``, ``pg_constraint``,
``pg_indexes`` — rather than against metadata generated from the same models
under test. A migration test that only compares the models to themselves cannot
fail when the migration and the models disagree, which is the one thing it is
there to catch.

It also proves that PR-MVP-02's data survives the upgrade untouched, and that
``alembic check`` is clean afterwards: the two drift items this revision closes
were both discovered by an autogenerate run that should never have had anything
to say.
"""

from __future__ import annotations

import pytest
from alembic import command
from alembic.util import CommandError
from sqlalchemy import text

from app.core.database import get_engine
from tests.conftest import alembic_config

PROJECTS_REVISION = "0002_project_land_permits"
INVENTORY_REVISION = "0003_inventory"

#: What this revision adds, and nothing else.
NEW_TABLES = {
    "phases",
    "user_phase_access",
    "buildings",
    "floors",
    "units",
    "inventory_sub_assets",
    "area_types",
    "unit_area_schedules",
    "unit_area_values",
    "unit_status_events",
    "custom_field_definitions",
    "custom_field_options",
    "project_custom_field_values",
    "land_parcel_custom_field_values",
    "unit_custom_field_values",
}

#: Belongs to PR-MVP-04 and later. Inventory records what exists; it does not
#: price it, sell it or collect on it.
FORBIDDEN_TABLES = {
    "prices",
    "price_versions",
    "unit_prices",
    "premiums",
    "quotes",
    "clients",
    "reservations",
    "sales",
    "sale_contracts",
    "payment_plans",
    "installments",
    "receipts",
    "allocations",
    "collections",
    "unit_costs",
    "construction_budgets",
    "cashflows",
}

#: The old constraint name PostgreSQL actually held: SQLAlchemy truncated the
#: 65-character metadata name to 60 with a hash suffix, so the metadata could
#: never match it again.
TRUNCATED_NAME = "ck_country_approval_thresholds_discount_review_amount_n_9f00"
CANONICAL_NAME = "ck_country_approval_thresholds_discount_amount_nonneg"


@pytest.fixture
def at_projects(postgres: None) -> None:
    """Rewind to PR-MVP-02 so the inventory upgrade genuinely executes."""
    command.downgrade(alembic_config(), PROJECTS_REVISION)


def _restore_head() -> None:
    command.upgrade(alembic_config(), "head")


def _tables() -> set[str]:
    with get_engine().connect() as connection:
        rows = connection.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        return {row[0] for row in rows}


def _columns(table: str) -> set[str]:
    with get_engine().connect() as connection:
        rows = connection.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = :table"
            ),
            {"table": table},
        )
        return {row[0] for row in rows}


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


def _indexes(table: str) -> dict[str, str]:
    with get_engine().connect() as connection:
        rows = connection.execute(
            text("SELECT indexname, indexdef FROM pg_indexes WHERE tablename = :table"),
            {"table": table},
        )
        return {row[0]: row[1] for row in rows}


def test_the_revision_creates_exactly_the_expected_tables(at_projects: None) -> None:
    """Given the project schema, when the revision applies, then fifteen tables appear."""
    before = _tables()

    command.upgrade(alembic_config(), INVENTORY_REVISION)

    try:
        assert _tables() - before == NEW_TABLES
    finally:
        _restore_head()


def test_no_pricing_or_sales_table_is_created(at_projects: None) -> None:
    """Given the revision, then nothing belonging to a later PR appears."""
    command.upgrade(alembic_config(), INVENTORY_REVISION)

    try:
        assert _tables().isdisjoint(FORBIDDEN_TABLES)
    finally:
        _restore_head()


def test_the_revision_round_trips(at_projects: None) -> None:
    """Given the upgrade, then the downgrade leaves the project schema exactly."""
    before = _tables()

    command.upgrade(alembic_config(), INVENTORY_REVISION)
    command.downgrade(alembic_config(), PROJECTS_REVISION)

    try:
        assert _tables() == before
    finally:
        _restore_head()


def test_project_data_survives_the_upgrade(at_projects: None) -> None:
    """Given real PR-MVP-02 data, then the upgrade preserves all of it.

    The point of an incremental migration: a project, its parcel and its permit
    are still there afterwards, and so is the administrator who created them.
    """
    with get_engine().begin() as connection:
        connection.execute(text(_SEED))
        before = {
            table: connection.execute(text(f"SELECT count(*) FROM {table}")).scalar()
            for table in ("users", "roles", "projects", "land_parcels", "permits")
        }

    command.upgrade(alembic_config(), INVENTORY_REVISION)

    try:
        with get_engine().connect() as connection:
            after = {
                table: connection.execute(text(f"SELECT count(*) FROM {table}")).scalar()
                for table in before
            }
        assert after == before
        assert before["roles"] == 11
        assert before["projects"] == 1
    finally:
        _restore_head()


def test_existing_memberships_are_given_the_widest_scope(at_projects: None) -> None:
    """Given a membership from PR-MVP-02, then it reads ``all`` afterwards.

    Every row that existed before phases did meant "the whole project", and the
    upgrade has to keep it meaning that rather than silently narrowing anyone.
    """
    with get_engine().begin() as connection:
        connection.execute(text(_SEED))
        connection.execute(text(_SEED_MEMBERSHIP))

    command.upgrade(alembic_config(), INVENTORY_REVISION)

    try:
        with get_engine().connect() as connection:
            scopes = connection.execute(
                text("SELECT DISTINCT phase_scope FROM user_project_access")
            ).scalars()
            assert set(scopes) == {"all"}
    finally:
        _restore_head()


def test_the_overlong_constraint_is_renamed_not_rebuilt(at_projects: None) -> None:
    """Given the truncated name, then the upgrade renames it and keeps the rule."""
    assert TRUNCATED_NAME in _constraint_names("country_approval_thresholds", "c")

    command.upgrade(alembic_config(), INVENTORY_REVISION)

    try:
        names = _constraint_names("country_approval_thresholds", "c")
        assert CANONICAL_NAME in names
        assert TRUNCATED_NAME not in names
        assert len(CANONICAL_NAME) < 63
    finally:
        _restore_head()


def test_the_rename_reverses_cleanly(at_projects: None) -> None:
    """Given a downgrade, then the constraint carries its old name again."""
    command.upgrade(alembic_config(), INVENTORY_REVISION)
    command.downgrade(alembic_config(), PROJECTS_REVISION)

    try:
        assert TRUNCATED_NAME in _constraint_names("country_approval_thresholds", "c")
    finally:
        _restore_head()


def test_the_renamed_constraint_still_refuses_bad_data(postgres: None) -> None:
    """Given a negative amount, then the renamed constraint still rejects it.

    A rename that quietly dropped the rule would leave the name and lose the
    protection.
    """
    from sqlalchemy.exc import IntegrityError

    with get_engine().begin() as connection:
        connection.execute(text(_SEED))
    with pytest.raises(IntegrityError), get_engine().begin() as connection:
        connection.execute(text(_SEED_BAD_THRESHOLD))


def test_the_models_and_the_schema_agree(postgres: None) -> None:
    """Given the head revision, then ``alembic check`` finds nothing to do.

    This is the test the two drift items would have failed for a year. It is
    also why the check now runs in CI: a difference between the ORM metadata and
    the migration history is a defect, not background noise.
    """
    try:
        command.check(alembic_config())
    except CommandError as exc:  # pragma: no cover - only on real drift
        pytest.fail(f"Model and schema disagree: {exc}")


def test_no_redundant_uniqueness_is_declared_on_user_roles(postgres: None) -> None:
    """Given the composite primary key, then no second constraint repeats it.

    Declaring the rule twice made PostgreSQL keep only the primary key, and left
    autogenerate reporting the missing one for ever.
    """
    assert _constraint_names("user_roles", "p") == {"pk_user_roles"}
    assert _constraint_names("user_roles", "u") == set()


def test_the_hierarchy_is_held_together_by_composite_foreign_keys(postgres: None) -> None:
    """Given the tables, then each child proves its parent is in the same project.

    Not a Python check somebody can forget to write: the pair (parent_id,
    project_id) has to exist in the parent table.
    """
    with get_engine().connect() as connection:
        rows = connection.execute(
            text(
                "SELECT conrelid::regclass::text, pg_get_constraintdef(oid) "
                "FROM pg_constraint WHERE contype = 'f' "
                "AND conrelid::regclass::text IN "
                "('buildings', 'floors', 'units', 'unit_area_schedules', 'unit_area_values')"
            )
        ).all()
    definitions = {(table, definition) for table, definition in rows}

    def has_composite(table: str, columns: str) -> bool:
        return any(table == name and columns in definition for name, definition in definitions)

    assert has_composite("buildings", "(phase_id, project_id)")
    assert has_composite("floors", "(building_id, project_id)")
    assert has_composite("units", "(floor_id, project_id)")
    assert has_composite("unit_area_schedules", "(unit_id, project_id)")
    assert has_composite("unit_area_values", "(area_type_id, project_id)")


def test_a_phase_grant_requires_a_project_membership(postgres: None) -> None:
    """Given the table, then the pairing is a foreign key into project access."""
    with get_engine().connect() as connection:
        definitions = connection.execute(
            text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE contype = 'f' AND conrelid = 'user_phase_access'::regclass"
            )
        ).scalars()
    joined = " ".join(definitions)

    assert "user_project_access(project_id, user_id)" in joined
    assert "phases(id, project_id)" in joined


def test_the_uniqueness_rules_are_in_the_database(postgres: None) -> None:
    """Given the schema, then every identity rule is enforced by PostgreSQL."""
    assert "uq_phases_project_id_code" in _constraint_names("phases", "u")
    assert "uq_buildings_phase_id_code" in _constraint_names("buildings", "u")
    assert "uq_floors_building_id_code" in _constraint_names("floors", "u")
    assert "uq_units_project_id_unit_reference" in _constraint_names("units", "u")
    assert "uq_units_floor_id_unit_number" in _constraint_names("units", "u")
    assert "uq_inventory_sub_assets_project_id_asset_reference" in _constraint_names(
        "inventory_sub_assets", "u"
    )
    assert "uq_area_types_project_id_code" in _constraint_names("area_types", "u")
    assert "uq_unit_area_schedules_unit_id_revision_code" in _constraint_names(
        "unit_area_schedules", "u"
    )
    assert "uq_unit_area_values_unit_area_schedule_id_area_type_id" in _constraint_names(
        "unit_area_values", "u"
    )
    assert "uq_user_phase_access_user_id_phase_id" in _constraint_names("user_phase_access", "u")


def test_the_partial_indexes_carry_their_predicates(postgres: None) -> None:
    """Given the partial indexes, then their WHERE clauses are what they claim.

    A partial unique index without its predicate would either enforce too much
    or nothing at all.
    """
    area_types = _indexes("area_types")
    assert "internal" in area_types["uq_area_types_one_internal"]
    assert "is_active" in area_types["uq_area_types_one_internal"]

    schedules = _indexes("unit_area_schedules")
    assert "approved" in schedules["uq_unit_area_schedules_current"]

    values = _indexes("unit_custom_field_values")
    assert "unique_value IS NOT NULL" in values["uq_unit_custom_field_values_unique_value"]


def test_the_unit_table_holds_four_status_columns(postgres: None) -> None:
    """Given the unit, then the four dimensions are four columns, not one.

    A single ``status`` is the design mistake that makes a system unable to say
    "sold but not registered, paid but not handed over".
    """
    columns = _columns("units")

    assert {
        "commercial_status",
        "legal_status",
        "collection_status",
        "delivery_status",
    } <= columns
    assert "status" not in columns


def test_the_unit_table_stores_no_hierarchy_it_can_derive(postgres: None) -> None:
    """Given the unit, then phase and building are absent.

    They are reached through the floor. Two copies of one fact are two things to
    disagree, and ``project_id`` is the deliberate exception because it is the
    security scope every query filters on.
    """
    columns = _columns("units")

    assert "floor_id" in columns
    assert "project_id" in columns
    assert "phase_id" not in columns
    assert "building_id" not in columns


def test_no_money_column_reaches_inventory(postgres: None) -> None:
    """Given every new table, then none of them carries an amount.

    Inventory records what exists and how large it is. What it costs is
    PR-MVP-04's question.
    """
    with get_engine().connect() as connection:
        rows = connection.execute(
            text(
                "SELECT table_name, column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = ANY(:tables)"
            ),
            {"tables": sorted(NEW_TABLES)},
        ).all()

    suspicious = {"price", "amount", "cost", "discount", "total", "premium"}
    offenders = [
        f"{table}.{column}"
        for table, column in rows
        # `minimum_value` and `maximum_value` are custom-field validation bounds,
        # not money; they are NUMERIC because a bound on a decimal field is one.
        if any(word in column for word in suspicious) and table != "custom_field_definitions"
    ]
    assert offenders == []


_SEED = """
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
), pr AS (
    INSERT INTO projects (
        id, code, name, developer_entity, country_pack_id,
        base_currency_id, reporting_currency_id, fiscal_year_start_month,
        status, created_by_user_id
    )
    SELECT
        gen_random_uuid(), 'SEED', 'Seed project', 'Seed developer', p.id,
        p.default_currency_id, p.default_currency_id, 1, 'setup', u.id
    FROM p, u
    RETURNING id
), lp AS (
    INSERT INTO land_parcels (id, project_id, plot_number, land_area, area_unit, is_active)
    SELECT gen_random_uuid(), pr.id, 'PLOT-1', 4500, 'sqm', true FROM pr
    RETURNING id
)
INSERT INTO permits (
    id, project_id, permit_code, permit_type_code, authority,
    status, status_effective_date, is_blocking, is_critical_path
)
SELECT
    gen_random_uuid(), pr.id, 'BLD-001', 'BUILDING', 'Municipality',
    'not_started', CURRENT_DATE, false, false
FROM pr
"""

_SEED_MEMBERSHIP = """
INSERT INTO user_project_access (id, project_id, user_id, is_active, granted_by_user_id)
SELECT gen_random_uuid(), p.id, u.id, true, u.id
FROM projects p, users u
LIMIT 1
"""

_SEED_BAD_THRESHOLD = """
INSERT INTO country_approval_thresholds (id, country_pack_id, discount_review_amount)
SELECT gen_random_uuid(), id, -1 FROM country_packs LIMIT 1
"""
