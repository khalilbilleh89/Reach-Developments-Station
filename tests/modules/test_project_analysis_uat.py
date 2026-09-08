"""One governed Gate 0 + Gate 0A journey; all writes use owning APIs."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.modules.conftest import allocate as allocate_receipt
from tests.modules.conftest import (
    approve_areas,
    confirm_receipt,
    construction_url,
    governing_installments,
    inventory_url,
    parcel_payload,
    permit_payload,
    pricing_url,
    record_invoice,
    record_payment,
    record_receipt,
    sales_url,
)
from tests.modules.test_commissions_review import snapshot
from tests.modules.test_construction_invoices_payments import allocate, approve_invoice
from tests.modules.test_project_analysis import root


@pytest.fixture
def priced_unit(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
) -> str:
    # Overrides only this test module's price fixture: the downstream sale/plan
    # fixtures still execute release, reservation, signatures and activation APIs.
    approve_areas(admin_client, project_id, unit_id, area_types)
    base = inventory_url(project_id)
    assert (
        admin_client.patch(
            f"{base}/area-types/{area_types['BALCONY']}", json={"physical_component": "balcony"}
        ).status_code
        == 200
    )
    values = [
        {"area_type_id": area_types["INTERNAL"], "raw_area": "100"},
        {"area_type_id": area_types["BALCONY"], "raw_area": "20"},
    ]
    for component in ("roof_garden", "front_garden", "terrace", "porches"):
        response = admin_client.post(
            f"{base}/area-types",
            json={
                "code": component,
                "label": component,
                "area_role": "outdoor",
                "physical_component": component,
                "weight_factor": "0",
            },
        )
        assert response.status_code == 201, response.text
        values.append({"area_type_id": response.json()["id"], "raw_area": "0"})
    revision = admin_client.post(
        f"{base}/units/{unit_id}/area-schedules",
        json={"revision_code": "G0A", "reconciled": True, "values": values},
    )
    assert revision.status_code == 201, revision.text
    assert (
        admin_client.post(
            f"{base}/units/{unit_id}/area-schedules/{revision.json()['id']}/approve"
        ).status_code
        == 200
    )
    result = finance_client.post(
        f"{pricing_url(project_id)}/units/{unit_id}/price-versions",
        json={"selling_price": "150000", "change_reason": "Gate 0A direct selling price"},
    )
    assert result.status_code == 201, result.text
    url = f"{pricing_url(project_id)}/price-versions/{result.json()['id']}"
    assert finance_client.post(f"{url}/submit", json={}).status_code == 200
    assert (
        cfo_client.post(f"{url}/approve", json={"reason": "Independent review"}).status_code == 200
    )
    assert cfo_client.post(f"{url}/activate").status_code == 200
    return unit_id


@pytest.fixture
def reservation_id(
    sales_ops_client: TestClient, project_id: str, released_unit: str, buyer_id: str
) -> str:
    expires = (datetime.now(UTC).date() + timedelta(days=7)).isoformat()
    response = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations",
        json={
            "unit_id": released_unit,
            "client_id": buyer_id,
            "expires_on": expires,
            "price_locked_until": expires,
            "sales_branch_code": "AMMAN",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["reservation"]["id"]


def test_integrated_gate0a_journey(
    admin_client: TestClient,
    manager_member_client: TestClient,
    finance_client: TestClient,
    second_finance_client: TestClient,
    cfo_client: TestClient,
    collections_client: TestClient,
    engineer_client: TestClient,
    project_id: str,
    unit_id: str,
    currency_id: str,
    collecting_sale: str,
    active_contract: str,
    certified_certificate: str,
    db: Session,
) -> None:
    today = datetime.now(UTC).date().isoformat()
    project_root = f"/api/v1/projects/{project_id}"
    client = manager_member_client
    # CountryPack/currency, project and Phase/Building/Floor/Unit were created by
    # their fixture APIs; no Settings-page detour or duplicate string identity.
    parcel = admin_client.post(
        f"{project_root}/parcels",
        json=parcel_payload(purchase_price="90000", acquisition_fees="10000"),
    )
    assert parcel.status_code == 201, parcel.text
    assert Decimal(parcel.json()["total_acquisition_cost"]) == Decimal("100000")
    permit = admin_client.post(f"{project_root}/permits", json=permit_payload())
    assert permit.status_code == 201, permit.text
    for status in ("preparing", "submitted", "accepted_for_review", "issued"):
        changed = admin_client.post(
            f"{project_root}/permits/{permit.json()['id']}/transitions",
            json={"to_status": status, "effective_date": today, "reason": "Gate 0A acceptance"},
        )
        assert changed.status_code == 201, changed.text
    feature = engineer_client.post(
        f"{inventory_url(project_id)}/units/{unit_id}/features", json={"label": "Acoustic glazing"}
    )
    assert feature.status_code == 201, feature.text
    expense_url = f"{project_root}/pre-launch/expenses"
    expense = finance_client.post(
        expense_url,
        json={
            "category": "utilities",
            "amount": "8000",
            "movement_date": today,
            "currency_id": currency_id,
            "evidence_reference": "acceptance://utilities",
        },
    )
    assert expense.status_code == 201, expense.text
    confirm_url = f"{expense_url}/{expense.json()['id']}/confirm"
    assert finance_client.post(confirm_url, json={}).status_code == 403
    assert second_finance_client.post(confirm_url, json={}).status_code == 200
    recorded = record_receipt(
        collections_client, project_id, collecting_sale, "10000", receipt_date=today
    )
    assert recorded.status_code == 201, recorded.text
    received = record_receipt(
        collections_client, project_id, collecting_sale, "30000", receipt_date=today
    )
    assert received.status_code == 201, received.text
    assert confirm_receipt(finance_client, project_id, received.json()["id"]).status_code == 200
    installments = governing_installments(collections_client, project_id, collecting_sale)
    allocated = allocate_receipt(
        collections_client,
        project_id,
        received.json()["id"],
        installments[0]["installment_id"],
        "30000",
    )
    assert allocated.status_code == 201, allocated.text
    invoice = record_invoice(
        finance_client,
        project_id,
        active_contract,
        certificate_id=certified_certificate,
        amount_ex_tax="12000",
        invoice_date=today,
    )
    assert invoice.status_code == 201, invoice.text
    approve_invoice(second_finance_client, project_id, invoice.json()["id"])
    payment = record_payment(
        finance_client, project_id, active_contract, currency_id, amount="12000", payment_date=today
    )
    assert payment.status_code == 201, payment.text
    allocate(
        finance_client,
        project_id,
        payment.json()["id"],
        invoice_id=invoice.json()["id"],
        amount="12000",
    )
    assert (
        second_finance_client.post(
            f"{construction_url(project_id)}/payments/{payment.json()['id']}/confirm", json={}
        ).status_code
        == 200
    )
    before = finance_client.get(f"{root(project_id)}/financial").json()
    month = next(row for row in before["monthly"] if row["month"] == today[:7] + "-01")
    assert Decimal(month["contracted_sales_value"]) == Decimal("150000")
    assert Decimal(month["customer_cash_received"]) == Decimal("30000")
    assert Decimal(month["project_cash_outflow"]) == Decimal("20000")
    assert Decimal(month["net_actual_cash_movement"]) == Decimal("10000")
    # Release commission with a separate checker; compare every other persisted row.
    before_commission = snapshot(
        db, ("commission_grants", "commission_allocations", "audit_events")
    )
    grant_url = f"{project_root}/commissions"
    grant = finance_client.post(
        grant_url,
        json={
            "sale_contract_id": collecting_sale,
            "commissionable_base_amount": "150000",
            "granted_rate_fraction": "0.1",
        },
    )
    assert grant.status_code == 201, grant.text
    grant_id = grant.json()["id"]
    for label, rate in (
        ("Branch", "0.05"),
        ("Sales Person", "0.03"),
        ("Cyprus Branch", "0.01"),
        ("Support Team", "0.01"),
    ):
        response = finance_client.post(
            f"{grant_url}/{grant_id}/allocations",
            json={"beneficiary_name": label, "rate_fraction": rate},
        )
        assert response.status_code == 200, response.text
    assert finance_client.post(f"{grant_url}/{grant_id}/release", json={}).status_code == 403
    released = second_finance_client.post(f"{grant_url}/{grant_id}/release", json={})
    assert released.status_code == 200, released.text
    assert Decimal(released.json()["commission_total"]) == Decimal("15000")
    assert sorted(Decimal(row["calculated_amount"]) for row in released.json()["allocations"]) == [
        Decimal("1500"),
        Decimal("1500"),
        Decimal("4500"),
        Decimal("7500"),
    ]
    assert (
        snapshot(db, ("commission_grants", "commission_allocations", "audit_events"))
        == before_commission
    )
    consultant_url = f"{project_root}/consultant-engineering"
    agreement = client.post(
        f"{consultant_url}/engagements",
        json={"consultant_name": "Acceptance Engineer", "agreement_reference": "CE-1"},
    )
    assert agreement.status_code == 201
    path = f"{consultant_url}/engagements/{agreement.json()['id']}"
    assert client.post(f"{path}/activate").status_code == 200
    discipline = client.post(f"{path}/disciplines", json={"name": "Civil"})
    stage = client.post(f"{path}/stages", json={"name": "Concept"})
    assert discipline.status_code == stage.status_code == 201
    payload = {"name": "Issued drawings", "stage_id": stage.json()["id"]}
    deliverable = client.post(f"{path}/deliverables", json=payload)
    assert deliverable.status_code == 201
    for state in ("submitted", "accepted"):
        payload.update(
            status=state, submitted_date=today, expected_updated_at=deliverable.json()["updated_at"]
        )
        if state == "accepted":
            payload["accepted_date"] = today
        deliverable = client.put(
            f"{consultant_url}/deliverables/{deliverable.json()['id']}", json=payload
        )
        assert deliverable.status_code == 200, deliverable.text
    assert finance_client.get(f"{root(project_id)}/financial").json() == before
    technical = engineer_client.get(f"{root(project_id)}/technical")
    assert technical.status_code == 200, technical.text
    assert technical.json()["features"] == {"Acoustic glazing": 1}
    assert technical.json()["permits"]["issued"] == 1
    assert technical.json()["consultant"]["accepted_deliverables"] == 1
    assert (
        next(row for row in technical.json()["areas"] if row["component"] == "gross")["average"]
        == "120.00"
    )
    assert (
        engineer_client.post(
            f"{inventory_url(project_id)}/units/{unit_id}/features",
            json={"label": "Thermal insulation"},
        ).status_code
        == 201
    )
    assert (
        engineer_client.get(f"{root(project_id)}/technical").json()["features"][
            "Thermal insulation"
        ]
        == 1
    )
    construction = client.post(
        f"{construction_url(project_id)}/stages", json={"name": "Foundation"}
    )
    assert construction.status_code == 201, construction.text
    completed = engineer_client.post(
        f"{construction_url(project_id)}/units/{unit_id}/stages/{construction.json()['id']}/completion",
        json={"completed_date": today, "reason": "Inspected", "expected_revision": 0},
    )
    assert completed.status_code == 204, completed.text
    assert (
        engineer_client.get(f"{root(project_id)}/technical").json()["construction_stages"][0][
            "completed_units"
        ]
        == 1
    )
    frozen = snapshot(db)
    for section in ("fundamental", "financial", "technical"):
        assert finance_client.get(f"{root(project_id)}/{section}").status_code == 200
    assert snapshot(db) == frozen
