"""What PostgreSQL refuses, whatever the service layer believes.

Every invariant here is one the database can express, so it is expressed there
too. A service check is a rule that holds until somebody writes a second code
path; a constraint is a rule that holds against direct SQL.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.modules.conftest import current_version_id, plans_url


def _version_row(db: Session, version_id: str) -> dict:
    row = (
        db.execute(text("SELECT * FROM payment_plan_versions WHERE id = :i"), {"i": version_id})
        .mappings()
        .first()
    )
    assert row is not None
    return dict(row)


def _insert_version(db: Session, base: dict, **overrides: object) -> None:
    values = {**base, **overrides}
    values["id"] = overrides.get("id", uuid.uuid4())
    db.execute(
        text(
            "INSERT INTO payment_plan_versions (id, project_id, payment_plan_id,"
            " version_number, status, effective_date, currency_id, contract_value_covered,"
            " tax_total_snapshot, buyer_fee_total_snapshot, total_buyer_payable_snapshot,"
            " allocation_mode, charge_allocation_mode, reservation_treatment, origin_type,"
            " created_by_user_id)"
            " VALUES (:id, :project_id, :payment_plan_id, :version_number, :status,"
            " :effective_date, :currency_id, :contract_value_covered, :tax_total_snapshot,"
            " :buyer_fee_total_snapshot, :total_buyer_payable_snapshot, :allocation_mode,"
            " :charge_allocation_mode, :reservation_treatment, :origin_type,"
            " :created_by_user_id)"
        ),
        {
            key: values[key]
            for key in (
                "id",
                "project_id",
                "payment_plan_id",
                "version_number",
                "status",
                "effective_date",
                "currency_id",
                "contract_value_covered",
                "tax_total_snapshot",
                "buyer_fee_total_snapshot",
                "total_buyer_payable_snapshot",
                "allocation_mode",
                "charge_allocation_mode",
                "reservation_treatment",
                "origin_type",
                "created_by_user_id",
            )
        },
    )


def test_a_sale_cannot_carry_two_plans_even_through_direct_sql(
    db: Session, collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    plan = (
        db.execute(text("SELECT * FROM payment_plans WHERE id = :i"), {"i": plan_id})
        .mappings()
        .first()
    )
    with pytest.raises(IntegrityError) as caught:
        db.execute(
            text(
                "INSERT INTO payment_plans (id, project_id, sale_contract_id, plan_number,"
                " name, created_by_user_id)"
                " VALUES (:id, :p, :s, 'PLN-000099', 'Second', :u)"
            ),
            {
                "id": uuid.uuid4(),
                "p": plan["project_id"],
                "s": plan["sale_contract_id"],
                "u": plan["created_by_user_id"],
            },
        )
    assert "uq_payment_plans_sale" in str(caught.value)
    db.rollback()


def test_a_plan_number_is_unique_within_a_project(
    db: Session, project_id: str, plan_id: str
) -> None:
    plan = (
        db.execute(text("SELECT * FROM payment_plans WHERE id = :i"), {"i": plan_id})
        .mappings()
        .first()
    )
    with pytest.raises(IntegrityError) as caught:
        db.execute(
            text(
                "INSERT INTO payment_plans (id, project_id, sale_contract_id, plan_number,"
                " name, created_by_user_id)"
                " VALUES (:id, :p, :s, :n, 'Clone', :u)"
            ),
            {
                "id": uuid.uuid4(),
                "p": plan["project_id"],
                "s": plan["sale_contract_id"],
                "n": plan["plan_number"],
                "u": plan["created_by_user_id"],
            },
        )
    assert "uq_payment_plans" in str(caught.value)
    db.rollback()


def test_two_versions_cannot_share_a_number(
    db: Session, collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    version_id = current_version_id(collections_client, project_id, plan_id)
    base = _version_row(db, version_id)
    with pytest.raises(IntegrityError) as caught:
        _insert_version(db, base)
    assert "uq_plan_versions_number" in str(caught.value)
    db.rollback()


def test_only_one_version_can_be_active(
    db: Session, project_id: str, active_plan: tuple[str, str]
) -> None:
    _plan_id, version_id = active_plan
    base = _version_row(db, version_id)
    with pytest.raises(IntegrityError) as caught:
        _insert_version(db, base, version_number=99, status="active")
    assert "uq_plan_versions_active" in str(caught.value)
    db.rollback()


def test_only_one_version_can_be_in_preparation(
    db: Session, collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    version_id = current_version_id(collections_client, project_id, plan_id)
    base = _version_row(db, version_id)
    with pytest.raises(IntegrityError) as caught:
        _insert_version(db, base, version_number=99, status="submitted")
    assert "uq_plan_versions_open" in str(caught.value)
    db.rollback()


def test_a_forecast_date_can_never_stand_in_as_an_actual_due_date(
    db: Session, collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    """The control, in the database.

    Even direct SQL cannot mark a construction-milestone instalment due while
    it is still awaiting its trigger.
    """
    version_id = current_version_id(collections_client, project_id, plan_id)
    row_id = uuid.uuid4()
    with pytest.raises(IntegrityError) as caught:
        db.execute(
            text(
                "INSERT INTO payment_plan_installments (id, project_id,"
                " payment_plan_version_id, sequence, label, trigger_type, actual_due_date,"
                " trigger_status, grace_days, principal_amount, principal_fraction,"
                " tax_amount, fee_amount)"
                " VALUES (:id, :p, :v, 1, 'Slab', 'construction_milestone', '2026-03-01',"
                " 'awaiting_trigger', 0, 100.00, 1.000000, 0, 0)"
            ),
            {"id": row_id, "p": project_id, "v": version_id},
        )
    assert "contingent_needs_trigger" in str(caught.value)
    db.rollback()


def test_a_relative_instalment_must_carry_its_offset(
    db: Session, collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    version_id = current_version_id(collections_client, project_id, plan_id)
    with pytest.raises(IntegrityError) as caught:
        db.execute(
            text(
                "INSERT INTO payment_plan_installments (id, project_id,"
                " payment_plan_version_id, sequence, label, trigger_type, trigger_status,"
                " grace_days, principal_amount, principal_fraction, tax_amount, fee_amount)"
                " VALUES (:id, :p, :v, 1, 'Relative', 'days_after_spa', 'scheduled', 0,"
                " 100.00, 1.000000, 0, 0)"
            ),
            {"id": uuid.uuid4(), "p": project_id, "v": version_id},
        )
    assert "relative_has_offset" in str(caught.value)
    db.rollback()


def test_a_negative_principal_is_refused(
    db: Session, collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    version_id = current_version_id(collections_client, project_id, plan_id)
    with pytest.raises(IntegrityError) as caught:
        db.execute(
            text(
                "INSERT INTO payment_plan_installments (id, project_id,"
                " payment_plan_version_id, sequence, label, trigger_type,"
                " contractual_due_date, trigger_status, grace_days, principal_amount,"
                " principal_fraction, tax_amount, fee_amount)"
                " VALUES (:id, :p, :v, 1, 'Negative', 'fixed_date', '2026-03-01',"
                " 'scheduled', 0, -1.00, 0.000000, 0, 0)"
            ),
            {"id": uuid.uuid4(), "p": project_id, "v": version_id},
        )
    assert "principal_nonneg" in str(caught.value)
    db.rollback()


def test_a_fraction_above_the_whole_is_refused(
    db: Session, collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    version_id = current_version_id(collections_client, project_id, plan_id)
    with pytest.raises(IntegrityError) as caught:
        db.execute(
            text(
                "INSERT INTO payment_plan_installments (id, project_id,"
                " payment_plan_version_id, sequence, label, trigger_type,"
                " contractual_due_date, trigger_status, grace_days, principal_amount,"
                " principal_fraction, tax_amount, fee_amount)"
                " VALUES (:id, :p, :v, 1, 'Too much', 'fixed_date', '2026-03-01',"
                " 'scheduled', 0, 100.00, 1.500000, 0, 0)"
            ),
            {"id": uuid.uuid4(), "p": project_id, "v": version_id},
        )
    assert "fraction_range" in str(caught.value)
    db.rollback()


def test_an_unknown_trigger_type_is_refused(
    db: Session, collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    version_id = current_version_id(collections_client, project_id, plan_id)
    with pytest.raises(IntegrityError) as caught:
        db.execute(
            text(
                "INSERT INTO payment_plan_installments (id, project_id,"
                " payment_plan_version_id, sequence, label, trigger_type, trigger_status,"
                " grace_days, principal_amount, principal_fraction, tax_amount, fee_amount)"
                " VALUES (:id, :p, :v, 1, 'Invented', 'when_the_moon_is_full', 'scheduled',"
                " 0, 100.00, 1.000000, 0, 0)"
            ),
            {"id": uuid.uuid4(), "p": project_id, "v": version_id},
        )
    assert "trigger_type_ok" in str(caught.value)
    db.rollback()


def test_an_unknown_version_status_is_refused(
    db: Session, collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    version_id = current_version_id(collections_client, project_id, plan_id)
    base = _version_row(db, version_id)
    with pytest.raises(IntegrityError) as caught:
        _insert_version(db, base, version_number=99, status="nearly_approved")
    assert "status_ok" in str(caught.value)
    db.rollback()


def test_a_version_cannot_reference_a_plan_in_another_project(
    db: Session, collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    """The composite key refuses a cross-project substitution outright."""
    version_id = current_version_id(collections_client, project_id, plan_id)
    base = _version_row(db, version_id)
    with pytest.raises(IntegrityError) as caught:
        _insert_version(db, base, version_number=99, project_id=uuid.uuid4())
    assert "fk_payment_plan_versions_plan" in str(caught.value) or "plan" in str(caught.value)
    db.rollback()


def test_an_installment_cannot_belong_to_a_version_in_another_project(
    db: Session, collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    version_id = current_version_id(collections_client, project_id, plan_id)
    with pytest.raises(IntegrityError) as caught:
        db.execute(
            text(
                "INSERT INTO payment_plan_installments (id, project_id,"
                " payment_plan_version_id, sequence, label, trigger_type,"
                " contractual_due_date, trigger_status, grace_days, principal_amount,"
                " principal_fraction, tax_amount, fee_amount)"
                " VALUES (:id, :p, :v, 1, 'Wrong project', 'fixed_date', '2026-03-01',"
                " 'scheduled', 0, 100.00, 1.000000, 0, 0)"
            ),
            {"id": uuid.uuid4(), "p": uuid.uuid4(), "v": version_id},
        )
    assert "version" in str(caught.value)
    db.rollback()


def test_a_copied_version_must_name_its_source(
    db: Session, collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    version_id = current_version_id(collections_client, project_id, plan_id)
    base = _version_row(db, version_id)
    with pytest.raises(IntegrityError) as caught:
        _insert_version(db, base, version_number=99, status="draft", origin_type="copied_plan")
    assert "copied_has_source" in str(caught.value) or "uq_plan_versions_open" in str(caught.value)
    db.rollback()


def test_there_is_no_delete_route_for_a_plan(
    collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    """Financial history is never removed; the API offers no way to try."""
    response = collections_client.delete(f"{plans_url(project_id)}/{plan_id}")
    assert response.status_code in {404, 405}


def test_there_is_no_delete_route_for_a_version(
    collections_client: TestClient, project_id: str, active_plan: tuple[str, str]
) -> None:
    plan_id, version_id = active_plan
    response = collections_client.delete(f"{plans_url(project_id)}/{plan_id}/versions/{version_id}")
    assert response.status_code in {404, 405}


def test_a_request_with_an_unknown_field_is_refused(
    collections_client: TestClient, project_id: str, active_sale: str
) -> None:
    """A typo must fail loudly rather than being silently dropped."""
    refused = collections_client.post(
        plans_url(project_id),
        json={
            "sale_contract_id": active_sale,
            "name": "Typo",
            "reservaton_treatment": "reference_only",
        },
    )
    assert refused.status_code == 422


def test_a_malformed_decimal_is_refused(
    collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    version_id = current_version_id(collections_client, project_id, plan_id)
    refused = collections_client.put(
        f"{plans_url(project_id)}/{plan_id}/versions/{version_id}/installments",
        json={
            "allocation_mode": "percentage",
            "charge_allocation_mode": "pro_rata",
            "installments": [
                {
                    "sequence": 1,
                    "label": "Bad",
                    "trigger_type": "fixed_date",
                    "contractual_due_date": "2026-03-01",
                    "principal_fraction": "not-a-number",
                }
            ],
        },
    )
    assert refused.status_code == 422


def test_an_enormous_decimal_is_refused_before_it_reaches_the_column(
    collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    version_id = current_version_id(collections_client, project_id, plan_id)
    refused = collections_client.put(
        f"{plans_url(project_id)}/{plan_id}/versions/{version_id}/installments",
        json={
            "allocation_mode": "amount",
            "charge_allocation_mode": "pro_rata",
            "installments": [
                {
                    "sequence": 1,
                    "label": "Overflow",
                    "trigger_type": "fixed_date",
                    "contractual_due_date": "2026-03-01",
                    "principal_amount": "1e400",
                }
            ],
        },
    )
    assert refused.status_code == 422
