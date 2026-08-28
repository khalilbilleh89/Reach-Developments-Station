"""The governance migration against PostgreSQL.

Deliberately targets revision names rather than ``head`` so these assertions
stay true as later roadmap revisions land.
"""

from __future__ import annotations

import pytest
from alembic import command
from sqlalchemy import UniqueConstraint, inspect, text

from app.core.database import get_engine
from app.modules.access.models import SYSTEM_ROLES
from app.modules.settings.models import CountryApprovalThreshold
from tests.conftest import alembic_config

BASELINE = "0000_mvp_baseline"
GOVERNANCE = "0001_governance_access"

EXPECTED_TABLES = {
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

#: Tables that must not exist yet. Projects and everything hanging off them
#: belong to PR-MVP-02 and later.
FORBIDDEN_TABLES = {
    "projects",
    "project_access",
    "user_project_access",
    "phases",
    "buildings",
    "floors",
    "units",
    "prices",
    "sales",
    "payment_plans",
    "installments",
    "receipts",
    "construction_budgets",
    "cashflows",
}


@pytest.fixture
def at_baseline(postgres: None) -> None:
    """Rewind to the baseline so the governance upgrade genuinely executes."""
    command.downgrade(alembic_config(), BASELINE)


def _tables() -> set[str]:
    with get_engine().connect() as connection:
        rows = connection.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        return {row[0] for row in rows}


def _restore_head() -> None:
    command.upgrade(alembic_config(), "head")


def test_the_governance_revision_creates_exactly_the_expected_tables(
    at_baseline: None,
) -> None:
    """Given the baseline, when the revision is applied, then the schema matches."""
    assert _tables() == {"alembic_version"}

    command.upgrade(alembic_config(), GOVERNANCE)

    try:
        assert _tables() == EXPECTED_TABLES
    finally:
        _restore_head()


def test_no_project_or_domain_table_is_created(at_baseline: None) -> None:
    """Given the revision, then nothing belonging to a later PR appears.

    Project-scoped access is deferred to PR-MVP-02, where a real Project exists
    to point at, rather than leaving orphan identifiers behind here.
    """
    command.upgrade(alembic_config(), GOVERNANCE)

    try:
        assert _tables().isdisjoint(FORBIDDEN_TABLES)
    finally:
        _restore_head()


def test_the_role_catalogue_is_seeded_exactly(at_baseline: None) -> None:
    """Given the revision, then the eleven fixed roles exist and nothing else."""
    command.upgrade(alembic_config(), GOVERNANCE)

    try:
        with get_engine().connect() as connection:
            rows = connection.execute(text("SELECT key, label FROM roles")).all()
        assert sorted((key, label) for key, label in rows) == sorted(SYSTEM_ROLES)
    finally:
        _restore_head()


def test_no_user_is_seeded(at_baseline: None) -> None:
    """Given the revision, then no account exists until someone bootstraps one."""
    command.upgrade(alembic_config(), GOVERNANCE)

    try:
        with get_engine().connect() as connection:
            assert connection.execute(text("SELECT count(*) FROM users")).scalar() == 0
            assert connection.execute(text("SELECT count(*) FROM audit_events")).scalar() == 0
    finally:
        _restore_head()


def test_the_revision_round_trips(at_baseline: None) -> None:
    """Given a full down and up cycle, then the schema and seed data return."""
    config = alembic_config()

    command.upgrade(config, GOVERNANCE)
    assert _tables() == EXPECTED_TABLES

    command.downgrade(config, BASELINE)
    assert _tables() == {"alembic_version"}

    command.upgrade(config, GOVERNANCE)
    try:
        assert _tables() == EXPECTED_TABLES
        with get_engine().connect() as connection:
            assert connection.execute(text("SELECT count(*) FROM roles")).scalar() == 11
    finally:
        _restore_head()


THRESHOLD_LINK_CONSTRAINT = "uq_country_approval_thresholds_country_pack_id"


def test_one_country_pack_link_is_guarded_by_exactly_one_constraint(at_baseline: None) -> None:
    """Given the migrated schema, then one invariant is enforced by one constraint.

    Two unique constraints over the same column cost two indexes to maintain and
    leave a later migration guessing which name to drop, for no added safety.
    """
    command.upgrade(alembic_config(), GOVERNANCE)

    try:
        inspector = inspect(get_engine())
        on_the_link = [
            constraint
            for constraint in inspector.get_unique_constraints("country_approval_thresholds")
            if tuple(constraint["column_names"]) == ("country_pack_id",)
        ]
        assert [constraint["name"] for constraint in on_the_link] == [THRESHOLD_LINK_CONSTRAINT]

        # One constraint means PostgreSQL maintains one backing index, not two.
        with get_engine().connect() as connection:
            indexes = connection.execute(
                text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE schemaname = 'public' "
                    "AND tablename = 'country_approval_thresholds' "
                    "AND indexdef LIKE '%UNIQUE%(country_pack_id)'"
                )
            ).scalars()
            assert sorted(indexes) == [THRESHOLD_LINK_CONSTRAINT]
    finally:
        _restore_head()


def test_the_model_declares_the_same_single_constraint() -> None:
    """Given the mapped table, then it agrees with the migration on one constraint."""
    declared = {
        constraint.name: tuple(constraint.columns.keys())
        for constraint in CountryApprovalThreshold.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert declared == {THRESHOLD_LINK_CONSTRAINT: ("country_pack_id",)}
    # ``unique=True`` on the column would silently add a second one back.
    assert CountryApprovalThreshold.__table__.c.country_pack_id.unique is not True


def test_constraints_survive_the_round_trip(at_baseline: None) -> None:
    """Given a rebuilt schema, then the invariants are still enforced.

    A migration that recreates tables without their constraints would leave the
    database structurally present but unprotected.
    """
    config = alembic_config()
    command.upgrade(config, GOVERNANCE)
    command.downgrade(config, BASELINE)
    command.upgrade(config, GOVERNANCE)

    try:
        inspector = inspect(get_engine())
        unique_columns = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints("users")
        }
        assert ("email_normalized",) in unique_columns

        with get_engine().connect() as connection:
            checks = connection.execute(
                text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE contype = 'c' "
                    "AND conrelid = 'country_approval_thresholds'::regclass"
                )
            ).scalars()
            assert len(list(checks)) >= 9

        # And the rebuilt constraint actually rejects bad data.
        with pytest.raises(Exception, match="rate_fraction_range"), get_engine().begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO currencies (id, code, name, minor_units, is_active,"
                    " created_at, updated_at)"
                    " VALUES (gen_random_uuid(), 'XXX', 'Test', 2, true, now(), now())"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO country_packs (id, country_code, name, locale, timezone,"
                    " default_currency_id, area_unit, fiscal_year_start_month, is_active,"
                    " created_at, updated_at)"
                    " SELECT gen_random_uuid(), 'XX', 'Test', 'en', 'UTC', id, 'sqm', 1, true,"
                    " now(), now() FROM currencies WHERE code = 'XXX'"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO tax_rules (id, country_pack_id, tax_code, label, applies_to,"
                    " calculation_basis, rate_fraction, valid_from, is_active,"
                    " created_at, updated_at)"
                    " SELECT gen_random_uuid(), id, 'VAT', 'VAT', 'sale', 'net_amount',"
                    " 2.5, '2026-01-01', true, now(), now() FROM country_packs"
                    " WHERE country_code = 'XX'"
                )
            )
    finally:
        _restore_head()
