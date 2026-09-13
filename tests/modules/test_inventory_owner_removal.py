"""Owner removal affects current registers, never retained financial evidence."""

import uuid

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.inventory.models import Unit, UnitAreaSchedule
from app.modules.sales.models import SaleContract
from tests.conftest import alembic_config
from tests.factories import client_for, make_user
from tests.modules.conftest import PROJECTS, inventory_url, project_payload, sales_url


@pytest.fixture
def owner(db: Session) -> TestClient:
    return client_for(make_user(db, email="remove-unit@example.com", roles=("master_admin",)).email)


def test_owner_removes_signed_unit_from_both_registers_and_retains_history(
    owner: TestClient, admin_client: TestClient, project_id: str, active_sale: str, db: Session
) -> None:
    sale = db.get(SaleContract, uuid.UUID(active_sale))
    unit_id = sale.unit_id
    before = (sale.status, sale.total_contract_price)
    url = f"{inventory_url(project_id)}/units/{unit_id}"
    assert admin_client.delete(url, params={"reason": "Remove"}).status_code == 403
    assert owner.delete(url, params={"reason": "   "}).status_code == 422
    removed = owner.delete(url, params={"reason": "Duplicate development unit"})
    assert removed.status_code == 204, removed.text
    db.expire_all()
    assert db.get(Unit, unit_id).removed_at is not None
    assert db.get(Unit, unit_id).is_active is False
    assert (sale.status, sale.total_contract_price) == before
    assert owner.get(url).status_code == 404
    register = owner.get(f"{inventory_url(project_id)}/units").json()
    assert str(unit_id) not in [row["id"] for row in register["units"]]
    sales = owner.get(f"{sales_url(project_id)}/transactions").json()
    assert active_sale not in [row["id"] for row in sales["items"]]
    history = owner.get(f"{sales_url(project_id)}/transactions", params={"history": True}).json()
    assert active_sale in [row["id"] for row in history["items"]]
    assert owner.delete(url, params={"reason": "Retry"}).status_code == 204
    events = list(
        db.scalars(
            select(AuditEvent).where(
                AuditEvent.entity_id == unit_id, AuditEvent.action == "unit.removed"
            )
        )
    )
    assert len(events) == 1
    assert events[0].reason == "Duplicate development unit"
    assert (
        owner.patch(url, json={"is_active": True, "activity_reason": "Restore"}).status_code == 404
    )


def test_priced_unit_retains_measurements_when_physical_deletion_is_impossible(
    owner: TestClient, project_id: str, priced_unit: str, unit_id: str, db: Session
) -> None:
    before = list(db.scalars(select(UnitAreaSchedule.id)))
    response = owner.delete(
        f"{inventory_url(project_id)}/units/{unit_id}", params={"reason": "Duplicate"}
    )
    assert response.status_code == 204, response.text
    assert list(db.scalars(select(UnitAreaSchedule.id))) == before
    db.expire_all()
    assert db.get(Unit, uuid.UUID(unit_id)).removed_at is not None


def test_removal_refuses_wrong_project(
    owner: TestClient,
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    country_pack_id: str,
    currency_id: str,
) -> None:
    other = admin_client.post(
        PROJECTS,
        json=project_payload(
            country_pack_id, currency_id, code="OTHER-REMOVE", name="Other development"
        ),
    ).json()["id"]
    assert (
        owner.delete(
            f"{inventory_url(other)}/units/{unit_id}", params={"reason": "Wrong project"}
        ).status_code
        == 404
    )
    assert owner.get(f"{inventory_url(project_id)}/units/{unit_id}").status_code == 200


def test_removal_migration_and_history_guard(
    owner: TestClient, project_id: str, active_sale: str, db: Session
) -> None:
    config = alembic_config()
    db.rollback()
    command.downgrade(config, "0029_merge_installment_tax")
    command.upgrade(config, "head")
    command.check(config)
    sale = db.get(SaleContract, uuid.UUID(active_sale))
    response = owner.delete(
        f"{inventory_url(project_id)}/units/{sale.unit_id}", params={"reason": "Retain history"}
    )
    assert response.status_code == 204, response.text
    db.rollback()
    with pytest.raises(RuntimeError, match="Removed unit history"):
        command.downgrade(config, "0029_merge_installment_tax")
    command.upgrade(config, "head")
