"""Already signed contracts, actual cash and omissions need no invented budget."""

import uuid
from typing import Any

import pytest
from alembic import command
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.access.models import User
from app.modules.audit.models import AuditEvent
from app.modules.construction import service
from tests.conftest import alembic_config
from tests.modules.conftest import (
    PROJECTS,
    certify,
    construction_url,
    create_certificate,
    create_contract,
    grant_access,
    project_payload,
    record_invoice,
    set_contract_line,
)
from tests.test_migrations import HEAD_REVISION


def signed(
    client: TestClient, project_id: str, currency_id: str, **extra: object
) -> dict[str, Any]:
    response = create_contract(
        client,
        project_id,
        currency_id,
        signed_contract=True,
        signed_reference="Signed main works agreement 2026-09-20",
        tax_rate_fraction="0.050000",
        **extra,
    )
    assert response.status_code == 201, response.text
    return response.json()


def payment(
    client: TestClient, base: str, contract_id: str, currency_id: str, **extra: object
) -> Response:
    body: dict[str, object] = {
        "payment_reference": "BANK-01",
        "payment_date": "2026-09-20",
        "amount": "210000.00",
        "currency_id": currency_id,
        "proof_reference": "Bank transfer receipt 01",
        "direct_contract_payment": True,
    }
    body.update(extra)
    return client.post(f"{base}/contracts/{contract_id}/payments", json=body)


def test_signed_contract_payment_reduction_and_reversal(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    currency_id: str,
    db: Session,
) -> None:
    base = construction_url(project_id)
    contract = signed(finance_client, project_id, currency_id)
    assert contract["status"] == "active"
    assert contract["line_total"] == "1000000.00"
    assert finance_client.get(f"{base}/budgets").json() == []
    paid = payment(finance_client, base, contract["id"], currency_id)
    assert paid.status_code == 201, paid.text
    assert paid.json()["status"] == "confirmed"
    assert paid.json()["allocations"] == []
    cash = service.cashflow_payment_rows(db, project_id=uuid.UUID(project_id))
    assert len(cash) == 1
    assert str(cash[0].amount) == "210000.00"
    assert str(cash[0].unattributed_amount) == "210000.00"
    detail_url = f"{base}/contracts/{contract['id']}"
    detail = finance_client.get(detail_url).json()
    assert detail["remaining_contract_balance"] == "840000.00"
    assert detail["invoice_outstanding"] == "0.00"
    summary = finance_client.get(f"{base}/summary").json()
    assert summary["payable"]["confirmed_paid"] == "210000.00"
    assert summary["payable"]["invoice_outstanding"] == "0.00"
    for kind, amount, expected in (
        ("addition", "100000.00", "1155000.00"),
        ("reduction", "50000.00", "1102500.00"),
    ):
        change = finance_client.post(
            f"{detail_url}/variations",
            json={
                "variation_number": kind,
                "description": "Client items" if kind == "reduction" else "Extra works",
                "requested_date": "2026-09-20",
                "cost_code_id": contract["lines"][0]["cost_code_id"],
                "adjustment_amount": amount,
                "adjustment_kind": kind,
            },
        )
        assert change.status_code == 201, change.text
        change_url = f"{base}/variations/{change.json()['id']}"
        assert finance_client.post(f"{change_url}/submit", json={}).status_code == 200
        assert finance_client.post(f"{change_url}/approve", json={}).status_code == 403
        approved = cfo_client.post(f"{change_url}/approve", json={})
        assert approved.status_code == 200, approved.text
        assert finance_client.get(detail_url).json()["revised_contract_value_inc_tax"] == expected
    detail = finance_client.get(detail_url).json()
    assert detail["original_contract_value_ex_tax"] == "1000000.00"
    assert detail["approved_additions"] == "100000.00"
    assert detail["approved_reductions"] == "50000.00"
    assert detail["remaining_contract_balance"] == "892500.00"
    reverse = finance_client.post(
        f"{base}/payments/{paid.json()['id']}/reverse", json={"reason": "Duplicate bank record"}
    )
    assert reverse.status_code == 200, reverse.text
    assert finance_client.get(detail_url).json()["remaining_contract_balance"] == "1102500.00"
    assert (
        finance_client.post(
            f"{base}/payments/{paid.json()['id']}/reverse", json={"reason": "Again"}
        ).status_code
        == 409
    )
    assert db.scalar(
        select(AuditEvent.id).where(
            AuditEvent.action == "construction.paid_contract_payment_registered"
        )
    )


