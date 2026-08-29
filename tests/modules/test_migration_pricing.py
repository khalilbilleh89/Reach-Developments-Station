"""The pricing migration against PostgreSQL.

Asserts against the real catalogue — ``pg_tables``, ``pg_constraint``,
``pg_indexes`` — rather than against metadata generated from the same models
under test. A migration test that only compares the models to themselves cannot
fail when the migration and the models disagree, which is the one thing it is
there to catch.

It also proves the two things an incremental production migration has to be:
additive, so PR-MVP-03's inventory survives it untouched, and reversible, so a
rollback leaves exactly the schema it started from.
"""

from __future__ import annotations

import pytest
from alembic import command
from sqlalchemy import text

from app.core.database import get_engine
from tests.conftest import alembic_config

INVENTORY_REVISION = "0003_inventory"
PRICING_REVISION = "0004_pricing"

#: What this revision adds, and nothing else.
NEW_TABLES = {
    "pricing_configurations",
    "pricing_area_rules",
    "pricing_premium_rules",
    "pricing_escalation_rules",
    "pricing_escalation_activations",
    "market_benchmarks",
    "unit_price_versions",
    "unit_price_components",
}

#: Belongs to PR-MVP-05 and later. Pricing says what a unit is offered at; it
#: does not sell it, collect on it or work out what it cost to build.
FORBIDDEN_TABLES = {
    "clients",
    "reservations",
    "sales",
    "sale_contracts",
    "spa_contracts",
    "payment_plans",
    "installments",
    "receipts",
    "allocations",
    "collections",
    "unit_costs",
    "unit_cost_allocations",
    "profitability",
    "construction_budgets",
    "construction_certificates",
    "cashflows",
    "pricing_scenarios",
    "pricing_rules",
}


@pytest.fixture
def at_inventory(postgres: None) -> None:
    """Rewind to PR-MVP-03 so the pricing upgrade genuinely executes."""
    command.downgrade(alembic_config(), INVENTORY_REVISION)


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


def _indexes(table: str) -> dict[str, str]:
    with get_engine().connect() as connection:
        rows = connection.execute(
            text("SELECT indexname, indexdef FROM pg_indexes WHERE tablename = :table"),
            {"table": table},
        )
        return {row[0]: row[1] for row in rows}


def _numeric(table: str) -> dict[str, tuple[int | None, int | None]]:
    with get_engine().connect() as connection:
        rows = connection.execute(
            text(
                "SELECT column_name, numeric_precision, numeric_scale "
                "FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = :table "
                "AND data_type IN ('numeric', 'real', 'double precision')"
            ),
            {"table": table},
        )
        return {row[0]: (row[1], row[2]) for row in rows}


_SEED = """
INSERT INTO currencies (id, code, name, minor_units, is_active)
VALUES ('11111111-1111-1111-1111-111111111111', 'JOD', 'Jordanian dinar', 3, true);
INSERT INTO country_packs
  (id, country_code, name, locale, timezone, default_currency_id, area_unit,
   fiscal_year_start_month, is_active)
VALUES ('22222222-2222-2222-2222-222222222222', 'JO', 'Jordan', 'en-JO', 'Asia/Amman',
        '11111111-1111-1111-1111-111111111111', 'sqm', 4, true);
INSERT INTO users
  (id, email, email_normalized, display_name, password_hash, is_active, must_change_password)
VALUES ('33333333-3333-3333-3333-333333333333', 'seed@example.com', 'seed@example.com',
        'Seed', 'x', true, false);
INSERT INTO projects
  (id, code, name, developer_entity, country_pack_id, status, base_currency_id,
   reporting_currency_id, fiscal_year_start_month, created_by_user_id)
VALUES ('44444444-4444-4444-4444-444444444444', 'SEED', 'Seed project', 'Reach',
        '22222222-2222-2222-2222-222222222222', 'predevelopment',
        '11111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111111', 1,
        '33333333-3333-3333-3333-333333333333');
INSERT INTO phases (id, project_id, code, name, sequence, status, is_active, created_by_user_id)
VALUES ('55555555-5555-5555-5555-555555555555', '44444444-4444-4444-4444-444444444444',
        'PHASE-1', 'Phase 1', 1, 'planning', true, '33333333-3333-3333-3333-333333333333');
INSERT INTO buildings
  (id, project_id, phase_id, code, name, sequence, is_active, created_by_user_id)
VALUES ('66666666-6666-6666-6666-666666666666', '44444444-4444-4444-4444-444444444444',
        '55555555-5555-5555-5555-555555555555', 'B1', 'Building 1', 1, true,
        '33333333-3333-3333-3333-333333333333');
INSERT INTO floors
  (id, project_id, building_id, code, label, sequence, is_active, created_by_user_id)
VALUES ('77777777-7777-7777-7777-777777777777', '44444444-4444-4444-4444-444444444444',
        '66666666-6666-6666-6666-666666666666', '01', 'First', 1, true,
        '33333333-3333-3333-3333-333333333333');
INSERT INTO units
  (id, project_id, floor_id, unit_number, unit_reference, sequence, asset_class,
   has_maid_room, is_duplex, is_penthouse, is_corner, pool_access,
   commercial_status, legal_status, collection_status, delivery_status,
   drawings_approved, legal_sale_eligible, pricing_approved, is_active, created_by_user_id)
VALUES ('88888888-8888-8888-8888-888888888888', '44444444-4444-4444-4444-444444444444',
        '77777777-7777-7777-7777-777777777777', '101', 'B1-101', 1, 'apartment',
        false, false, false, false, false,
        'unreleased', 'not_started', 'not_started', 'not_started',
        true, true, false, true, '33333333-3333-3333-3333-333333333333');
"""


