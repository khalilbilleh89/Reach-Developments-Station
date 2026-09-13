"""Master confirmation evidence, category arithmetic and migration safety."""

from decimal import Decimal

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.cashflow.models import CashflowDevelopmentMovement
from tests.conftest import alembic_config
from tests.factories import client_for, make_user
from tests.modules.test_prelaunch import editable, payload, root


def test_category_totals_follow_corrections_confirmation_removal_and_reversal(
    finance_client: TestClient,
    second_finance_client: TestClient,
    project_id: str,
    currency_id: str,
) -> None:
    client = finance_client
    empty = client.get(root(project_id)).json()
    assert len(empty["categories"]) == 10
    assert all(x["total_amount"] == "0.00" for x in empty["categories"])
    rows = []
    for category, amount in (("design", "10.01"), ("utilities", "30.03"), ("design", "5.00")):
        response = client.post(
            root(project_id), json={**payload(currency_id, category=category), "amount": amount}
        )
        assert response.status_code == 201, response.text
        rows.append(response.json())
    for row in rows[:2]:
        response = second_finance_client.post(
            f"{root(project_id)}/{row['id']}/confirm", json={"expected": editable(row)}
        )
        assert response.status_code == 200, response.text
    register = client.get(root(project_id)).json()
    categories = {x["category"]: x for x in register["categories"]}
    assert categories["design"] == {
        "category": "design",
        "recorded_amount": "5.00",
        "confirmed_paid_amount": "10.01",
        "total_amount": "15.01",
        "confirmed_share_percent": "25.00",
    }
    assert categories["utilities"]["confirmed_share_percent"] == "75.00"
    for key in ("recorded_amount", "confirmed_paid_amount"):
        assert sum(Decimal(x[key]) for x in categories.values()) == Decimal(register[key])
    row = rows[2]
    corrected = client.patch(
        f"{root(project_id)}/{row['id']}",
        json={
            "expected": editable(row),
            "changes": {**editable(row), "category": "tax", "amount": "7.13"},
        },
    ).json()
    categories = {x["category"]: x for x in client.get(root(project_id)).json()["categories"]}
    assert categories["tax"]["recorded_amount"] == "7.13"
    assert categories["design"]["recorded_amount"] == "0.00"
    assert (
        client.post(
            f"{root(project_id)}/{row['id']}/remove",
            json={"expected": editable(corrected), "reason": "Duplicate"},
        ).status_code
        == 200
    )
    assert (
        second_finance_client.post(
            f"{root(project_id)}/{rows[0]['id']}/reverse", json={"reason": "Returned"}
        ).status_code
        == 200
    )
    categories = {x["category"]: x for x in client.get(root(project_id)).json()["categories"]}
    assert categories["design"]["total_amount"] == categories["tax"]["total_amount"] == "0.00"
    assert categories["utilities"]["confirmed_share_percent"] == "100.00"


def test_master_confirmation_is_attributed_once_and_survives_role_removal(
    db: Session,
    finance_client: TestClient,
    project_id: str,
    currency_id: str,
) -> None:
    master = make_user(db, email="master-expense@example.com", roles=("master_admin",))
    client = client_for(master.email)
    row = client.post(root(project_id), json=payload(currency_id)).json()
    url = f"{root(project_id)}/{row['id']}/confirm"
    assert (
        client.post(url, json={"expected": {**editable(row), "amount": "1.00"}}).status_code == 409
    )
    assert client.post(url, json={"expected": editable(row)}).status_code == 200
    assert client.post(url, json={"expected": editable(row)}).status_code == 409
    stored = db.scalar(select(CashflowDevelopmentMovement))
    assert stored.master_self_confirmed
    assert stored.recorded_by_user_id == stored.confirmed_by_user_id == master.id
    audit = db.scalar(
        select(AuditEvent).where(AuditEvent.action == "cashflow.development_movement_confirmed")
    )
    assert audit.before_data["master_self_confirmed"] is False
    assert audit.after_data["master_self_confirmed"] is True
    assert audit.actor_user_id == master.id
    reconciliation = client.get(f"/api/v1/projects/{project_id}/cashflow/reconciliation")
    assert reconciliation.status_code == 200, reconciliation.text
    checks = {check["name"]: check for check in reconciliation.json()["checks"]}
    assert checks["development_maker_is_not_checker"]["passed"] is True
    db.execute(text("DELETE FROM user_roles WHERE user_id = :id"), {"id": master.id})
    db.commit()
    # Historical permission remains valid; another authorised user can reverse it.
    assert finance_client.get(root(project_id)).json()["confirmed_paid_amount"] == "1250.25"
    assert (
        finance_client.post(
            f"{root(project_id)}/{row['id']}/reverse", json={"reason": "Returned"}
        ).status_code
        == 200
    )
    assert finance_client.get(root(project_id)).json()["confirmed_paid_amount"] == "0.00"


def test_master_exception_does_not_cover_other_development_categories(
    db: Session,
    project_id: str,
    currency_id: str,
) -> None:
    master = make_user(db, email="master-scope@example.com", roles=("master_admin",))
    client = client_for(master.email)
    url = f"/api/v1/projects/{project_id}/cashflow/development-movements"
    row = client.post(url, json=payload(currency_id, category="land_acquisition"))
    assert row.status_code == 201, row.text
    assert client.post(f"{url}/{row.json()['id']}/confirm", json={}).status_code == 403


def test_master_migration_guards_and_rollback(
    db: Session,
    finance_client: TestClient,
    project_id: str,
    currency_id: str,
) -> None:
    row = finance_client.post(root(project_id), json=payload(currency_id)).json()
    for marker in (False, True):
        with pytest.raises(SQLAlchemyError):
            db.execute(
                text(
                    "UPDATE cashflow_development_movements SET status='confirmed', "
                    "confirmed_at=now(), confirmed_by_user_id=recorded_by_user_id, "
                    "master_self_confirmed=:marker WHERE id=:id"
                ),
                {"marker": marker, "id": row["id"]},
            )
            db.commit()
        db.rollback()
    db.rollback()
    command.downgrade(alembic_config(), "0024_merge_permits_inventory")
    command.upgrade(alembic_config(), "head")
    stored = db.scalar(select(CashflowDevelopmentMovement))
    assert stored.amount == Decimal("1250.25") and not stored.master_self_confirmed
    db.rollback()
    master = make_user(db, email="migration-master@example.com", roles=("master_admin",))
    client = client_for(master.email)
    own = client.post(root(project_id), json=payload(currency_id)).json()
    assert (
        client.post(
            f"{root(project_id)}/{own['id']}/confirm", json={"expected": editable(own)}
        ).status_code
        == 200
    )
    with pytest.raises(RuntimeError, match="Retained Master self-confirmations"):
        command.downgrade(alembic_config(), "0024_merge_permits_inventory")
    assert client.get(root(project_id)).json()["confirmed_paid_amount"] == "1250.25"
    with pytest.raises(SQLAlchemyError):
        db.execute(
            text(
                "UPDATE cashflow_development_movements SET master_self_confirmed=false WHERE id=:id"
            ),
            {"id": own["id"]},
        )
        db.commit()
    db.rollback()
