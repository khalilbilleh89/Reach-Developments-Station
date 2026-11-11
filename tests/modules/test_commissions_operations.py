"""Fixed client commission lifecycle, scope, precision and retained history."""

from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.access.models import User
from app.modules.audit.models import AuditEvent
from app.modules.commissions.models import OperationsCommission
from tests.modules.conftest import (
    PROJECTS,
    client_for,
    grant_access,
    make_user,
    project_payload,
    sales_url,
)


def url(project_id: str) -> str:
    return f"/api/v1/projects/{project_id}/commissions/operations"


def payload(buyer_id: str, **overrides: object) -> dict:
    return {
        "client_id": buyer_id,
        "beneficiary_name": "Operations recipient",
        "reason": "Client coordination",
        "amount": "1250.50",
        **overrides,
    }


def test_operations_lifecycle_and_retention(
    finance_client: TestClient,
    admin_client: TestClient,
    project_id: str,
    buyer_id: str,
    db: Session,
) -> None:
    base = url(project_id)
    before_sales = finance_client.get(f"/api/v1/projects/{project_id}/commissions").json()
    created = finance_client.post(base, json=payload(buyer_id))
    assert created.status_code == 201, created.text
    row = created.json()
    assert row["amount"] == "1250.50"
    assert row["client_display"] == "Rana Haddad"
    register = finance_client.get(base).json()
    assert register["items"] == [row]
    assert set(register["clients"][0]) == {"id", "display_name", "client_number"}
    edited = finance_client.put(
        f"{base}/{row['id']}",
        json={**payload(buyer_id, amount="999.99", reason="Updated reason"), "expected_version": 1},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["version"] == 2
    assert edited.json()["currency_id"] == row["currency_id"]
    assert (
        finance_client.put(
            f"{base}/{row['id']}", json={**payload(buyer_id), "expected_version": 1}
        ).status_code
        == 409
    )
    deletion = f"{base}/{row['id']}/delete"
    assert (
        finance_client.post(deletion, json={"expected_version": 1, "reason": "Mistake"}).status_code
        == 409
    )
    assert (
        finance_client.post(deletion, json={"expected_version": 2, "reason": "  "}).status_code
        == 422
    )
    assert (
        finance_client.post(
            deletion, json={"expected_version": 2, "reason": "Mistaken entry"}
        ).status_code
        == 204
    )
    assert finance_client.get(base).json()["items"] == []
    assert (
        finance_client.post(deletion, json={"expected_version": 2, "reason": "Again"}).status_code
        == 404
    )
    retained = db.get(OperationsCommission, UUID(row["id"]))
    assert retained.is_deleted and retained.version == 3
    events = list(
        db.scalars(
            select(AuditEvent)
            .where(AuditEvent.entity_id == UUID(row["id"]))
            .order_by(AuditEvent.occurred_at)
        )
    )
    assert {event.action for event in events} == {
        "operations_commission.created",
        "operations_commission.updated",
        "operations_commission.deleted",
    }
    assert finance_client.get(f"/api/v1/projects/{project_id}/commissions").json() == before_sales
    assert (
        admin_client.delete(
            f"{sales_url(project_id)}/clients/{buyer_id}",
            params={"reason": "Cannot erase evidence"},
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"amount": "0"},
        {"amount": "-1"},
        {"amount": "0.001"},
        {"amount": "NaN"},
        {"amount": "Infinity"},
        {"amount": "10000000000000000"},
        {"beneficiary_name": "  "},
        {"reason": "  "},
        {"currency_id": str(uuid4())},
    ],
)
def test_operations_reject_invalid_terms(
    finance_client: TestClient, project_id: str, buyer_id: str, changes: dict
) -> None:
    assert (
        finance_client.post(url(project_id), json=payload(buyer_id, **changes)).status_code == 422
    )
    assert finance_client.get(url(project_id)).json()["items"] == []


def test_operations_scope_and_roles(
    finance_client: TestClient,
    cfo_client: TestClient,
    admin_client: TestClient,
    sales_ops_client: TestClient,
    project_id: str,
    buyer_id: str,
    country_pack_id: str,
    currency_id: str,
    finance: User,
    db: Session,
) -> None:
    second = admin_client.post(
        PROJECTS,
        json=project_payload(
            country_pack_id, currency_id, code="OTHER-OPS", name="Other operations project"
        ),
    ).json()["id"]
    created = finance_client.post(url(project_id), json=payload(buyer_id)).json()
    assert cfo_client.get(url(project_id)).status_code == 200
    assert cfo_client.post(url(project_id), json=payload(buyer_id)).status_code == 403
    assert (
        cfo_client.put(
            f"{url(project_id)}/{created['id']}", json={**payload(buyer_id), "expected_version": 1}
        ).status_code
        == 403
    )
    assert (
        cfo_client.post(
            f"{url(project_id)}/{created['id']}/delete",
            json={"expected_version": 1, "reason": "Denied"},
        ).status_code
        == 403
    )
    assert finance_client.get(url(second)).status_code == 404
    grant_access(admin_client, second, finance)
    assert finance_client.post(url(second), json=payload(buyer_id)).status_code == 404
    assert (
        finance_client.put(
            f"{url(second)}/{created['id']}", json={**payload(buyer_id), "expected_version": 1}
        ).status_code
        == 404
    )
    assert (
        finance_client.post(
            f"{url(second)}/{created['id']}/delete",
            json={"expected_version": 1, "reason": "Wrong project"},
        ).status_code
        == 404
    )
    assert (
        sales_ops_client.patch(
            f"{sales_url(project_id)}/clients/{buyer_id}", json={"is_active": False}
        ).status_code
        == 200
    )
    assert finance_client.post(url(project_id), json=payload(buyer_id)).status_code == 409
    assert (
        finance_client.put(
            f"{url(project_id)}/{created['id']}", json={**payload(buyer_id), "expected_version": 1}
        ).status_code
        == 200
    )


def test_operations_migration_roundtrip(
    finance_client: TestClient, project_id: str, buyer_id: str, db: Session
) -> None:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    db.rollback()
    command.downgrade(config, "0069_company_profile")
    command.upgrade(config, "head")
    command.check(config)
    row = finance_client.post(url(project_id), json=payload(buyer_id)).json()
    assert (
        finance_client.post(
            f"{url(project_id)}/{row['id']}/delete",
            json={"expected_version": 1, "reason": "Retain"},
        ).status_code
        == 204
    )
    db.rollback()
    with pytest.raises(RuntimeError, match="retained operations commission"):
        command.downgrade(config, "0069_company_profile")
    command.upgrade(config, "head")
    assert db.scalar(text("SELECT count(*) FROM operations_commissions WHERE is_deleted")) == 1


def test_operations_phase_scope_denied(
    admin_client: TestClient, project_id: str, phase_id: str, buyer_id: str, db: Session
) -> None:
    scoped = make_user(db, email="ops-phase@example.com", roles=("finance",))
    grant_access(admin_client, project_id, scoped)
    assert (
        admin_client.patch(
            f"/api/v1/projects/{project_id}/access/{scoped.id}/phase-scope",
            json={"phase_scope": "selected"},
        ).status_code
        == 200
    )
    assert (
        admin_client.put(
            f"/api/v1/projects/{project_id}/access/{scoped.id}/phases/{phase_id}"
        ).status_code
        == 200
    )
    caller = client_for(scoped.email)
    assert caller.get(url(project_id)).status_code == 403
    assert caller.post(url(project_id), json=payload(buyer_id)).status_code == 403