def test_signed_contract_requires_evidence_and_keeps_scope(
    finance_client: TestClient, admin_client: TestClient, project_id: str, currency_id: str
) -> None:
    invalid = create_contract(finance_client, project_id, currency_id, signed_contract=True)
    assert invalid.status_code == 422
    assert (
        create_contract(
            admin_client, project_id, currency_id, signed_contract=True, signed_reference="Signed"
        ).status_code
        == 403
    )
    contract = signed(finance_client, project_id, currency_id)
    base = construction_url(project_id)
    assert (
        payment(finance_client, base, contract["id"], currency_id, proof_reference=" ").status_code
        == 422
    )
    assert payment(finance_client, base, str(uuid.uuid4()), currency_id).status_code == 404
    assert payment(admin_client, base, contract["id"], currency_id).status_code == 403


def test_unused_contract_and_draft_change_removal(
    finance_client: TestClient, admin_client: TestClient, project_id: str, currency_id: str
) -> None:
    contract = signed(finance_client, project_id, currency_id)
    base = construction_url(project_id)
    url = f"{base}/contracts/{contract['id']}"
    assert admin_client.delete(url, params={"reason": "Test"}).status_code == 403
    change = finance_client.post(
        f"{url}/variations",
        json={
            "variation_number": "CUT",
            "description": "Client-supplied tiles",
            "requested_date": "2026-09-20",
            "cost_code_id": contract["lines"][0]["cost_code_id"],
            "adjustment_amount": "10000.00",
            "adjustment_kind": "reduction",
        },
    )
    assert change.status_code == 201, change.text
    assert finance_client.delete(url, params={"reason": "Mistaken entry"}).status_code == 409
    change_url = f"{base}/variations/{change.json()['id']}"
    assert finance_client.delete(change_url, params={"reason": "Duplicate"}).status_code == 204
    assert finance_client.delete(change_url, params={"reason": "Duplicate"}).status_code == 404
    assert finance_client.delete(url, params={"reason": "Mistaken signed entry"}).status_code == 204
    retained = finance_client.get(url).json()
    assert retained["status"] == "cancelled"
    assert retained["remaining_contract_balance"] is None
    assert retained["cancellation_reason"] == "Mistaken signed entry"
    assert finance_client.delete(url, params={"reason": "Again"}).status_code == 409


def test_payment_migration_roundtrip(
    db: Session, finance_client: TestClient, project_id: str, currency_id: str
) -> None:
    db.commit()
    config = alembic_config()
    command.downgrade(config, "0032_building_units")
    command.upgrade(config, "head")
    contract = signed(finance_client, project_id, currency_id)
    paid = payment(finance_client, construction_url(project_id), contract["id"], currency_id)
    assert paid.status_code == 201, paid.text
    with pytest.raises(RuntimeError, match="history must be retained"):
        command.downgrade(config, "0032_building_units")
    # The refusal leaves the database exactly where it was, at whatever the head
    # is — not at the revision that happened to be head when this was written. A
    # later merge revision moves it, and a test naming one directly turns that
    # ordinary event into a failure in a file about contract payments.
    assert db.scalar(text("SELECT version_num FROM alembic_version")) == HEAD_REVISION


def test_existing_draft_signed_activation_preserves_lines(
    finance_client: TestClient, project_id: str, currency_id: str, cost_codes: dict[str, str]
) -> None:
    base = construction_url(project_id)
    draft = create_contract(finance_client, project_id, currency_id).json()
    url = f"{base}/contracts/{draft['id']}"
    assert (
        set_contract_line(
            finance_client,
            project_id,
            draft["id"],
            sequence=1,
            cost_code_id=cost_codes["hard"],
            original_amount_ex_tax="900000.00",
        ).status_code
        == 200
    )
    blocked = finance_client.post(f"{url}/register-signed", json={"reason": "Signed agreement"})
    assert blocked.status_code == 200, blocked.text
    assert blocked.json()["line_total"] == "1000000.00"
    draft = create_contract(
        finance_client, project_id, currency_id, contract_number="CT-002"
    ).json()
    url = f"{base}/contracts/{draft['id']}"
    assert (
        set_contract_line(
            finance_client,
            project_id,
            draft["id"],
            sequence=1,
            cost_code_id=cost_codes["hard"],
            original_amount_ex_tax="1000000.00",
        ).status_code
        == 200
    )
    assert finance_client.post(f"{url}/submit", json={}).status_code == 200
    active = finance_client.post(f"{url}/register-signed", json={"reason": "Signed agreement"})
    assert active.status_code == 200, active.text
    assert active.json()["status"] == "active"
    assert len(active.json()["lines"]) == 1
    assert active.json()["lines"][0]["cost_code_id"] == cost_codes["hard"]
    assert active.json()["remaining_contract_balance"] is None
    assert (
        finance_client.post(f"{url}/register-signed", json={"reason": "Again"}).status_code == 409
    )


