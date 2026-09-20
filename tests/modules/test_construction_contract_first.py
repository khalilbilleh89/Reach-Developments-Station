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
    construction_url,
    create_contract,
    grant_access,
    project_payload,
    set_contract_line,
)


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
    assert db.scalar(text("SELECT version_num FROM alembic_version")) == "0033_contract_payments"


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
    assert blocked.status_code == 422, blocked.text
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
