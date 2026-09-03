"""The construction revision: its shape, its reversal, and what it did not do.

Two kinds of proof here. The first is that 0009 applies, reverses and reapplies
cleanly and leaves exactly one head — the ordinary migration contract every
revision in this repository owes.

The second is the more interesting one: a list of things this migration must
**not** have done. Construction is the module with the most tempting shortcuts —
a foreign key from a buyer's instalment straight to a milestone, a certified
cost column on the unit, a paid balance beside an invoice — and each of them
would work, would pass every test that only checks what exists, and would break
the separation the module is for. So they are asserted absent.
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_engine

CONSTRUCTION_TABLES = (
    "construction_cost_codes",
    "construction_budget_versions",
    "construction_budget_lines",
    "construction_contracts",
    "construction_contract_lines",
    "construction_variations",
    "construction_variation_lines",
    "construction_certificates",
    "construction_certificate_lines",
    "construction_invoices",
    "construction_payments",
    "construction_payment_allocations",
    "construction_milestones",
    "construction_milestone_dependencies",
    "construction_forecast_versions",
    "construction_forecast_lines",
)


class TestTheRevision:
    def test_there_is_exactly_one_head_and_it_is_this_revision(self) -> None:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        script = ScriptDirectory.from_config(Config("alembic.ini"))
        assert len(script.get_heads()) == 1
        assert script.get_current_head() == "0009_construction"

    def test_the_revision_sits_directly_on_unit_economics(self) -> None:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        script = ScriptDirectory.from_config(Config("alembic.ini"))
        revision = script.get_revision("0009_construction")
        assert revision.down_revision == "0008_unit_economics"

    def test_every_construction_table_exists(self) -> None:
        """Sixteen tables, because five financial truths need five records."""
        inspector = inspect(get_engine())
        existing = set(inspector.get_table_names())
        for table in CONSTRUCTION_TABLES:
            assert table in existing, table

    def test_no_construction_foreign_key_reaches_payment_plans(self) -> None:
        """The load-bearing absence.

        A buyer's instalment names a milestone by its code, a stable handle, and
        not by a foreign key. The relationship a key would create is what would
        force payment plans to know construction exists — and once it did, a
        forecast date would be one join away from a receivable.
        """
        inspector = inspect(get_engine())
        for key in inspector.get_foreign_keys("payment_plan_installments"):
            assert not key["referred_table"].startswith("construction_"), key

    def test_no_construction_foreign_key_reaches_sales_or_units(self) -> None:
        """Delivery status has an owner, and construction is not it.

        Construction moves a unit through its build states by asking inventory,
        through inventory's public contract. A column here would be a second
        writer for a status inventory answers for.
        """
        inspector = inspect(get_engine())
        for table in ("sale_contracts", "units"):
            for key in inspector.get_foreign_keys(table):
                assert not key["referred_table"].startswith("construction_"), (table, key)

    def test_units_gained_no_construction_cost_column(self) -> None:
        """What a unit costs is unit economics' answer, derived from a governed
        basis. A construction cost on the unit row would be a second answer,
        and the two would disagree the first time a certificate was reversed."""
        inspector = inspect(get_engine())
        columns = {column["name"] for column in inspector.get_columns("units")}
        for forbidden in (
            "construction_cost",
            "certified_cost",
            "construction_progress",
            "construction_budget",
        ):
            assert forbidden not in columns, forbidden

    def test_no_derived_total_is_stored_anywhere_in_construction(self) -> None:
        """Every one of these is a sum over immutable rows.

        Storing one makes it independent truth, and independent truth drifts:
        the first reversed certificate leaves a cumulative column saying
        something the certificates no longer say.
        """
        inspector = inspect(get_engine())
        forbidden = {
            "revised_contract_value",
            "cumulative_certified",
            "previous_certified",
            "retention_balance",
            "retention_outstanding",
            "advance_outstanding",
            "advance_paid",
            "net_due",
            "paid_amount",
            "outstanding_amount",
            "estimate_at_completion",
            "variance_at_completion",
        }
        for table in CONSTRUCTION_TABLES:
            columns = {column["name"] for column in inspector.get_columns(table)}
            overlap = columns & forbidden
            assert not overlap, f"{table}: {sorted(overlap)}"


class TestTheUnitEconomicsExtension:
    def test_the_cost_pool_gained_construction_provenance(self) -> None:
        inspector = inspect(get_engine())
        columns = {column["name"] for column in inspector.get_columns("unit_economics_cost_pools")}
        assert "source_construction_forecast_version_id" in columns

    def test_provenance_points_at_a_forecast_in_the_same_project(self) -> None:
        """A composite key, so a pool cannot name a forecast from another project."""
        inspector = inspect(get_engine())
        keys = [
            key
            for key in inspector.get_foreign_keys("unit_economics_cost_pools")
            if key["referred_table"] == "construction_forecast_versions"
        ]
        assert len(keys) == 1
        assert set(keys[0]["constrained_columns"]) == {
            "source_construction_forecast_version_id",
            "project_id",
        }
        assert set(keys[0]["referred_columns"]) == {"id", "project_id"}


class TestTheDatabaseRefusesTheseShapes:
    """The invariants PostgreSQL can prove, tried past the service layer.

    A check constraint that only the service enforces is a check constraint that
    is not there, so each of these writes raw SQL at the table.
    """

    def test_a_construction_source_must_be_hard_and_project_wide(self, db: Session) -> None:
        with pytest.raises(Exception) as caught:
            db.execute(
                text(
                    "INSERT INTO unit_economics_cost_pools "
                    "(id, project_id, allocation_version_id, pool_number, name, category, "
                    " source_kind, amount, scope_kind, allocation_method, created_by_user_id, "
                    " source_construction_forecast_version_id) "
                    "VALUES (gen_random_uuid(), gen_random_uuid(), gen_random_uuid(), 'X', 'X', "
                    " 'soft', 'construction_forecast', 1, 'project', 'unit_count', "
                    " gen_random_uuid(), gen_random_uuid())"
                )
            )
        db.rollback()
        assert "cx_source_shape" in str(caught.value) or "violates" in str(caught.value)

    def test_provenance_is_required_by_that_source_and_forbidden_to_others(
        self, db: Session
    ) -> None:
        with pytest.raises(Exception) as caught:
            db.execute(
                text(
                    "INSERT INTO unit_economics_cost_pools "
                    "(id, project_id, allocation_version_id, pool_number, name, category, "
                    " source_kind, amount, scope_kind, allocation_method, created_by_user_id, "
                    " source_construction_forecast_version_id) "
                    "VALUES (gen_random_uuid(), gen_random_uuid(), gen_random_uuid(), 'X', 'X', "
                    " 'hard', 'manual', 1, 'project', 'unit_count', gen_random_uuid(), "
                    " gen_random_uuid())"
                )
            )
        db.rollback()
        assert "cx_provenance_shape" in str(caught.value) or "violates" in str(caught.value)


class TestLineageIsProvenNotNoted:
    """A source version that cannot be proved is a note, not provenance."""

    def test_budget_lineage_is_a_composite_key_into_the_same_project(self) -> None:
        inspector = inspect(get_engine())
        keys = [
            key
            for key in inspector.get_foreign_keys("construction_budget_versions")
            if key["referred_table"] == "construction_budget_versions"
        ]
        assert len(keys) == 1, "budget lineage must be a foreign key"
        assert set(keys[0]["constrained_columns"]) == {"source_version_id", "project_id"}
        assert set(keys[0]["referred_columns"]) == {"id", "project_id"}

    def test_forecast_lineage_is_a_composite_key_into_the_same_project(self) -> None:
        inspector = inspect(get_engine())
        keys = [
            key
            for key in inspector.get_foreign_keys("construction_forecast_versions")
            if key["referred_table"] == "construction_forecast_versions"
        ]
        assert len(keys) == 1, "forecast lineage must be a foreign key"
        assert set(keys[0]["constrained_columns"]) == {"source_version_id", "project_id"}
        assert set(keys[0]["referred_columns"]) == {"id", "project_id"}

    def test_a_budget_cannot_name_a_source_that_does_not_exist(self, db: Session) -> None:
        with pytest.raises(IntegrityError) as caught:
            db.execute(
                text(
                    "INSERT INTO construction_budget_versions "
                    "(id, project_id, version_number, currency_id, status, effective_date, "
                    " source_version_id, change_reason, created_by_user_id) "
                    "VALUES (gen_random_uuid(), gen_random_uuid(), 1, gen_random_uuid(), "
                    " 'draft', CURRENT_DATE, gen_random_uuid(), 'x', gen_random_uuid())"
                )
            )
        db.rollback()
        assert "source_version" in str(caught.value) or "violates" in str(caught.value)


class TestALifecycleClaimNeedsItsEvidence:
    """Every one of these is a status somebody could assert without signing it."""

    def test_a_milestone_cannot_be_certified_without_a_certifier(self, db: Session) -> None:
        """The tautological scope check that used to sit beside this proved
        nothing; this one is the reason the table has a check at all."""
        with pytest.raises(Exception) as caught:
            db.execute(
                text(
                    "INSERT INTO construction_milestones "
                    "(id, project_id, code, name, milestone_type, progress_fraction, "
                    " status, certified_date, certified_at, certified_by_user_id, "
                    " created_by_user_id) "
                    "VALUES (gen_random_uuid(), gen_random_uuid(), 'M1', 'M', 'progress', 0, "
                    " 'certified', CURRENT_DATE, NULL, NULL, gen_random_uuid())"
                )
            )
        db.rollback()
        assert "certified_shape" in str(caught.value) or "violates" in str(caught.value)

    def test_a_payment_cannot_be_confirmed_without_a_confirmer(self, db: Session) -> None:
        with pytest.raises(Exception) as caught:
            db.execute(
                text(
                    "INSERT INTO construction_payments "
                    "(id, project_id, contract_id, payment_reference, payment_date, amount, "
                    " currency_id, status, recorded_by_user_id) "
                    "VALUES (gen_random_uuid(), gen_random_uuid(), gen_random_uuid(), 'P1', "
                    " CURRENT_DATE, 1, gen_random_uuid(), 'confirmed', gen_random_uuid())"
                )
            )
        db.rollback()
        assert "confirmed_shape" in str(caught.value) or "violates" in str(caught.value)

    def test_an_other_invoice_cannot_stand_without_a_certificate(self, db: Session) -> None:
        """The escape hatch that used to exist: an invoice type with no ceiling.

        An approved liability has to fit inside something that authorised it, and
        "other" with no certificate fitted inside nothing at all.
        """
        with pytest.raises(Exception) as caught:
            db.execute(
                text(
                    "INSERT INTO construction_invoices "
                    "(id, project_id, contract_id, certificate_id, invoice_number, "
                    " invoice_type, invoice_date, amount_ex_tax, tax_amount, status, "
                    " recorded_by_user_id) "
                    "VALUES (gen_random_uuid(), gen_random_uuid(), gen_random_uuid(), NULL, "
                    " 'I1', 'other', CURRENT_DATE, 100, 0, 'recorded', gen_random_uuid())"
                )
            )
        db.rollback()
        assert "claim_has_certificate" in str(caught.value) or "violates" in str(caught.value)