def test_actual_overpayment_is_a_credit_and_duplicate_is_rejected(
    finance_client: TestClient, project_id: str, currency_id: str
) -> None:
    contract = signed(finance_client, project_id, currency_id)
    base = construction_url(project_id)
    result = payment(finance_client, base, contract["id"], currency_id, amount="1100000.00")
    assert result.status_code == 201, result.text
    assert payment(finance_client, base, contract["id"], currency_id).status_code == 409
    detail = finance_client.get(f"{base}/contracts/{contract['id']}").json()
    assert detail["remaining_contract_balance"] == "-50000.00"
    assert (
        finance_client.delete(
            f"{base}/contracts/{contract['id']}", params={"reason": "Mistake"}
        ).status_code
        == 409
    )


def test_direct_workflow_removal_respects_project_and_phase_scope(
    finance_client: TestClient,
    admin_client: TestClient,
    finance: User,
    project_id: str,
    currency_id: str,
    country_pack_id: str,
    db: Session,
) -> None:
    contract = signed(finance_client, project_id, currency_id)
    original = construction_url(project_id)
    second = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="SECOND")
    )
    assert second.status_code == 201, second.text
    second_id = second.json()["id"]
    grant_access(admin_client, second_id, finance)
    wrong = construction_url(second_id)
    assert payment(finance_client, wrong, contract["id"], currency_id).status_code == 404
    assert (
        finance_client.post(
            f"{wrong}/contracts/{contract['id']}/register-signed", json={"reason": "Signed"}
        ).status_code
        == 404
    )
    assert (
        finance_client.delete(
            f"{wrong}/contracts/{contract['id']}", params={"reason": "Wrong project"}
        ).status_code
        == 404
    )
    change = finance_client.post(
        f"{original}/contracts/{contract['id']}/variations",
        json={
            "variation_number": "SCOPE",
            "description": "Client item",
            "requested_date": "2026-09-20",
            "cost_code_id": contract["lines"][0]["cost_code_id"],
            "adjustment_amount": "1000.00",
            "adjustment_kind": "reduction",
        },
    ).json()
    assert (
        admin_client.delete(
            f"{original}/variations/{change['id']}", params={"reason": "Denied"}
        ).status_code
        == 403
    )
    assert (
        finance_client.delete(
            f"{wrong}/variations/{change['id']}", params={"reason": "Wrong project"}
        ).status_code
        == 404
    )
    assert (
        finance_client.delete(
            f"{original}/variations/{change['id']}", params={"reason": "Duplicate"}
        ).status_code
        == 204
    )
    assert db.scalar(
        select(AuditEvent.id).where(AuditEvent.action == "construction.variation_deleted")
    )
    narrow = admin_client.patch(
        f"{PROJECTS}/{project_id}/access/{finance.id}/phase-scope", json={"phase_scope": "selected"}
    )
    assert narrow.status_code == 200, narrow.text
    assert payment(finance_client, original, contract["id"], currency_id).status_code == 403
    assert (
        finance_client.delete(
            f"{original}/contracts/{contract['id']}", params={"reason": "Partial scope"}
        ).status_code
        == 403
    )


