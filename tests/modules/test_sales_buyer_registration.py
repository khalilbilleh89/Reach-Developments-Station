"""One owner action registers the sale atomically without inventing legal or cash evidence."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.sales.models import Client, Reservation, SaleContract, SaleLegalEvent
from tests.factories import client_for, make_user
from tests.modules.conftest import inventory_url, sales_url


@pytest.fixture
def owner_client(db: Session) -> TestClient:
    owner = make_user(db, email="owner-sales@example.com", roles=("master_admin",))
    return client_for(owner.email)


def new_buyer(unit_id: str) -> dict:
    return {
        "unit_id": unit_id,
        "buyer": {"display_name": "Test Buyer", "sole_purchaser_name": "Test Buyer"},
        "reason": "Owner confirms the commercial sale; legal completion is pending.",
    }


def test_owner_registers_new_buyer_as_sold_without_fictional_signatures(
    owner_client: TestClient,
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    priced_unit: str,
    db: Session,
) -> None:
    response = owner_client.post(
        f"{sales_url(project_id)}/buyer-registrations", json=new_buyer(unit_id)
    )
    assert response.status_code == 201, response.text
    sale = response.json()["sale"]
    assert sale["status"] == "signature_pending"
    assert len(response.json()["parties"]) == 1
    assert response.json()["parties"][0]["share_fraction"] == "1.000000"
    unit = admin_client.get(f"{inventory_url(project_id)}/units/{unit_id}").json()
    assert unit["commercial_status"] == "contract_pending"
    assert unit["legal_status"] == "no_spa"
    assert unit["collection_status"] == "not_started"
    assert db.scalar(select(func.count()).select_from(SaleLegalEvent)) == 0
    reservation = db.get(Reservation, uuid.UUID(sale["reservation_id"]))
    assert reservation.status == "converted"
    assert reservation.deposit_gate_status == "waived"
    sold = admin_client.get(
        f"{inventory_url(project_id)}/units", params={"commercial_status": "sold"}
    ).json()
    assert sold["sold_count"] == sold["total"] == 1
    assert sold["available_count"] == 0
    duplicate = owner_client.post(
        f"{sales_url(project_id)}/buyer-registrations", json=new_buyer(unit_id)
    )
    assert duplicate.status_code == 409, duplicate.text
    assert db.scalar(select(func.count()).select_from(Client)) == 1
    assert db.scalar(select(func.count()).select_from(SaleContract)) == 1


def test_failed_registration_rolls_back_buyer_and_unit_change(
    owner_client: TestClient,
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    db: Session,
) -> None:
    response = owner_client.post(
        f"{sales_url(project_id)}/buyer-registrations", json=new_buyer(unit_id)
    )
    assert response.status_code == 409, response.text
    assert db.scalar(select(func.count()).select_from(Client)) == 0
    assert db.scalar(select(func.count()).select_from(Reservation)) == 0
    unit = admin_client.get(f"{inventory_url(project_id)}/units/{unit_id}").json()
    assert unit["commercial_status"] == "unreleased"


def test_owner_converts_existing_reservation_for_same_buyer(
    owner_client: TestClient,
    project_id: str,
    unit_id: str,
    buyer_id: str,
    active_reservation: str,
) -> None:
    response = owner_client.post(
        f"{sales_url(project_id)}/buyer-registrations",
        json={
            "unit_id": unit_id,
            "client_id": buyer_id,
            "reason": "Buyer confirms purchase",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["sale"]["reservation_id"] == active_reservation


def test_reserved_unit_cannot_be_assigned_to_a_different_buyer(
    owner_client: TestClient,
    project_id: str,
    unit_id: str,
    active_reservation: str,
    db: Session,
) -> None:
    before = db.scalar(select(func.count()).select_from(Client))
    response = owner_client.post(
        f"{sales_url(project_id)}/buyer-registrations", json=new_buyer(unit_id)
    )
    assert response.status_code == 409, response.text
    assert db.scalar(select(func.count()).select_from(Client)) == before
    assert db.scalar(select(func.count()).select_from(SaleContract)) == 0


def test_ordinary_administrator_cannot_use_owner_sale_override(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
) -> None:
    response = admin_client.post(
        f"{sales_url(project_id)}/buyer-registrations", json=new_buyer(unit_id)
    )
    assert response.status_code == 403, response.text


def test_registration_requires_one_buyer_source_and_nonblank_reason(
    owner_client: TestClient,
    project_id: str,
    unit_id: str,
) -> None:
    url = f"{sales_url(project_id)}/buyer-registrations"
    response = owner_client.post(url, json={**new_buyer(unit_id), "client_id": str(uuid.uuid4())})
    assert response.status_code == 422, response.text
    response = owner_client.post(url, json={**new_buyer(unit_id), "reason": "   "})
    assert response.status_code == 422, response.text
