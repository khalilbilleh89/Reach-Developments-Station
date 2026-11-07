"""Management report reconciliation, threshold boundaries and disclosure scope."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.project_analysis.report import chart
from app.modules.sales.models import SaleContract
from app.modules.settings.models import Currency
from tests.factories import client_for, make_user
from tests.modules.conftest import grant_access
from tests.modules.test_commissions_review import snapshot


def url(project_id: str) -> str:
    return f"/api/v1/projects/{project_id}/analysis/report"


def points(body: dict, key: str) -> dict[str, Decimal | None]:
    item = next(item for item in body["charts"] if item["key"] == key)
    return {
        row["label"]: Decimal(row["value"]) if row["value"] is not None else None
        for row in item["points"]
    }


def test_report_empty_missing_costs_and_no_writes(
    manager_member_client: TestClient,
    project_id: str,
    db: Session,
) -> None:
    before = snapshot(db)
    response = manager_member_client.get(url(project_id))
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data["charts"]) == 20
    assert len({row["key"] for row in data["charts"]}) == 20
    assert all(row["source"] and row["insight"] for row in data["charts"])
    assert all(value is None for value in points(data, "construction-cost").values())
    assert points(data, "threshold") == {
        "Above threshold": 0,
        "At threshold": 0,
        "Below threshold": 0,
    }
    assert snapshot(db) == before


def test_report_threshold_ex_tax_agent_attribution_and_cancellation(
    finance_client: TestClient,
    active_sale: str,
    project_id: str,
    db: Session,
) -> None:
    sale = db.get(SaleContract, uuid.UUID(active_sale))
    code = db.get(Currency, sale.currency_id).code
    sale.agent_name = "Recorded agent"
    sale.agent_branch = "Recorded branch"
    sale.activated_at = datetime.now(UTC)
    db.commit()
    for delta, bucket in (
        (Decimal(-1), "Above threshold"),
        (Decimal(0), "At threshold"),
        (Decimal(1), "Below threshold"),
    ):
        response = finance_client.get(
            url(project_id),
            params={
                "threshold": str(sale.net_contract_price_ex_tax + delta),
                "currency": code,
            },
        )
        assert response.status_code == 200, response.text
        data = response.json()
        counts = points(data, "threshold")
        assert counts[bucket] == 1 and sum(counts.values()) == 1
        assert points(data, "agents") == {"Recorded agent": 1}
        assert points(data, "branches") == {"Recorded branch": 1}
        assert points(data, "buyers")["One purchased unit"] == 1
    sale.cancelled_at = datetime.now(UTC)
    db.commit()
    data = finance_client.get(url(project_id)).json()
    assert sum(points(data, "threshold").values()) == 0
    assert points(data, "agents") == {}
    assert sum(points(data, "net-sales").values()) == 0


@pytest.mark.parametrize(
    "params",
    [
        {"threshold": "-1"},
        {"threshold": "NaN"},
        {"threshold": "Infinity"},
        {"threshold": "1.001"},
        {"currency": "ZZZ"},
        {"period_from": "2026-10-01", "period_to": "2026-01-01"},
        {"period_to": "2099-01-01"},
    ],
)
def test_report_invalid_filters(
    manager_member_client: TestClient, project_id: str, params: dict
) -> None:
    assert manager_member_client.get(url(project_id), params=params).status_code == 422


def test_report_roles_project_and_phase_scope(
    admin_client: TestClient,
    project_id: str,
    phase_id: str,
    db: Session,
) -> None:
    for role in ("sales_advisor", "sales_operations", "legal", "collections", "design_engineering"):
        user = make_user(db, email=f"report-{role}@example.com", roles=(role,))
        grant_access(admin_client, project_id, user)
        client = client_for(user.email)
        assert client.get(url(project_id)).status_code == 403
        assert client.get(url(str(uuid.uuid4()))).status_code == 404
    user = make_user(db, email="report-phase@example.com", roles=("project_manager",))
    grant_access(admin_client, project_id, user)
    assert (
        admin_client.patch(
            f"/api/v1/projects/{project_id}/access/{user.id}/phase-scope",
            json={"phase_scope": "selected"},
        ).status_code
        == 200
    )
    admin_client.put(f"/api/v1/projects/{project_id}/access/{user.id}/phases/{phase_id}")
    assert client_for(user.email).get(url(project_id)).status_code == 403


def test_chart_geometry_missing_negative_and_rollup() -> None:
    data = chart("cash", "Cash", "Cash", [("in", 20), ("out", -10), ("missing", None)], "Test")
    assert data.points[1].value == -10
    assert data.points[1].scale_percentage == 50
    assert data.points[2].value is None
    assert all(point.share_percentage is None for point in data.points)
    data = chart("agents", "Agents", "People", [(str(i), i) for i in range(20)], "Test")
    assert len(data.points) == 10
    assert sum(point.value for point in data.points) == sum(range(20))


def test_report_currency_exclusion_and_confirmed_cash(
    admin_client: TestClient,
    collections_client: TestClient,
    finance_client: TestClient,
    collecting_sale: str,
    project_id: str,
    db: Session,
) -> None:
    from tests.modules.conftest import confirm_receipt, record_receipt

    sale = db.get(SaleContract, uuid.UUID(collecting_sale))
    code = db.get(Currency, sale.currency_id).code
    other = admin_client.post("/api/v1/settings/currencies", json={"code": "XYZ", "name": "Test"})
    assert other.status_code == 201, other.text
    result = finance_client.get(url(project_id), params={"currency": "XYZ"})
    assert result.status_code == 200, result.text
    data = result.json()
    assert sum(points(data, "threshold").values()) == 0
    assert sum(points(data, "cash-in").values()) == 0
    receipt = record_receipt(collections_client, project_id, collecting_sale, "400.01")
    assert receipt.status_code == 201, receipt.text
    data = finance_client.get(url(project_id), params={"currency": code}).json()
    assert sum(points(data, "cash-in").values()) == 0
    assert confirm_receipt(finance_client, project_id, receipt.json()["id"]).status_code == 200
    data = finance_client.get(url(project_id), params={"currency": code}).json()
    assert sum(points(data, "cash-in").values()) == Decimal("400.01")
    assert points(data, "collections-position")["Confirmed receipts"] == Decimal("400.01")
    assert points(data, "cash-bridge")["Customer receipts"] == Decimal("400.01")
    assert (
        next(row for row in data["metrics"] if row["label"] == "Period collections")["value"]
        == "400.01"
    )
