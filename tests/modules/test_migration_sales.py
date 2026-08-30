"""The sales migration against PostgreSQL.

Asserts against the real catalogue — ``pg_tables``, ``pg_constraint``,
``pg_indexes`` — rather than against metadata generated from the same models
under test. A migration test that only compares the models to themselves cannot
fail when the migration and the models disagree, which is the one thing it is
there to catch.

This revision is the first that is not purely additive: it restates the closed
sets behind two columns PR-MVP-03 created and renames one value in place. The
tests below hold both halves — that the sales tables appear, and that a unit
already loaded comes through with everything except that one renamed word
untouched, and goes back exactly as it was on the way down.
"""

from __future__ import annotations

import pytest
from alembic import command
from sqlalchemy import text

from app.core.database import get_engine
from tests.conftest import alembic_config

PRICING_REVISION = "0004_pricing"
SALES_REVISION = "0005_sales_legal"

#: What this revision adds, and nothing else.
NEW_TABLES = {
    "sales_project_policies",
    "clients",
    "client_parties",
    "reservations",
    "reservation_adjustments",
    "reservation_status_events",
    "sale_contracts",
    "sale_contract_parties",
    "sale_contract_tax_lines",
    "sale_legal_events",
    "sale_cancellations",
    "handover_records",
    "handover_clearances",
}

#: Belongs to PR-MVP-06 and later. Sales records what was agreed; it does not
#: schedule the money, receipt it, refund it, or work out what the unit cost.
FORBIDDEN_TABLES = {
    "leads",
    "opportunities",
    "campaigns",
    "commissions",
    "payment_plans",
    "payment_plan_templates",
    "installments",
    "receipts",
    "receipt_allocations",
    "refunds",
    "collections",
    "unit_costs",
    "unit_cost_allocations",
    "profitability",
    "construction_budgets",
    "cashflows",
    "documents",
    "workflows",
    "workflow_steps",
    "approvals",
    "approval_rules",
}


@pytest.fixture
def at_pricing(postgres: None) -> None:
    """Rewind to PR-MVP-04 so the sales upgrade genuinely executes."""
    command.downgrade(alembic_config(), PRICING_REVISION)


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


def _check(name: str) -> str:
    with get_engine().connect() as connection:
        return connection.execute(
            text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conrelid = 'units'::regclass AND conname = :name"
            ),
            {"name": name},
        ).scalar_one()


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
        'reserved', 'not_started', 'not_started', 'not_started',
        true, true, true, true, '33333333-3333-3333-3333-333333333333');
INSERT INTO area_types
  (id, project_id, code, label, area_role, unit_of_measure, weight_factor,
   required_for_release, sort_order, is_active, created_by_user_id)
VALUES ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', '44444444-4444-4444-4444-444444444444',
        'INTERNAL', 'Internal area', 'internal', 'sqm', 1.000000, true, 1, true,
        '33333333-3333-3333-3333-333333333333');
INSERT INTO unit_area_schedules
  (id, project_id, unit_id, revision_code, status, reconciled, approved_by_user_id,
   approved_at, created_by_user_id)
VALUES ('cccccccc-cccc-cccc-cccc-cccccccccccc', '44444444-4444-4444-4444-444444444444',
        '88888888-8888-8888-8888-888888888888', 'R0', 'approved', true,
        '33333333-3333-3333-3333-333333333333', now(),
        '33333333-3333-3333-3333-333333333333');
INSERT INTO pricing_configurations
  (id, project_id, version_number, name, status, pricing_currency_id, base_internal_rate,
   premium_stacking_default, tax_treatment_code, valid_from, created_by_user_id)
VALUES ('99999999-9999-9999-9999-999999999999', '44444444-4444-4444-4444-444444444444',
        1, 'Launch', 'active', '11111111-1111-1111-1111-111111111111', 1500.00,
        'additive', 'exclusive', '2026-01-01', '33333333-3333-3333-3333-333333333333');
