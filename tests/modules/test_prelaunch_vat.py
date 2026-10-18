"""Explicit expense VAT uses one gross movement, with unknown legacy tax preserved."""

from decimal import Decimal

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.modules.access.models import User
from app.modules.audit.models import AuditEvent
from app.modules.cashflow.models import CashflowDevelopmentMovement
from tests.conftest import alembic_config
from tests.modules.conftest import grant_access, project_payload
from tests.modules.test_prelaunch import editable, payload, root


def vat_payload(currency_id: str, net: str = "1000.00", rate: str = "5") -> dict:
    body = payload(currency_id)
    body.pop("amount")
    return {**body, "amount_ex_vat": net, "vat_rate_percent": rate}


def expected(row: dict) -> dict:
    return {
        **editable(row),
        "amount_ex_vat": row["amount_ex_vat"],
        "vat_rate_percent": row["vat_rate_percent"],
    }


@pytest.mark.parametrize(
    "net,rate,vat,gross",
    [
        ("1000.00", "5", "50.00", "1050.00"),
        ("10.05", "10", "1.01", "11.06"),
        ("0.01", "5", "0.00", "0.01"),
        ("100.00", "0", "0.00", "100.00"),
        ("100.00", "7.125", "7.13", "107.13"),
    ],
)
def test_preview_and_record_use_identical_decimal_vat(
    finance_client: TestClient,
    project_id: str,
    currency_id: str,
    db: Session,
    net: str,
    rate: str,
    vat: str,
    gross: str,
) -> None:
    preview = finance_client.post(
        root(project_id) + "/preview", json={"amount_ex_vat": net, "vat_rate_percent": rate}
    )
    assert preview.status_code == 200, preview.text
    assert db.scalar(select(CashflowDevelopmentMovement)) is None
    assert (
        db.scalar(
            select(AuditEvent).where(AuditEvent.action == "cashflow.development_movement_recorded")
        )
        is None
    )
    created = finance_client.post(root(project_id), json=vat_payload(currency_id, net, rate))
    assert created.status_code == 201, created.text
    for answer in (created.json(), preview.json()):
        assert answer["amount"] == gross
        assert answer["amount_ex_vat"] == net
        assert answer["vat_amount"] == vat
        assert Decimal(answer["vat_rate_percent"]) == Decimal(rate)
    assert finance_client.get(root(project_id)).json()["recorded_amount"] == gross
    assert not created.json()["counts_as_cash"]


def test_vat_correction_stale_confirmation_and_removal(
    finance_client: TestClient,
    second_finance_client: TestClient,
    project_id: str,
    currency_id: str,
    db: Session,
) -> None:
    client = finance_client
    original = client.post(root(project_id), json=vat_payload(currency_id, "100.00", "5")).json()
    url = f"{root(project_id)}/{original['id']}"
    # Keep gross constant while changing tax: old amount-only stale guards would miss this.
    changes = {**expected(original), "amount_ex_vat": "105.00", "vat_rate_percent": "0"}
    changes.pop("amount")
    changed = client.patch(url, json={"expected": expected(original), "changes": changes})
    assert changed.status_code == 200, changed.text
    row = changed.json()
    assert row["amount"] == original["amount"] == "105.00"
    assert row["vat_amount"] == "0.00"
    assert (
        second_finance_client.post(
            url + "/confirm", json={"expected": expected(original)}
        ).status_code
        == 409
    )
    assert (
        second_finance_client.post(url + "/confirm", json={"expected": editable(row)}).status_code
        == 409
    )
    assert (
        client.post(
            url + "/remove", json={"expected": expected(original), "reason": "Duplicate"}
        ).status_code
        == 409
    )
    assert (
        second_finance_client.post(url + "/confirm", json={"expected": expected(row)}).status_code
        == 200
    )
    register = client.get(root(project_id)).json()
    assert register["recorded_amount"] == "0.00"
    assert register["confirmed_paid_amount"] == "105.00"
    cashflow = client.get(f"/api/v1/projects/{project_id}/cashflow/development-movements").json()
    assert cashflow[0]["amount"] == "105.00" and cashflow[0]["vat_amount"] == "0.00"
    audit = db.scalar(
        select(AuditEvent).where(AuditEvent.action == "cashflow.development_movement_corrected")
    )
    assert Decimal(audit.before_data["vat_rate_percent"]) == 5
    assert Decimal(audit.after_data["vat_rate_percent"]) == 0
    assert (
        client.patch(url, json={"expected": expected(row), "changes": changes}).status_code == 409
    )
    assert (
        second_finance_client.post(url + "/reverse", json={"reason": "Returned"}).status_code == 200
    )
    assert client.get(root(project_id)).json()["confirmed_paid_amount"] == "0.00"