def test_the_revision_creates_exactly_the_expected_tables(at_inventory: None) -> None:
    """Given the inventory schema, when the revision applies, then eight tables appear."""
    before = _tables()

    command.upgrade(alembic_config(), PRICING_REVISION)

    try:
        assert _tables() - before == NEW_TABLES
    finally:
        _restore_head()


def test_no_sales_collections_or_economics_table_is_created(at_inventory: None) -> None:
    """Given the revision, then nothing belonging to a later PR appears.

    PR-MVP-05 owns the sale, PR-MVP-06 the payment plan, PR-MVP-08 unit
    economics. Pricing pre-building any of them would be the abstraction-first
    mistake this rebuild exists to remove.
    """
    command.upgrade(alembic_config(), PRICING_REVISION)

    try:
        assert _tables().isdisjoint(FORBIDDEN_TABLES)
    finally:
        _restore_head()


def test_the_revision_alters_no_existing_table(at_inventory: None) -> None:
    """``units.pricing_approved`` already existed. This PR gives it a writer, not a column."""
    before = {table: _columns(table) for table in ("units", "projects", "area_types")}

    command.upgrade(alembic_config(), PRICING_REVISION)

    try:
        assert {table: _columns(table) for table in before} == before
        assert "pricing_approved" in before["units"]
    finally:
        _restore_head()


def test_the_revision_round_trips(at_inventory: None) -> None:
    """Given the upgrade, then the downgrade leaves the inventory schema exactly."""
    before = _tables()

    command.upgrade(alembic_config(), PRICING_REVISION)
    command.downgrade(alembic_config(), INVENTORY_REVISION)

    try:
        assert _tables() == before
    finally:
        _restore_head()


def test_inventory_data_survives_the_upgrade(at_inventory: None) -> None:
    """The point of an incremental migration: nothing already loaded moves.

    A project, its phase, its building, its floor and its unit are all still
    there afterwards — and ``pricing_approved`` still reads exactly what it read
    before, because this revision writes no data.
    """
    with get_engine().begin() as connection:
        connection.execute(text(_SEED))
        before = {
            table: connection.execute(text(f"SELECT count(*) FROM {table}")).scalar()
            for table in ("users", "projects", "phases", "buildings", "floors", "units")
        }

    command.upgrade(alembic_config(), PRICING_REVISION)

    try:
        with get_engine().connect() as connection:
            after = {
                table: connection.execute(text(f"SELECT count(*) FROM {table}")).scalar()
                for table in before
            }
            approved = connection.execute(
                text("SELECT pricing_approved FROM units WHERE unit_reference = 'B1-101'")
            ).scalar()
        assert after == before
        assert approved is False
    finally:
        _restore_head()


def test_one_active_configuration_is_enforced_by_a_partial_index(postgres: None) -> None:
    indexes = _indexes("pricing_configurations")

    definition = indexes["uq_pricing_configurations_active"]
    assert "UNIQUE" in definition
    assert "(project_id)" in definition
    assert "'active'::text" in definition


def test_one_active_price_per_unit_is_enforced_by_a_partial_index(postgres: None) -> None:
    indexes = _indexes("unit_price_versions")

    definition = indexes["uq_unit_price_versions_active"]
    assert "UNIQUE" in definition
    assert "(unit_id)" in definition
    assert "'active'::text" in definition


def test_one_benchmark_per_scope_treats_nulls_as_equal(postgres: None) -> None:
    """Without ``NULLS NOT DISTINCT`` two project-wide benchmarks would both fit."""
    definition = _indexes("market_benchmarks")["uq_market_benchmarks_scope"]

    assert "UNIQUE" in definition
    assert "NULLS NOT DISTINCT" in definition


def test_every_money_column_is_numeric_and_never_a_float(postgres: None) -> None:
    """The rule from ENGINEERING_RULES §6, checked against the real catalogue.

    A price that has been through a binary float is a price nobody can
    reconcile, and the place that guarantee has to hold is the column type.
    """
    for table in NEW_TABLES:
        for column, (precision, scale) in _numeric(table).items():
            assert precision is not None, f"{table}.{column} is a floating-point column"
            assert scale is not None, f"{table}.{column} has no fixed scale"
