"""The 0006 migration against a real database that already holds sales.

Upgrading must add four tables and touch nothing that came before. Downgrading
must remove exactly those four and leave the sales and legal record intact —
production is incremental, and a migration that resets is a migration that
loses a development's contracts.
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

NEW_TABLES = (
    "payment_plans",
    "payment_plan_versions",
    "payment_plan_installments",
    "installment_trigger_events",
)


def _columns(db: Session, table: str) -> dict[str, dict]:
    return {column["name"]: column for column in inspect(db.get_bind()).get_columns(table)}


def _indexes(db: Session, table: str) -> dict[str, dict]:
    return {index["name"]: index for index in inspect(db.get_bind()).get_indexes(table)}


def _check_constraints(db: Session, table: str) -> set[str]:
    rows = db.execute(
        text(
            "SELECT conname FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid"
            " WHERE t.relname = :t AND c.contype = 'c'"
        ),
        {"t": table},
    ).scalars()
    return set(rows)


def test_the_four_tables_exist_at_head(db: Session) -> None:
    existing = set(inspect(db.get_bind()).get_table_names())
    for table in NEW_TABLES:
        assert table in existing


def test_the_sales_tables_were_not_altered(db: Session) -> None:
    """PR-MVP-06 adds no column to the domain above it."""
    columns = _columns(db, "sale_contracts")
    assert "active_payment_plan_version_id" not in columns
    assert "payment_plan_id" not in columns
    for forbidden in ("paid_amount", "balance_due", "receipt_id"):
        assert forbidden not in columns


def test_a_plan_is_unique_per_sale(db: Session) -> None:
    indexes = _indexes(db, "payment_plans")
    unique = {name: index for name, index in indexes.items() if index.get("unique")}
    assert any(index["column_names"] == ["sale_contract_id"] for index in unique.values())


def test_one_active_and_one_open_version_per_plan(db: Session) -> None:
    indexes = _indexes(db, "payment_plan_versions")
    assert "uq_plan_versions_active" in indexes
    assert "uq_plan_versions_open" in indexes
    active = db.execute(
        text("SELECT indexdef FROM pg_indexes WHERE indexname = 'uq_plan_versions_active'")
    ).scalar_one()
    # PostgreSQL renders the predicate with an explicit cast.
    assert "'active'::text" in active
    assert "UNIQUE" in active
    open_index = db.execute(
        text("SELECT indexdef FROM pg_indexes WHERE indexname = 'uq_plan_versions_open'")
    ).scalar_one()
    for status in ("draft", "submitted", "approved"):
        assert status in open_index


def test_the_contingent_trigger_check_is_in_the_database(db: Session) -> None:
    """The control, expressed where direct SQL cannot get past it."""
    checks = _check_constraints(db, "payment_plan_installments")
    assert "ck_payment_plan_installments_contingent_needs_trigger" in checks
    definition = db.execute(
        text(
            "SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c"
            " WHERE c.conname = 'ck_payment_plan_installments_contingent_needs_trigger'"
        )
    ).scalar_one()
    assert "actual_due_date IS NULL" in definition
    assert "triggered" in definition


def test_every_closed_set_is_a_check_constraint(db: Session) -> None:
    version_checks = _check_constraints(db, "payment_plan_versions")
    for name in ("status_ok", "allocation_ok", "charge_ok", "reservation_ok", "origin_ok"):
        assert f"ck_payment_plan_versions_{name}" in version_checks
    installment_checks = _check_constraints(db, "payment_plan_installments")
    for name in ("trigger_type_ok", "trigger_status_ok", "fraction_range"):
        assert f"ck_payment_plan_installments_{name}" in installment_checks
    event_checks = _check_constraints(db, "installment_trigger_events")
    assert "ck_installment_trigger_events_status_ok" in event_checks


def test_money_columns_carry_the_platform_scale(db: Session) -> None:
    version = _columns(db, "payment_plan_versions")
    for name in (
        "contract_value_covered",
        "tax_total_snapshot",
        "buyer_fee_total_snapshot",
        "total_buyer_payable_snapshot",
    ):
        assert version[name]["type"].scale == 2
        assert version[name]["type"].precision == 18
    installment = _columns(db, "payment_plan_installments")
    for name in ("principal_amount", "tax_amount", "fee_amount"):
        assert installment[name]["type"].scale == 2
    assert installment["principal_fraction"]["type"].scale == 6


def test_business_dates_are_date_columns_not_timestamps(db: Session) -> None:
    """A due date is a calendar fact, so no timezone can move it."""
    installment = _columns(db, "payment_plan_installments")
    for name in ("contractual_due_date", "forecast_due_date", "actual_due_date"):
        assert installment[name]["type"].python_type.__name__ == "date"
    assert _columns(db, "payment_plan_versions")["effective_date"]["type"].python_type.__name__ == (
        "date"
    )


def test_composite_project_safe_foreign_keys_are_present(db: Session) -> None:
    """A cross-project substitution is refused by the key, not by a service check."""
    for table, expected in (
        ("payment_plans", {"sale_contract_id", "project_id"}),
        ("payment_plan_versions", {"payment_plan_id", "project_id"}),
        ("payment_plan_installments", {"payment_plan_version_id", "project_id"}),
        ("installment_trigger_events", {"installment_id", "project_id"}),
    ):
        keys = inspect(db.get_bind()).get_foreign_keys(table)
        assert any(set(key["constrained_columns"]) == expected for key in keys), table


def test_the_useful_indexes_exist(db: Session) -> None:
    indexes = _indexes(db, "payment_plan_installments")
    for name in (
        "ix_installments_version_sequence",
        "ix_installments_actual_due_date",
        "ix_installments_forecast_due_date",
        "ix_installments_trigger_status",
        "ix_installments_owner_user_id",
    ):
        assert name in indexes


def test_no_collections_column_was_created_anywhere(db: Session) -> None:
    """PR-MVP-07 owns cash. Nothing here may hold a place for it."""
    forbidden = {
        "paid_amount",
        "balance_due",
        "outstanding_amount",
        "receipt_id",
        "payment_status",
        "days_overdue",
        "aging_bucket",
    }
    for table in NEW_TABLES:
        assert not forbidden.intersection(_columns(db, table)), table


@pytest.mark.parametrize("table", NEW_TABLES)
def test_each_table_is_scoped_to_a_project(db: Session, table: str) -> None:
    assert "project_id" in _columns(db, table)
