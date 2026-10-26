"""Independent design appointments and stage payments through the cash ledger."""

import uuid
from datetime import date

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.modules.access.models import User
from app.modules.audit.models import AuditEvent
from app.modules.cashflow.models import CashflowDevelopmentMovement
from app.modules.consultant_engineering.models import ConsultantPaymentProof, ConsultantStagePayment
from tests.conftest import alembic_config
from tests.modules.conftest import grant_access, project_payload

PDF = b"%PDF-1.4\n1 0 obj <</Type /Catalog>> endobj\ntrailer <</Root 1 0 R>>\n%%EOF"


def root(project_id: str) -> str:
    return f"/api/v1/projects/{project_id}/consultant-engineering"


def agreement(client: TestClient, project_id: str, name: str = "Main", kind: str = "main") -> dict:
    response = client.post(
        root(project_id) + "/engagements",
        json={
            "consultant_name": name,
            "agreement_reference": name + "-01",
            "engagement_type": kind,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def completed_stage(client: TestClient, project_id: str, kind: str = "main") -> tuple[dict, dict]:
    row = agreement(client, project_id, "Studio", kind)
    assert client.post(root(project_id) + f"/engagements/{row['id']}/activate").status_code == 200
    response = client.post(
        root(project_id) + f"/engagements/{row['id']}/stages",
        json={
            "name": "Detailed design",
            "status": "completed",
            "actual_completion_date": "2026-01-01",
            "agreed_payment_amount": "1200.00",
        },
    )
    assert response.status_code == 201, response.text
    return row, response.json()


def payment_body(stage: dict, currency_id: str) -> dict:
    return {
        "request_id": str(uuid.uuid4()),
        "expected_stage_updated_at": stage["updated_at"],
        "amount_ex_vat": "1000.00",
        "vat_rate_percent": "5",
        "currency_id": currency_id,
        "movement_date": date.today().isoformat(),
        "invoice_reference": "DESIGN-PAY-1",
    }


def expected(row: dict) -> dict:
    expense = row["expense"]
    return {
        key: expense[key]
        for key in (
            "amount",
            "amount_ex_vat",
            "vat_rate_percent",
            "category",
            "movement_date",
            "counterparty_reference",
            "invoice_reference",
            "evidence_reference",
            "notes",
        )
    }


def record(client: TestClient, project_id: str, stage: dict, currency_id: str) -> dict:
    response = client.post(
        root(project_id) + f"/stages/{stage['id']}/payments", json=payment_body(stage, currency_id)
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_main_and_independent_subconsultants_keep_separate_programmes(
    manager_member_client: TestClient, project_id: str
) -> None:
    client = manager_member_client
    main = agreement(client, project_id)
    landscape = agreement(client, project_id, "Landscape Ltd", "subconsultant")
    lighting = agreement(client, project_id, "Lighting Ltd", "subconsultant")
    for item in (main, landscape, lighting):
        assert (
            client.post(root(project_id) + f"/engagements/{item['id']}/activate").status_code == 200
        )
        assert (
            client.post(
                root(project_id) + f"/engagements/{item['id']}/stages",
                json={"name": item["consultant_name"] + " programme"},
            ).status_code
            == 201
        )
    another = agreement(client, project_id, "Replacement")
    assert (
        client.post(root(project_id) + f"/engagements/{another['id']}/activate").status_code == 409
    )
    workspace = client.get(root(project_id)).json()
    assert workspace["active_engagement"]["id"] == main["id"]
    assert {row["engagement_id"] for row in workspace["stages"]} == {
        row["id"] for row in (main, landscape, lighting)
    }
    assert len({row["consultant_name"] for row in workspace["engagements"]}) == 4


def test_completed_stage_payment_counts_gross_once_and_keeps_proof_optional(
    manager_member_client: TestClient,
    second_finance_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    currency_id: str,
    db: Session,
) -> None:
    _, stage = completed_stage(manager_member_client, project_id, "subconsultant")
    body = payment_body(stage, currency_id)
    url = root(project_id) + f"/stages/{stage['id']}/payments"
    first = manager_member_client.post(url, json=body)
    assert first.status_code == 201, first.text
    row = first.json()
    assert row["expense"]["amount"] == "1050.00" and row["proofs"] == []
    assert row["expense"]["counts_as_cash"] is False
    assert manager_member_client.post(url, json=body).json()["id"] == row["id"]
    assert (
        manager_member_client.post(url, json={**body, "amount_ex_vat": "1.00"}).status_code == 409
    )
    assert db.scalar(select(func.count()).select_from(ConsultantStagePayment)) == 1
    assert db.scalar(select(func.count()).select_from(CashflowDevelopmentMovement)) == 1
    pay_url = root(project_id) + f"/payments/{row['id']}"
    confirmed = second_finance_client.post(pay_url + "/confirm", json={"expected": expected(row)})
    assert confirmed.status_code == 200, confirmed.text
    assert (
        second_finance_client.post(
            pay_url + "/confirm", json={"expected": expected(row)}
        ).status_code
        == 409
    )
    position = finance_client.get(root(project_id) + "/payments").json()
    assert position["currency_id"] == currency_id
    assert position["stages"][0]["confirmed_paid_amount"] == "1050.00"
    assert position["stages"][0]["remaining_amount"] == "150.00"
    ledger = finance_client.get(f"/api/v1/projects/{project_id}/pre-launch/expenses").json()
    assert ledger["confirmed_paid_amount"] == "1050.00"


def test_prelaunch_correction_cannot_break_stage_attribution(
    manager_member_client: TestClient, project_id: str, currency_id: str
) -> None:
    client = manager_member_client
    _, stage = completed_stage(client, project_id)
    row = record(client, project_id, stage, currency_id)
    assert row["expense"]["counterparty_reference"] == "Studio"
    url = f"/api/v1/projects/{project_id}/pre-launch/expenses/{row['expense']['id']}"
    for changes in ({"category": "other"}, {"movement_date": "2025-12-31"}):
        response = client.patch(
            url, json={"expected": expected(row), "changes": {**expected(row), **changes}}
        )
        assert response.status_code == 409, response.text
    updated = client.patch(
        url,
        json={
            "expected": expected(row),
            "changes": {**expected(row), "invoice_reference": "BANK-2"},
        },
    )
    assert updated.status_code == 200, updated.text
    workspace = client.get(root(project_id) + "/payments").json()
    assert workspace["payments"][0]["expense"]["invoice_reference"] == "BANK-2"


def test_completion_is_required_and_cannot_be_reopened_with_standing_payment(
    manager_member_client: TestClient,
    project_id: str,
    currency_id: str,
) -> None:
    client = manager_member_client
    _, stage = completed_stage(client, project_id)
    row = record(client, project_id, stage, currency_id)
    fields = {
        k: stage[k]
        for k in ("name", "planned_date", "forecast_date", "notes", "agreed_payment_amount")
    }
    update = {
        **fields,
        "status": "in_progress",
        "actual_completion_date": None,
        "sequence": 1,
        "expected_updated_at": stage["updated_at"],
        "expected_order": [stage["id"]],
    }
    stage_url = root(project_id) + f"/stages/{stage['id']}"
    assert client.put(stage_url, json=update).status_code == 409
    assert (
        client.post(
            root(project_id) + f"/payments/{row['id']}/remove",
            json={"expected": expected(row), "reason": "Entered in error"},
        ).status_code
        == 200
    )
    response = client.put(stage_url, json=update)
    assert response.status_code == 200, response.text
    assert (
        client.post(
            stage_url + "/payments", json=payment_body(response.json(), currency_id)
        ).status_code
        == 409
    )


def test_permissions_scope_and_finance_maker_checker(
    manager_member_client: TestClient,
    finance_client: TestClient,
    engineer_client: TestClient,
    executive_client: TestClient,
    admin_client: TestClient,
    finance: User,
    project_id: str,
    country_pack_id: str,
    currency_id: str,
) -> None:
    _, stage = completed_stage(manager_member_client, project_id)
    assert engineer_client.get(root(project_id) + "/payments").status_code == 403
    body = payment_body(stage, currency_id)
    assert (
        executive_client.post(
            root(project_id) + f"/stages/{stage['id']}/payments", json=body
        ).status_code
        == 403
    )
    row = record(finance_client, project_id, stage, currency_id)
    url = root(project_id) + f"/payments/{row['id']}"
    assert (
        finance_client.post(url + "/confirm", json={"expected": expected(row)}).status_code == 403
    )
    other = admin_client.post(
        "/api/v1/projects", json=project_payload(country_pack_id, currency_id, code="DESIGN-OTHER")
    ).json()["id"]
    grant_access(admin_client, other, finance)
    assert (
        finance_client.post(
            root(other) + f"/payments/{row['id']}/confirm", json={"expected": expected(row)}
        ).status_code
        == 404
    )


def test_optional_proofs_add_later_download_delete_and_survive_reversal(
    manager_member_client: TestClient,
    second_finance_client: TestClient,
    engineer_client: TestClient,
    project_id: str,
    currency_id: str,
    db: Session,
) -> None:
    client = manager_member_client
    _, stage = completed_stage(client, project_id)
    row = record(client, project_id, stage, currency_id)
    url = root(project_id) + f"/payments/{row['id']}"
    assert (
        second_finance_client.post(url + "/confirm", json={"expected": expected(row)}).status_code
        == 200
    )
    upload = client.post(url + "/proofs?filename=bank-proof.pdf", content=PDF)
    assert upload.status_code == 201, upload.text
    proof = upload.json()
    assert "document" not in proof and "sha256" not in proof
    assert (
        client.post(url + "/proofs?filename=bank-proof.pdf", content=PDF).json()["id"]
        == proof["id"]
    )
    file_url = url + f"/proofs/{proof['id']}/file"
    assert client.get(file_url).content == PDF
    assert client.get(file_url).headers["cache-control"] == "private, no-store"
    assert engineer_client.get(file_url).status_code == 403
    assert (
        second_finance_client.post(
            url + "/reverse", json={"reason": "Bank returned payment"}
        ).status_code
        == 200
    )
    assert client.get(file_url).content == PDF
    assert (
        client.post(
            url + f"/proofs/{proof['id']}/delete", json={"reason": "Incorrect scan"}
        ).status_code
        == 204
    )
    assert client.get(file_url).status_code == 404
    assert (
        client.post(url + f"/proofs/{proof['id']}/delete", json={"reason": "Again"}).status_code
        == 404
    )
    stored = db.scalar(select(ConsultantPaymentProof))
    assert stored.document == PDF and stored.is_deleted
    assert (
        db.scalar(
            select(AuditEvent).where(AuditEvent.action == "design.payment_proof_removed")
        ).reason
        == "Incorrect scan"
    )
    positions = client.get(root(project_id) + "/payments").json()
    assert positions["stages"][0]["confirmed_paid_amount"] == "0.00"


@pytest.mark.parametrize(
    "name,data",
    [("proof.txt", PDF), ("fake.pdf", b"not a pdf"), ("empty.pdf", b""), ("../proof.pdf", PDF)],
    ids=["extension", "signature", "empty", "path"],
)
def test_invalid_proof_upload_is_rejected(
    manager_member_client: TestClient, project_id: str, currency_id: str, name: str, data: bytes
) -> None:
    client = manager_member_client
    _, stage = completed_stage(client, project_id)
    row = record(client, project_id, stage, currency_id)
    response = client.post(
        root(project_id) + f"/payments/{row['id']}/proofs", params={"filename": name}, content=data
    )
    assert response.status_code == 422


def test_unused_subconsultant_draft_delete_is_audited_and_repeated_delete_is_missing(
    manager_member_client: TestClient, executive_client: TestClient, project_id: str, db: Session
) -> None:
    client = manager_member_client
    item = agreement(client, project_id, "Unused Landscape", "subconsultant")
    url = root(project_id) + f"/engagements/{item['id']}/delete"
    body = {"expected_updated_at": item["updated_at"], "reason": "Duplicate appointment"}
    assert executive_client.post(url, json=body).status_code == 403
    assert client.post(url, json={**body, "reason": " "}).status_code == 422
    assert (
        client.post(url, json={**body, "expected_updated_at": "2020-01-01T00:00:00Z"}).status_code
        == 409
    )
    assert client.post(url, json=body).status_code == 204
    assert client.post(url, json=body).status_code == 404
    audit = db.scalar(
        select(AuditEvent).where(AuditEvent.action == "design.draft_agreement_deleted")
    )
    assert audit.before_data["consultant_name"] == "Unused Landscape"
    linked = agreement(client, project_id, "Linked landscape", "subconsultant")
    assert (
        client.post(
            root(project_id) + f"/engagements/{linked['id']}/stages", json={"name": "Concept"}
        ).status_code
        == 201
    )
    assert (
        client.post(
            root(project_id) + f"/engagements/{linked['id']}/delete",
            json={"expected_updated_at": linked["updated_at"], "reason": "Retain linked records"},
        ).status_code
        == 409
    )


def test_migration_roundtrip_and_retained_evidence(
    manager_member_client: TestClient, project_id: str, db: Session
) -> None:
    main = agreement(manager_member_client, project_id)
    db.rollback()
    command.downgrade(alembic_config(), "0050_project_matrices")
    command.upgrade(alembic_config(), "head")
    row = db.execute(
        text("SELECT engagement_type, consultant_name FROM consultant_engagements WHERE id=:id"),
        {"id": main["id"]},
    ).one()
    assert row.engagement_type == "main" and row.consultant_name == "Main"
    db.rollback()
    agreement(manager_member_client, project_id, "New Sub", "subconsultant")
    with pytest.raises(RuntimeError, match="Retained Design"):
        command.downgrade(alembic_config(), "0050_project_matrices")
