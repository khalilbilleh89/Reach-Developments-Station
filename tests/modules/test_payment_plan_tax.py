"""Per-installment VAT behavior, persisted invariants and retained history."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.payment_plans.schedule import installment_tax
from app.modules.payment_plans.service import cashflow_schedule_rows
from tests.conftest import alembic_config
from tests.modules.conftest import (
    collection_account,
    current_version_id,
    fixed_row,
    plan_detail,
    plans_url,
    write_schedule,
)


def tax_rows() -> list[dict[str, object]]:
    return [
        fixed_row(1, "0.2", "2026-03-01", tax_rate_fraction="0.19"),
        fixed_row(2, "0.3", "2026-06-01", tax_rate_fraction="0.05"),
        fixed_row(3, "0.5", "2026-09-01", tax_rate_fraction="0"),
    ]


def test_mixed_rates_survive_approval_activation_and_revision(
    db: Session,
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    plan_id: str,
) -> None:
    version = current_version_id(collections_client, project_id, plan_id)
    before = plan_detail(collections_client, project_id, plan_id)["current"]["version"]
    saved = write_schedule(
        collections_client,
        project_id,
        plan_id,
        version,
        tax_rows(),
        charge_allocation_mode="per_installment",
    )
    assert saved.status_code == 200, saved.text
    data = saved.json()
    expected = [
        installment_tax(Decimal(r["principal_amount"]), Decimal(rate))
        for r, rate in zip(data["installments"], ["0.19", "0.05", "0"], strict=True)
    ]
    assert [Decimal(r["tax_amount"]) for r in data["installments"]] == expected
    assert Decimal(data["reconciliation"]["scheduled_tax_total"]) == sum(expected)
    assert data["reconciliation"]["is_reconciled"]
    assert data["version"]["tax_total_snapshot"] == before["tax_total_snapshot"]
    base = f"{plans_url(project_id)}/{plan_id}/versions/{version}"
    assert collections_client.post(f"{base}/submit", json={}).status_code == 200
    assert (
        cfo_client.post(f"{base}/approve", json={"reason": "Approved installment VAT"}).status_code
        == 200
    )
    activated = cfo_client.post(f"{base}/activate", json={})
    assert activated.status_code == 200, activated.text
    sale_id = plan_detail(collections_client, project_id, plan_id)["sale_id"]
    account = collection_account(collections_client, project_id, sale_id)
    assert account["scheduled_total"] == data["reconciliation"]["scheduled_buyer_total"]
    assert account["outstanding_total"] == account["scheduled_total"]
    forecast = cashflow_schedule_rows(db, project_id=uuid.UUID(project_id), as_of=date.today())
    assert sum(r.amount for r in forecast) == Decimal(account["scheduled_total"])
    db.rollback()
    assert (
        write_schedule(
            collections_client,
            project_id,
            plan_id,
            version,
            tax_rows(),
            charge_allocation_mode="per_installment",
        ).status_code
        == 409
    )
    revised = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/versions",
        json={"change_reason": "Reduced VAT approval"},
    )
    assert revised.status_code == 201, revised.text
    detail = plan_detail(collections_client, project_id, plan_id)
    assert [r["tax_rate_fraction"] for r in detail["current"]["installments"]] == [
        "0.190000",
        "0.050000",
        "0.000000",
    ]
    assert detail["active"]["version"]["id"] == version
    assert detail["current"]["reconciliation"]["is_reconciled"]


@pytest.mark.parametrize("rate", [None, "-0.01", "1.01", "NaN", "0.1234567"])
def test_missing_or_invalid_rate_is_rejected(
    collections_client: TestClient, project_id: str, plan_id: str, rate: str | None
) -> None:
    version = current_version_id(collections_client, project_id, plan_id)
    rows = [fixed_row(1, "1", "2026-03-01", tax_rate_fraction=rate)]
    result = write_schedule(
        collections_client,
        project_id,
        plan_id,
        version,
        rows,
        charge_allocation_mode="per_installment",
    )
    assert result.status_code == 422, result.text


def test_tax_rounds_each_installment_independently() -> None:
    assert installment_tax(Decimal("0.10"), Decimal("0.05")) == Decimal("0.01")
    assert installment_tax(Decimal("999.99"), Decimal("0")) == Decimal("0.00")


def test_tax_migration_roundtrip(
    db: Session, collections_client: TestClient, project_id: str, reconciled_plan: tuple[str, str]
) -> None:
    plan_id, version = reconciled_plan
    original = plan_detail(collections_client, project_id, plan_id)["current"]["installments"]
    db.rollback()
    command.downgrade(alembic_config(), "0025_prelaunch_master")
    command.upgrade(alembic_config(), "head")
    assert (
        plan_detail(collections_client, project_id, plan_id)["current"]["installments"] == original
    )
    saved = write_schedule(
        collections_client,
        project_id,
        plan_id,
        version,
        tax_rows(),
        charge_allocation_mode="per_installment",
    )
    assert saved.status_code == 200, saved.text
    row_id = saved.json()["installments"][0]["id"]
    with pytest.raises(IntegrityError):
        db.execute(
            text("UPDATE payment_plan_installments SET tax_amount=tax_amount+1 WHERE id=:id"),
            {"id": row_id},
        )
        db.commit()
    db.rollback()
    with pytest.raises(RuntimeError, match="tax history exists"):
        command.downgrade(alembic_config(), "0025_prelaunch_master")
    command.check(alembic_config())


def test_rate_mode_amounts_removal_permissions_and_scope(
    collections_client: TestClient,
    engineer_client: TestClient,
    project_id: str,
    plan_id: str,
) -> None:
    version = current_version_id(collections_client, project_id, plan_id)
    original = plan_detail(collections_client, project_id, plan_id)["current"]["version"]
    principal = original["contract_value_covered"]
    row = fixed_row(1, "1", "2026-03-01", principal_amount=principal, tax_rate_fraction="0.05")
    denied = write_schedule(
        engineer_client,
        project_id,
        plan_id,
        version,
        [row],
        allocation_mode="amount",
        charge_allocation_mode="per_installment",
    )
    assert denied.status_code == 403
    wrong = write_schedule(
        collections_client,
        project_id,
        str(uuid.uuid4()),
        version,
        [row],
        allocation_mode="amount",
        charge_allocation_mode="per_installment",
    )
    assert wrong.status_code == 404
    saved = write_schedule(
        collections_client,
        project_id,
        plan_id,
        version,
        tax_rows(),
        charge_allocation_mode="per_installment",
    )
    assert saved.status_code == 200
    removed = write_schedule(
        collections_client,
        project_id,
        plan_id,
        version,
        [row],
        allocation_mode="amount",
        charge_allocation_mode="per_installment",
    )
    assert removed.status_code == 200, removed.text
    assert len(removed.json()["installments"]) == 1
    assert removed.json()["reconciliation"]["is_reconciled"]
    assert Decimal(removed.json()["installments"][0]["tax_amount"]) == installment_tax(
        Decimal(principal), Decimal("0.05")
    )
    # A rate must never be silently ignored in an older charge mode.
    assert (
        write_schedule(collections_client, project_id, plan_id, version, [row]).status_code == 422
    )
    # Incomplete principal still blocks approval even with correct tax.
    row["principal_amount"] = str(Decimal(principal) - Decimal("1"))
    short = write_schedule(
        collections_client,
        project_id,
        plan_id,
        version,
        [row],
        allocation_mode="amount",
        charge_allocation_mode="per_installment",
    )
    assert short.status_code == 200
    assert not short.json()["reconciliation"]["is_reconciled"]
