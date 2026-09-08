"""Owner workflows remain independent of read-only Portfolio management."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.cashflow import batch, calculator
from app.modules.cashflow import service as cashflow
from app.modules.projects.models import Project
from tests.modules.conftest import (
    create_cashflow_forecast,
    govern_cashflow_forecast,
    set_cashflow_line,
)
from tests.modules.test_portfolio import metric
from tests.modules.test_prelaunch import payload as expense_payload


def test_prelaunch_commission_and_consultant_independence(
    finance_client: TestClient,
    cfo_client: TestClient,
    manager_member_client: TestClient,
    project_id: str,
    currency_id: str,
    active_sale: str,
) -> None:
    url = f"/api/v1/portfolio/projects/{project_id}"
    before = finance_client.get(url).json()
    financial_codes = {
        "unrestricted_cash",
        "restricted_cash",
        "total_cash",
        "contracted_value",
        "construction_paid",
        "construction_commitment",
    }

    def financial(body: dict) -> dict:
        return {
            (row["metric_code"], row["currency"]): row["amount"]
            for row in body["money"]
            if row["metric_code"] in financial_codes
        }

    commission_url = f"/api/v1/projects/{project_id}/commissions"
    grant = finance_client.post(
        commission_url,
        json={
            "sale_contract_id": active_sale,
            "commissionable_base_amount": "100000",
            "granted_rate_fraction": "0.10",
        },
    )
    assert grant.status_code == 201, grant.text
    gid = grant.json()["id"]
    assert (
        finance_client.post(
            f"{commission_url}/{gid}/allocations",
            json={"beneficiary_name": "Agent", "rate_fraction": "0.10"},
        ).status_code
        == 200
    )
    assert cfo_client.post(f"{commission_url}/{gid}/release").status_code == 200
    after = finance_client.get(url).json()
    assert financial(before) == financial(after)
    assert Decimal(metric(after, "commission_released")["amount"]) == Decimal("10000")
    base = f"/api/v1/projects/{project_id}/consultant-engineering"
    agreement = manager_member_client.post(
        f"{base}/engagements",
        json={"consultant_name": "Portfolio design", "agreement_reference": "P-01"},
    )
    assert agreement.status_code == 201, agreement.text
    eid = agreement.json()["id"]
    assert manager_member_client.post(f"{base}/engagements/{eid}/activate").status_code == 200
    after = finance_client.get(url).json()
    assert financial(before) == financial(after)
    assert after["design"]["consultant_name"] == "Portfolio design"
    yesterday = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()
    stage = manager_member_client.post(
        f"{base}/engagements/{eid}/stages",
        json={"name": "Detailed design", "planned_date": yesterday},
    )
    assert stage.status_code == 201, stage.text
    item = manager_member_client.post(
        f"{base}/engagements/{eid}/deliverables",
        json={"name": "Drawings", "stage_id": stage.json()["id"], "due_date": yesterday},
    )
    assert item.status_code == 201, item.text
    after = finance_client.get(url).json()
    codes = {row["risk_code"] for row in after["risks"]}
    assert {"CONSULTANT_STAGE_OVERDUE", "CONSULTANT_DELIVERABLE_OVERDUE"} <= codes
    assert financial(before) == financial(after)
    expense_url = f"/api/v1/projects/{project_id}/pre-launch/expenses"
    created = finance_client.post(expense_url, json=expense_payload(currency_id))
    assert created.status_code == 201, created.text
    assert (
        cfo_client.post(f"{expense_url}/{created.json()['id']}/confirm", json={}).status_code == 200
    )
    after = finance_client.get(url).json()
    assert Decimal(metric(after, "unrestricted_cash")["amount"]) == Decimal(
        metric(before, "unrestricted_cash")["amount"]
    ) - Decimal("1250.25")
    assert "ACTUAL_CASH_DEFICIT" in {row["risk_code"] for row in after["risks"]}


def test_governed_forecast_and_opening_anchor_exact_parity(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    flat_construction_forecast: str,
    cost_codes: dict[str, str],
    confirmed_receipt: str,
    db: Session,
) -> None:
    created = create_cashflow_forecast(
        finance_client, project_id, opening_unrestricted_cash="5000", opening_restricted_cash="1000"
    )
    assert created.status_code == 201, created.text
    fid = created.json()["id"]
    month = datetime.now(UTC).date().replace(day=1).isoformat()
    line = set_cashflow_line(
        finance_client,
        project_id,
        fid,
        period_month=month,
        source_kind="development",
        category="consultants",
        amount="20000",
    )
    assert line.status_code == 200, line.text
    governed = govern_cashflow_forecast(
        finance_client, cfo_client, project_id, fid, cost_codes=cost_codes
    )
    assert governed.status_code == 200, governed.text
    today = datetime.now(UTC).date()
    project = db.get(Project, uuid.UUID(project_id))
    version = cashflow.active_forecast(db, project_id=project.id)
    expected_rows = cashflow.collect_source_rows(db, project=project, version=version, as_of=today)
    expected_cash = cashflow.actual_cash_position(expected_rows, version=version, as_of=today)
    expected_months = cashflow.monthly_positions(db, project=project, version=version, as_of=today)
    expected_peak = calculator.peak_deficit(
        [(row.period_month, row.closing_unrestricted_cash) for row in expected_months]
    )
    actual = batch.positions(db, select(Project.id).where(Project.id == project.id), today)[
        project.id
    ]
    assert actual.reason is None and actual.forecast_reason is None
    assert actual.total_cash == expected_cash.total_cash
    assert actual.restricted_cash == expected_cash.restricted_cash
    assert actual.unrestricted_cash == expected_cash.unrestricted_cash
    assert actual.peak_deficit == expected_peak.peak_funding_deficit
    body = finance_client.get(f"/api/v1/portfolio/projects/{project_id}").json()
    assert any(row["risk_code"] == "FORECAST_CASH_DEFICIT" for row in body["risks"])