def test_total_certificate_advance_recovery_invoice_settlement(
    finance_client: TestClient,
    second_finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    currency_id: str,
) -> None:
    contract = signed(
        finance_client,
        project_id,
        currency_id,
        advance_entitlement_amount="200000.00",
        retention_rate_fraction="0.100000",
    )
    base = construction_url(project_id)
    advance = record_invoice(
        finance_client,
        project_id,
        contract["id"],
        invoice_type="advance",
        amount_ex_tax="100000.00",
    ).json()
    assert cfo_client.post(f"{base}/invoices/{advance['id']}/approve", json={}).status_code == 200
    paid = payment(
        finance_client,
        base,
        contract["id"],
        currency_id,
        invoice_id=advance["id"],
        amount="100000.00",
    )
    assert paid.status_code == 201, paid.text
    assert finance_client.get(f"{base}/invoices/{advance['id']}").json()["outstanding"] == "0.00"
    certificate = create_certificate(
        finance_client,
        project_id,
        contract["id"],
        current_work_value_ex_tax="200000.00",
        advance_recovery_amount="10000.00",
    )
    assert certificate.status_code == 201, certificate.text
    assert certificate.json()["retention_held_amount"] == "20000.00"
    assert certificate.json()["net_due"] == "170000.00"
    certified = certify(finance_client, second_finance_client, project_id, certificate.json()["id"])
    assert certified.status_code == 200, certified.text
    invoice = record_invoice(
        finance_client,
        project_id,
        contract["id"],
        invoice_number="PROGRESS-01",
        amount_ex_tax="170000.00",
        certificate_id=certificate.json()["id"],
    ).json()
    assert cfo_client.post(f"{base}/invoices/{invoice['id']}/approve", json={}).status_code == 200
    settlement = payment(
        finance_client,
        base,
        contract["id"],
        currency_id,
        invoice_id=invoice["id"],
        payment_reference="BANK-02",
        amount="170000.00",
    )
    assert settlement.status_code == 201, settlement.text
    position = finance_client.get(f"{base}/contracts/{contract['id']}").json()
    assert position["confirmed_paid"] == "270000.00"
    assert position["invoice_outstanding"] == "0.00"
    assert position["advance_outstanding"] == "90000.00"
    assert position["retention_outstanding"] == "20000.00"
    assert position["certified_to_date"] == "200000.00"
    assert (
        payment(
            finance_client,
            base,
            contract["id"],
            currency_id,
            invoice_id=invoice["id"],
            payment_reference="OVER",
            amount="0.01",
        ).status_code
        == 409
    )
    assert len(finance_client.get(f"{base}/payments").json()) == 2
    assert (
        cfo_client.post(
            f"{base}/payments/{paid.json()['id']}/reverse",
            json={"reason": "Cannot reverse recovered advance"},
        ).status_code
        == 409
    )
    assert (
        cfo_client.post(
            f"{base}/payments/{settlement.json()['id']}/reverse",
            json={"reason": "Bank returned funds"},
        ).status_code
        == 200
    )
    assert (
        finance_client.get(f"{base}/invoices/{invoice['id']}").json()["outstanding"] == "170000.00"
    )


def test_total_certificate_deletion_scope_and_atomic_validation(
    finance_client: TestClient,
    admin_client: TestClient,
    project_id: str,
    currency_id: str,
    db: Session,
) -> None:
    contract = signed(finance_client, project_id, currency_id)
    base = construction_url(project_id)
    bad = create_certificate(
        finance_client,
        project_id,
        contract["id"],
        current_work_value_ex_tax="100.00",
        cost_code_id=str(uuid.uuid4()),
    )
    assert bad.status_code == 422, bad.text
    assert finance_client.get(f"{base}/certificates").json() == []
    created = create_certificate(
        finance_client, project_id, contract["id"], current_work_value_ex_tax="100.00"
    )
    assert created.status_code == 201, created.text
    url = f"{base}/certificates/{created.json()['id']}"
    assert admin_client.delete(url, params={"reason": "Wrong role"}).status_code == 403
    assert (
        finance_client.delete(
            f"{base}/certificates/{uuid.uuid4()}", params={"reason": "Wrong id"}
        ).status_code
        == 404
    )
    assert finance_client.delete(url, params={"reason": "Duplicate draft"}).status_code == 204
    assert finance_client.delete(url, params={"reason": "Duplicate draft"}).status_code == 404
    event = db.scalar(
        select(AuditEvent).where(AuditEvent.action == "construction.draft_certificate_deleted")
    )
    assert event is not None


def test_invoice_settlement_rejects_unapproved_or_other_contract(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    currency_id: str,
) -> None:
    first = signed(finance_client, project_id, currency_id, advance_entitlement_amount="100000.00")
    other = signed(finance_client, project_id, currency_id, contract_number="OTHER")
    base = construction_url(project_id)
    invoice = record_invoice(
        finance_client, project_id, first["id"], invoice_type="advance", amount_ex_tax="10000.00"
    ).json()
    assert (
        payment(
            finance_client,
            base,
            first["id"],
            currency_id,
            invoice_id=invoice["id"],
            amount="100.00",
        ).status_code
        == 409
    )
    assert cfo_client.post(f"{base}/invoices/{invoice['id']}/approve", json={}).status_code == 200
    assert (
        payment(
            finance_client,
            base,
            other["id"],
            currency_id,
            invoice_id=invoice["id"],
            amount="100.00",
        ).status_code
        == 404
    )
    assert finance_client.get(f"{base}/payments").json() == []


def test_submitted_contract_without_lines_activates_from_total(
    finance_client: TestClient,
    project_id: str,
    currency_id: str,
    db: Session,
) -> None:
    from app.modules.construction.models import Contract

    draft = create_contract(finance_client, project_id, currency_id).json()
    row = db.get(Contract, uuid.UUID(draft["id"]))
    assert row is not None
    row.status = "submitted"
    db.commit()
    base = construction_url(project_id)
    result = finance_client.post(
        f"{base}/contracts/{draft['id']}/register-signed",
        json={"reason": "Previously signed agreement"},
    )
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "active"
    assert result.json()["line_total"] == "1000000.00"