def test_zero_vat_legacy_preservation_and_unconfirmed_removal(
    finance_client: TestClient,
    project_id: str,
    currency_id: str,
) -> None:
    client = finance_client
    legacy = client.post(root(project_id), json=payload(currency_id)).json()
    assert legacy["amount_ex_vat"] is legacy["vat_rate_percent"] is legacy["vat_amount"] is None
    url = f"{root(project_id)}/{legacy['id']}"
    assert (
        client.patch(
            url, json={"expected": editable(legacy), "changes": editable(legacy)}
        ).status_code
        == 200
    )
    changes = {**editable(legacy), "amount_ex_vat": "100.00"}
    changes.pop("amount")
    row = client.patch(url, json={"expected": editable(legacy), "changes": changes}).json()
    assert row["amount"] == "100.00" and row["vat_amount"] == "0.00"
    assert Decimal(row["vat_rate_percent"]) == 0
    assert (
        client.post(
            url + "/remove", json={"expected": expected(row), "reason": "Unused expense"}
        ).status_code
        == 200
    )
    assert client.get(root(project_id)).json()["recorded_amount"] == "0.00"


@pytest.mark.parametrize(
    "amounts",
    [
        {},
        {"amount_ex_vat": "-1"},
        {"amount_ex_vat": "0"},
        {"amount_ex_vat": "1.001"},
        {"amount_ex_vat": "1", "vat_rate_percent": "-1"},
        {"amount_ex_vat": "1", "vat_rate_percent": "101"},
        {"amount_ex_vat": "1", "vat_rate_percent": "1.00001"},
        {"amount_ex_vat": "1", "vat_rate_percent": "NaN"},
        {"amount_ex_vat": "1", "amount": "2"},
        {"amount": "1", "vat_rate_percent": "5"},
        {"amount_ex_vat": "9999999999999999.99", "vat_rate_percent": "100"},
    ],
)
def test_invalid_vat_is_rejected_before_persistence(
    finance_client: TestClient,
    project_id: str,
    currency_id: str,
    amounts: dict,
) -> None:
    body = payload(currency_id)
    body.pop("amount")
    assert finance_client.post(root(project_id), json={**body, **amounts}).status_code == 422
    assert finance_client.post(root(project_id) + "/preview", json=amounts).status_code == 422
    assert finance_client.get(root(project_id)).json()["expenses"] == []


def test_vat_permissions_scope_and_maker_checker(
    finance_client: TestClient,
    second_finance_client: TestClient,
    executive_client: TestClient,
    project_id: str,
    currency_id: str,
    admin_client: TestClient,
    country_pack_id: str,
    finance: User,
) -> None:
    other = admin_client.post(
        "/api/v1/projects", json=project_payload(country_pack_id, currency_id, code="VAT-OTHER")
    )
    assert other.status_code == 201, other.text
    second_project_id = other.json()["id"]
    grant_access(admin_client, second_project_id, finance)
    body = vat_payload(currency_id)
    assert executive_client.post(root(project_id), json=body).status_code == 403
    assert (
        executive_client.post(
            root(project_id) + "/preview", json={"amount_ex_vat": "100"}
        ).status_code
        == 403
    )
    row = finance_client.post(root(project_id), json=body).json()
    url = f"{root(project_id)}/{row['id']}"
    assert (
        finance_client.post(url + "/confirm", json={"expected": expected(row)}).status_code == 403
    )
    assert (
        second_finance_client.patch(
            url, json={"expected": expected(row), "changes": expected(row)}
        ).status_code
        == 403
    )
    assert (
        finance_client.post(
            f"{root(second_project_id)}/{row['id']}/confirm", json={"expected": expected(row)}
        ).status_code
        == 404
    )


def test_vat_migration_roundtrip_and_retention(
    db: Session,
    finance_client: TestClient,
    project_id: str,
    currency_id: str,
) -> None:
    legacy = finance_client.post(root(project_id), json=payload(currency_id)).json()
    db.rollback()
    command.downgrade(alembic_config(), "0045_inventory_masterplans")
    command.upgrade(alembic_config(), "head")
    stored = db.scalar(select(CashflowDevelopmentMovement))
    assert stored.amount == Decimal("1250.25") and stored.amount_ex_vat is None
    for assignment in (
        "amount_ex_vat=100, vat_rate_percent=5, amount=100",
        "amount_ex_vat=100, vat_rate_percent=NULL",
        "amount_ex_vat=100, vat_rate_percent=-1",
    ):
        with pytest.raises(SQLAlchemyError):
            db.execute(
                text(f"UPDATE cashflow_development_movements SET {assignment} WHERE id=:id"),
                {"id": legacy["id"]},
            )
            db.commit()
        db.rollback()
    response = finance_client.post(root(project_id), json=vat_payload(currency_id))
    assert response.status_code == 201, response.text
    db.rollback()
    with pytest.raises(RuntimeError, match="Retained expense VAT breakdowns"):
        command.downgrade(alembic_config(), "0045_inventory_masterplans")
    assert finance_client.get(root(project_id)).json()["recorded_amount"] == "2300.25"
