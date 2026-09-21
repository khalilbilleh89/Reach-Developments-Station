"""Focused commission calculation, reconciliation and maker/checker tests."""

from collections.abc import Iterator
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.access.models import User
from app.modules.commissions.service import _terms
from app.modules.sales.models import SaleContract
from tests.modules.conftest import PROJECTS, grant_access, project_payload, sales_url


@pytest.fixture(autouse=True)
def clean_commission_rows(db: Session) -> Iterator[None]:
    yield
    db.execute(text("TRUNCATE commission_allocations, commission_grants CASCADE"))
    db.commit()


def root(project_id: str) -> str:
    return f"/api/v1/projects/{project_id}/commissions"


def draft(client: TestClient, project_id: str, sale_id: str) -> dict:
    eligible = client.get(f"{root(project_id)}/eligible-sales").json()
    sold = next(row["sold_price"] for row in eligible if row["id"] == sale_id)
    response = client.post(
        root(project_id),
        json={
            "sale_contract_id": sale_id,
            "commissionable_base_amount": sold,
            "granted_rate_fraction": "0.100000",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def add(client: TestClient, project_id: str, grant_id: str, payload: dict) -> object:
    return client.post(
        f"{root(project_id)}/{grant_id}/allocations",
        json={"rate_fraction": "0.100000", **payload},
    )


def test_structured_agent_snapshot_and_reversal(
    db: Session,
    finance_client: TestClient,
    sales_ops_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    active_sale: str,
) -> None:
    sale = db.get(SaleContract, UUID(active_sale))
    sale.agent_name = "Original sale agent"
    sale.agent_branch = "Amman"
    db.commit()
    base = sales_url(project_id)
    first = sales_ops_client.post(
        f"{base}/agents", json={"display_name": "Same Name", "branch": "West"}
    )
    second = sales_ops_client.post(
        f"{base}/agents", json={"display_name": "Same Name", "branch": "East"}
    )
    assert first.status_code == second.status_code == 201
    grant = draft(finance_client, project_id, active_sale)
    assert grant["sale_agent_name"] == "Original sale agent"
    assert grant["sale_agent_branch"] == "Amman"
    response = add(
        finance_client,
        project_id,
        grant["id"],
        {"beneficiary_type": "agent", "sales_agent_id": second.json()["id"]},
    )
    assert response.status_code == 200, response.text
    allocation = response.json()["allocations"][0]
    assert allocation["sales_agent_id"] == second.json()["id"] != first.json()["id"]
    assert allocation["beneficiary_name"] == "Same Name"
    assert allocation["beneficiary_branch_snapshot"] == "East"
    assert response.json()["is_reconciled"] is True
    assert response.json()["sale_agent_name"] == "Original sale agent"
    assert (
        sales_ops_client.delete(
            f"{base}/agents/{second.json()['id']}", params={"reason": "Unused"}
        ).status_code
        == 409
    )
    changed = sales_ops_client.patch(
        f"{base}/agents/{second.json()['id']}",
        json={"display_name": "Renamed", "branch": "North", "is_active": False},
    )
    assert changed.status_code == 200, changed.text
    frozen = finance_client.get(f"{root(project_id)}/{grant['id']}").json()["allocations"][0]
    assert frozen["beneficiary_name"] == "Same Name"
    assert frozen["beneficiary_branch_snapshot"] == "East"
    assert (
        add(
            finance_client,
            project_id,
            grant["id"],
            {"beneficiary_type": "agent", "sales_agent_id": second.json()["id"]},
        ).status_code
        == 409
    )
    released = cfo_client.post(f"{root(project_id)}/{grant['id']}/release")
    assert released.status_code == 200, released.text
    assert released.json()["allocations"][0]["sales_agent_id"] == second.json()["id"]
    assert (
        add(finance_client, project_id, grant["id"], {"beneficiary_type": "other"}).status_code
        == 409
    )
    reversed_response = cfo_client.post(
        f"{root(project_id)}/{grant['id']}/reverse", json={"reason": "Correction"}
    )
    assert reversed_response.status_code == 200, reversed_response.text
    assert reversed_response.json()["allocations"][0] == released.json()["allocations"][0]


def test_branch_and_other_identity_are_server_authoritative(
    db: Session,
    finance_client: TestClient,
    sales_ops_client: TestClient,
    project_id: str,
    active_sale: str,
) -> None:
    sale_agent = sales_ops_client.post(
        f"{sales_url(project_id)}/agents",
        json={"display_name": "Sale Agent", "branch": "Amman"},
    )
    assert sale_agent.status_code == 201, sale_agent.text
    sale = db.get(SaleContract, UUID(active_sale))
    sale.agent_id = UUID(sale_agent.json()["id"])
    sale.agent_name = "Sale Agent"
    sale.agent_branch = "Amman"
    db.commit()
    assert (
        sales_ops_client.patch(
            f"{sales_url(project_id)}/agents/{sale_agent.json()['id']}",
            json={"branch": "Abdoun"},
        ).status_code
        == 200
    )
    grant = draft(finance_client, project_id, active_sale)
    branch = add(finance_client, project_id, grant["id"], {"beneficiary_type": "branch"})
    assert branch.status_code == 200, branch.text
    assert branch.json()["allocations"][0]["beneficiary_name"] == "Amman"
    assert branch.json()["allocations"][0]["sales_agent_id"] is None
    assert (
        add(
            finance_client,
            project_id,
            grant["id"],
            {"beneficiary_type": "branch", "beneficiary_name": "Dubai"},
        ).status_code
        == 422
    )
    unnamed = add(finance_client, project_id, grant["id"], {"beneficiary_type": "other"})
    assert unnamed.status_code == 200, unnamed.text
    assert unnamed.json()["allocations"][1]["beneficiary_name"] is None
    assert (
        add(
            finance_client,
            project_id,
            grant["id"],
            {"beneficiary_type": "other", "beneficiary_name": "Marketing"},
        ).status_code
        == 200
    )
    sale.agent_branch = None
    db.commit()
    assert (
        add(finance_client, project_id, grant["id"], {"beneficiary_type": "branch"}).status_code
        == 409
    )


def test_agent_spoofing_and_project_scope(
    finance_client: TestClient,
    sales_ops_client: TestClient,
    sales_ops: User,
    admin_client: TestClient,
    project_id: str,
    active_sale: str,
    country_pack_id: str,
    currency_id: str,
) -> None:
    grant = draft(finance_client, project_id, active_sale)
    agent = sales_ops_client.post(f"{sales_url(project_id)}/agents", json={"display_name": "Real"})
    assert agent.status_code == 201
    assert (
        add(
            finance_client,
            project_id,
            grant["id"],
            {
                "beneficiary_type": "agent",
                "sales_agent_id": agent.json()["id"],
                "beneficiary_name": "Spoofed",
            },
        ).status_code
        == 422
    )
    other_project = admin_client.post(
        PROJECTS,
        json=project_payload(country_pack_id, currency_id, code="COM-OTHER", name="Other"),
    )
    assert other_project.status_code == 201
    grant_access(admin_client, other_project.json()["id"], sales_ops)
    foreign_agent = sales_ops_client.post(
        f"{sales_url(other_project.json()['id'])}/agents",
        json={"display_name": "Foreign"},
    )
    assert foreign_agent.status_code == 201
    assert (
        add(
            finance_client,
            project_id,
            grant["id"],
            {"beneficiary_type": "agent", "sales_agent_id": foreign_agent.json()["id"]},
        ).status_code
        == 404
    )


def test_removed_draft_allocation_releases_agent_reference(
    finance_client: TestClient,
    sales_ops_client: TestClient,
    project_id: str,
    active_sale: str,
) -> None:
    agent = sales_ops_client.post(
        f"{sales_url(project_id)}/agents", json={"display_name": "Temporary recipient"}
    )
    assert agent.status_code == 201, agent.text
    grant = draft(finance_client, project_id, active_sale)
    created = add(
        finance_client,
        project_id,
        grant["id"],
        {"beneficiary_type": "agent", "sales_agent_id": agent.json()["id"]},
    )
    assert created.status_code == 200, created.text
    assert (
        sales_ops_client.delete(
            f"{sales_url(project_id)}/agents/{agent.json()['id']}",
            params={"reason": "Check reference"},
        ).status_code
        == 409
    )
    removed = finance_client.delete(
        f"{root(project_id)}/{grant['id']}/allocations/{created.json()['allocations'][0]['id']}"
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["allocations"] == []
    assert (
        sales_ops_client.delete(
            f"{sales_url(project_id)}/agents/{agent.json()['id']}",
            params={"reason": "No longer used"},
        ).status_code
        == 204
    )


def test_150k_golden_decimal_calculation() -> None:
    base, total = _terms(Decimal("150000"), Decimal("0.10"), Decimal("150000"))
    assert base == Decimal("150000.00")
    assert total == Decimal("15000.00")


def test_reconciliation_and_maker_checker(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    active_sale: str,
) -> None:
    eligible = finance_client.get(f"{root(project_id)}/eligible-sales").json()
    sold_price = eligible[0]["sold_price"]
    created = finance_client.post(
        root(project_id),
        json={
            "sale_contract_id": active_sale,
            "commissionable_base_amount": sold_price,
            "granted_rate_fraction": "0.100000",
        },
    )
    assert created.status_code == 201, created.text
    grant = created.json()
    assert grant["sold_price_snapshot"] == sold_price
    expected_total = str((Decimal(sold_price) * Decimal("0.1")).quantize(Decimal("0.01")))
    assert grant["commission_total"] == expected_total
    for beneficiary, rate in (
        ("Branch", "0.050000"),
        ("Sales Person", "0.030000"),
        ("Cyprus Branch", "0.010000"),
        ("Support Team", "0.010000"),
    ):
        added = finance_client.post(
            f"{root(project_id)}/{grant['id']}/allocations",
            json={
                "beneficiary_type": "other",
                "beneficiary_name": beneficiary,
                "rate_fraction": rate,
            },
        )
        assert added.status_code == 200, added.text
        grant = added.json()
    assert grant["allocation_rate_total"] == "0.100000"
    assert grant["allocation_amount_total"] == expected_total
    assert grant["is_reconciled"] is True
    assert finance_client.post(f"{root(project_id)}/{grant['id']}/release").status_code == 403
    released = cfo_client.post(f"{root(project_id)}/{grant['id']}/release")
    assert released.status_code == 200, released.text
    assert released.json()["status"] == "released"
    assert (
        finance_client.post(
            f"{root(project_id)}/{grant['id']}/allocations",
            json={
                "beneficiary_type": "other",
                "beneficiary_name": "Late",
                "rate_fraction": "0.010000",
            },
        ).status_code
        == 409
    )


def test_partial_base_and_invalid_terms(
    finance_client: TestClient, project_id: str, active_sale: str
) -> None:
    sold = Decimal(finance_client.get(f"{root(project_id)}/eligible-sales").json()[0]["sold_price"])
    base = (sold / 2).quantize(Decimal("0.01"))
    partial = finance_client.post(
        root(project_id),
        json={
            "sale_contract_id": active_sale,
            "commissionable_base_amount": str(base),
            "granted_rate_fraction": "0.1",
        },
    )
    assert partial.status_code == 201, partial.text
    assert partial.json()["commission_total"] == str(
        (base * Decimal("0.1")).quantize(Decimal("0.01"))
    )
