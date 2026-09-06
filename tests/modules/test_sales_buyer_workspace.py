"""The short buyer form keeps ownership, privacy and transaction boundaries."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.sales import service
from tests.modules.conftest import sales_url


def test_sole_purchaser_registration_is_reconciled_and_redacted(
    advisor_client: TestClient,
    finance_client: TestClient,
    operational_project: str,
    db: Session,
) -> None:
    base = sales_url(operational_project)
    response = advisor_client.post(
        f"{base}/clients",
        json={
            "display_name": "Buyer workspace",
            "sole_purchaser_name": "Legal purchaser name",
            "phone": "+962790000001",
            "email": "workspace@example.com",
        },
    )
    assert response.status_code == 201, response.text
    buyer = response.json()
    assert buyer["owner_advisor_user_id"] is not None
    parties = advisor_client.get(f"{base}/clients/{buyer['id']}/parties").json()
    assert len(parties) == 1
    assert parties[0]["name_as_identification"] == "Legal purchaser name"
    assert parties[0]["share_fraction"] == "1.000000"
    assert parties[0]["is_primary"] is True
    shares = advisor_client.get(f"{base}/clients/{buyer['id']}/share-reconciliation").json()
    assert shares["total_share_fraction"] == "1.000000"
    redacted = finance_client.get(f"{base}/clients/{buyer['id']}")
    assert redacted.status_code == 200
    assert "phone" not in redacted.json()
    assert "email" not in redacted.json()
    audit = db.execute(
        text("SELECT action, after_data FROM audit_events WHERE entity_id = :id"),
        {"id": parties[0]["id"]},
    ).all()
    assert len(audit) == 1
    assert audit[0].action == "client_party.created"
    assert "Legal purchaser name" not in str(audit[0].after_data)


def test_joint_buyer_remains_explicit_and_invalid_input_does_not_create_a_client(
    sales_ops_client: TestClient, legal_client: TestClient, operational_project: str
) -> None:
    base = sales_url(operational_project)
    payload = {"display_name": "Joint purchasers"}
    assert legal_client.post(f"{base}/clients", json=payload).status_code == 403
    response = sales_ops_client.post(f"{base}/clients", json=payload)
    assert response.status_code == 201
    buyer_id = response.json()["id"]
    assert sales_ops_client.get(f"{base}/clients/{buyer_id}/parties").json() == []
    refused = sales_ops_client.post(
        f"{base}/clients", json={"display_name": "Invalid", "sole_purchaser_name": " "}
    )
    assert refused.status_code == 422
    assert len(sales_ops_client.get(f"{base}/clients").json()) == 1


def test_failure_to_record_ownership_rolls_back_buyer_registration(
    sales_ops_client: TestClient,
    operational_project: str,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = service.record_event

    def fail_party_audit(*args: object, **kwargs: object) -> object:
        if kwargs.get("action") == "client_party.created":
            raise RuntimeError("Simulated ownership write failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(service, "record_event", fail_party_audit)
    with pytest.raises(RuntimeError, match="Simulated ownership"):
        sales_ops_client.post(
            f"{sales_url(operational_project)}/clients",
            json={"display_name": "Atomic buyer", "sole_purchaser_name": "Atomic name"},
        )
    assert db.scalar(text("SELECT count(*) FROM clients")) == 0
    assert db.scalar(text("SELECT count(*) FROM client_parties")) == 0