INSERT INTO unit_price_versions
  (id, project_id, unit_id, pricing_configuration_id, unit_area_schedule_id, version_number,
   status, currency_id, valid_from, base_area_value, scope_adjustment_total, premium_total,
   premium_cap_adjustment, escalation_total, paid_upgrade_total, reference_price_ex_tax,
   market_flag, basis_snapshot_json, created_by_user_id)
VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '44444444-4444-4444-4444-444444444444',
        '88888888-8888-8888-8888-888888888888', '99999999-9999-9999-9999-999999999999',
        'cccccccc-cccc-cccc-cccc-cccccccccccc',
        1, 'active', '11111111-1111-1111-1111-111111111111', '2026-01-01',
        110.0000, 0.00, 0.00, 0.00, 0.00, 0.00, 165000.00, 'no_benchmark', '{}',
        '33333333-3333-3333-3333-333333333333');
"""


def test_the_revision_creates_exactly_the_expected_tables(at_pricing: None) -> None:
    """Given the pricing schema, when the revision applies, then thirteen tables appear."""
    before = _tables()

    command.upgrade(alembic_config(), SALES_REVISION)

    try:
        assert _tables() - before == NEW_TABLES
    finally:
        _restore_head()


def test_no_plan_receipt_cost_or_engine_table_is_created(at_pricing: None) -> None:
    """Nothing belonging to a later PR, and nothing generic, appears.

    PR-MVP-06 owns the payment plan, PR-MVP-07 the receipt, PR-MVP-08 unit
    economics. There is no workflow, approval or document table either: this
    module's approvals are two role checks and a comparison of identifiers.
    """
    command.upgrade(alembic_config(), SALES_REVISION)

    try:
        assert _tables().isdisjoint(FORBIDDEN_TABLES)
    finally:
        _restore_head()


def test_the_revision_adds_no_column_to_any_existing_table(at_pricing: None) -> None:
    """The two changes to ``units`` are to its constraints, not its shape."""
    before = {
        table: _columns(table)
        for table in ("units", "projects", "area_types", "unit_price_versions")
    }

    command.upgrade(alembic_config(), SALES_REVISION)

    try:
        assert {table: _columns(table) for table in before} == before
    finally:
        _restore_head()


def test_the_commercial_and_legal_closed_sets_are_restated(at_pricing: None) -> None:
    command.upgrade(alembic_config(), SALES_REVISION)

    try:
        commercial = _check("ck_units_commercial_ok")
        legal = _check("ck_units_legal_ok")
        for value in ("contract_pending", "withdrawn"):
            assert value in commercial
        for value in ("no_spa", "lodged_submitted", "transferred", "withdrawal_pending"):
            assert value in legal
        assert "not_started" not in legal
        assert "spa_in_progress" not in legal
    finally:
        _restore_head()


def test_an_existing_unit_is_renamed_in_place_and_otherwise_untouched(
    at_pricing: None,
) -> None:
    """``not_started`` becomes ``no_spa``: the same fact, named for the document."""
    with get_engine().begin() as connection:
        connection.execute(text(_SEED))
        before = connection.execute(
            text(
                "SELECT commercial_status, collection_status, delivery_status, "
                "pricing_approved, unit_reference FROM units "
                "WHERE unit_reference = 'B1-101'"
            )
        ).one()

    command.upgrade(alembic_config(), SALES_REVISION)

    try:
        with get_engine().connect() as connection:
            after = connection.execute(
                text(
                    "SELECT commercial_status, collection_status, delivery_status, "
                    "pricing_approved, unit_reference, legal_status FROM units "
                    "WHERE unit_reference = 'B1-101'"
                )
            ).one()
        assert after[:5] == before
        assert after[5] == "no_spa"
    finally:
        _restore_head()


def test_existing_price_data_is_intact_after_the_upgrade(at_pricing: None) -> None:
    with get_engine().begin() as connection:
        connection.execute(text(_SEED))

    command.upgrade(alembic_config(), SALES_REVISION)

    try:
        with get_engine().connect() as connection:
            price = connection.execute(
                text(
                    "SELECT status, reference_price_ex_tax FROM unit_price_versions "
                    "WHERE unit_id = '88888888-8888-8888-8888-888888888888'"
                )
            ).one()
        assert price[0] == "active"
        assert str(price[1]) == "165000.00"
    finally:
        _restore_head()


def test_the_revision_round_trips(at_pricing: None) -> None:
    """Given the upgrade, then the downgrade leaves the pricing schema exactly."""
    before = _tables()
    before_checks = (_check("ck_units_commercial_ok"), _check("ck_units_legal_ok"))

    command.upgrade(alembic_config(), SALES_REVISION)
    command.downgrade(alembic_config(), PRICING_REVISION)

    try:
        assert _tables() == before
        assert (_check("ck_units_commercial_ok"), _check("ck_units_legal_ok")) == before_checks
    finally:
        _restore_head()


def test_a_renamed_legal_status_comes_back_on_the_way_down(at_pricing: None) -> None:
    """``no_spa`` is the one value that round-trips exactly, and it does."""
    with get_engine().begin() as connection:
        connection.execute(text(_SEED))

    command.upgrade(alembic_config(), SALES_REVISION)
    command.downgrade(alembic_config(), PRICING_REVISION)

    try:
        with get_engine().connect() as connection:
            legal = connection.execute(
                text("SELECT legal_status FROM units WHERE unit_reference = 'B1-101'")
            ).scalar()
        assert legal == "not_started"
    finally:
        _restore_head()


def test_one_committed_reservation_per_unit_is_a_partial_index(postgres: None) -> None:
    definition = _indexes("reservations")["uq_reservations_committed_unit"]

    assert "UNIQUE" in definition
    assert "(unit_id)" in definition
    assert "'active'::character varying" in definition
    assert "'extended'::character varying" in definition


def test_one_committed_contract_per_unit_is_a_partial_index(postgres: None) -> None:
    definition = _indexes("sale_contracts")["uq_sale_contracts_committed_unit"]

    assert "UNIQUE" in definition
    assert "(unit_id)" in definition
    assert "'signature_pending'::character varying" in definition


def test_one_open_cancellation_per_contract_is_a_partial_index(postgres: None) -> None:
    definition = _indexes("sale_cancellations")["uq_sale_cancellations_open"]

    assert "UNIQUE" in definition
    assert "(sale_contract_id)" in definition
    assert "'ready_for_unit_return'::character varying" in definition


def test_one_live_clearance_per_type_is_a_partial_index(postgres: None) -> None:
    definition = _indexes("handover_clearances")["uq_handover_clearances_current"]

    assert "UNIQUE" in definition
    assert "(handover_id, clearance_type)" in definition
    assert "revoked" in definition


def test_every_money_column_is_numeric_at_the_platform_scale(postgres: None) -> None:
    """No float anywhere near a contract price."""
    for table, columns in (
        ("reservations", ("net_contract_price_ex_tax", "total_buyer_payable", "tax_total")),
        ("sale_contracts", ("net_contract_price_ex_tax", "total_contract_price")),
        ("sale_contract_tax_lines", ("taxable_amount", "tax_amount")),
        ("sale_cancellations", ("forfeiture_amount", "refund_due_amount")),
    ):
        numeric = _numeric(table)
        for column in columns:
            assert numeric[column] == (18, 2), f"{table}.{column}"


def test_every_rate_column_is_numeric_at_the_rate_scale(postgres: None) -> None:
    assert _numeric("client_parties")["share_fraction"] == (9, 6)
    assert _numeric("sale_contract_tax_lines")["rate_fraction"] == (9, 6)
    assert _numeric("reservation_adjustments")["rate_fraction"] == (9, 6)


def test_no_constraint_name_is_truncated_by_postgresql(postgres: None) -> None:
    """A truncated name stops matching the metadata and reports drift for ever."""
    with get_engine().connect() as connection:
        rows = connection.execute(
            text(
                "SELECT conname FROM pg_constraint c "
                "JOIN pg_class t ON t.oid = c.conrelid "
                "WHERE t.relname = ANY(:tables)"
            ),
            {"tables": sorted(NEW_TABLES)},
        )
        names = [row[0] for row in rows]

    assert names
    assert all(len(name) < 63 for name in names), [n for n in names if len(n) >= 63]
