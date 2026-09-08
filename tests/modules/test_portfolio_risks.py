"""Management boundaries exercised through persisted owner state and HTTP reads."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.construction.models import ForecastLine
from app.modules.inventory.models import Unit
from app.modules.portfolio import service
from app.modules.project_analysis.calculations import shift_month
from app.modules.projects.models import Project
from app.modules.sales.models import SaleContract
from tests.modules.conftest import (
    confirm_receipt,
    permit_payload,
    record_receipt,
    refund_buyer,
)
from tests.modules.test_portfolio import metric
from tests.modules.test_portfolio_scale import copy_project


def test_receipts_refund_and_unconfirmed_golden(
    collecting_sale: str,
    project_id: str,
    finance_client: TestClient,
    collections_client: TestClient,
    sales_ops_client: TestClient,
    cfo_client: TestClient,
) -> None:
    receipt = record_receipt(collections_client, project_id, collecting_sale, "30000")
    assert receipt.status_code == 201, receipt.text
    assert confirm_receipt(finance_client, project_id, receipt.json()["id"]).status_code == 200
    assert (
        record_receipt(collections_client, project_id, collecting_sale, "10000").status_code == 201
    )
    refund_buyer(
        sales_ops_client,
        cfo_client,
        collections_client,
        finance_client,
        project_id,
        collecting_sale,
        amount="5000",
    )
    body = finance_client.get(f"/api/v1/portfolio/projects/{project_id}").json()
    assert Decimal(metric(body, "confirmed_receipts")["amount"]) == 30000
    assert Decimal(metric(body, "refunds")["amount"]) == 5000
    assert Decimal(metric(body, "unrestricted_cash")["amount"]) == 25000


def test_resolved_permit_stops_risk_and_pages_have_stable_order(
    admin_client: TestClient,
    project_id: str,
) -> None:
    base = f"/api/v1/projects/{project_id}/permits"
    old = (datetime.now(UTC).date() - timedelta(days=10)).isoformat()
    identifiers = []
    for index, blocking in enumerate((True, False)):
        response = admin_client.post(
            base,
            json=permit_payload(
                permit_code=f"PORT-{index}", is_blocking=blocking, statutory_sla_days=1
            ),
        )
        assert response.status_code == 201, response.text
        pid = response.json()["id"]
        identifiers.append(pid)
        transition = admin_client.post(
            f"{base}/{pid}/transitions", json={"to_status": "preparing", "effective_date": old}
        )
        assert transition.status_code == 201, transition.text
    url = "/api/v1/portfolio/risks"
    all_rows = admin_client.get(url).json()
    assert [row["risk_code"] for row in all_rows["items"]] == [
        "UNRESOLVED_BLOCKING_PERMIT",
        "OVERDUE_PERMIT",
    ]
    pages = [
        admin_client.get(url, params={"limit": 1, "offset": offset}).json() for offset in range(2)
    ]
    assert all(row["total"] == 2 for row in pages)
    assert [row["items"][0] for row in pages] == all_rows["items"]
    assert admin_client.get(url, params={"limit": 1, "offset": 2}).json()["items"] == []
    assert admin_client.get(url, params={"limit": 101}).status_code == 422
    for status in ("submitted", "accepted_for_review", "approved_with_conditions", "issued"):
        result = admin_client.post(
            f"{base}/{identifiers[0]}/transitions",
            json={"to_status": status, "effective_date": old},
        )
        assert result.status_code == 201, result.text
    assert [row["risk_code"] for row in admin_client.get(url).json()["items"]] == ["OVERDUE_PERMIT"]


def test_partial_eac_bucket_and_strict_overrun_boundary(
    active_construction_forecast: str,
    project_id: str,
    admin_client: TestClient,
    db: Session,
) -> None:
    source = uuid.UUID(project_id)
    second = copy_project(db, source, "EAC-B")
    # Remove only the governing status in synthetic setup, not a production workflow.
    from app.modules.construction.models import ForecastVersion

    version = db.scalar(select(ForecastVersion).where(ForecastVersion.project_id == second))
    version.status = "superseded"
    db.commit()
    body = admin_client.get("/api/v1/portfolio/overview").json()
    total = metric(body, "construction_eac", "JOD")
    assert total["availability"] == "partial"
    assert total["contributing_project_count"] == total["missing_project_count"] == 1
    detail_url = f"/api/v1/portfolio/projects/{project_id}"
    detail = admin_client.get(detail_url).json()
    budget = Decimal(metric(detail, "construction_control_budget")["amount"])
    eac = Decimal(metric(detail, "construction_eac")["amount"])
    line = db.scalars(
        select(ForecastLine).where(
            ForecastLine.forecast_version_id == uuid.UUID(active_construction_forecast)
        )
    ).first()
    line.forecast_remaining_amount_ex_tax += budget - eac
    db.commit()
    at_budget = admin_client.get(detail_url).json()
    assert "CONSTRUCTION_COST_EXCEEDANCE" not in {row["risk_code"] for row in at_budget["risks"]}
    line.forecast_remaining_amount_ex_tax += Decimal("0.01")
    db.commit()
    above = admin_client.get(detail_url).json()
    assert "CONSTRUCTION_COST_EXCEEDANCE" in {row["risk_code"] for row in above["risks"]}


def test_commercial_stall_requires_complete_months_and_nonpositive_net(
    active_sale: str,
    project_id: str,
    db: Session,
) -> None:
    today = datetime.now(UTC).date()
    project = db.get(Project, uuid.UUID(project_id))
    sale = db.get(SaleContract, uuid.UUID(active_sale))
    original = db.get(Unit, sale.unit_id)
    values = {
        col.name: getattr(original, col.name) for col in Unit.__table__.columns if col.name != "id"
    }
    values.update(unit_number="REMAIN", unit_reference="REMAIN", commercial_status="available")
    db.add(Unit(**values))
    scope = select(Project.id).where(Project.id == project.id)

    def codes() -> set[str]:
        db.commit()
        return {risk.risk_code for risk in service.summaries(db, scope, today)[0].risks}

    project.created_at = datetime.combine(shift_month(today, -3), datetime.min.time(), UTC)
    sale.activated_at = datetime.combine(shift_month(today, -1), datetime.min.time(), UTC)
    assert "COMMERCIAL_STALL" not in codes()  # positive absorption has no invented target
    sale.activated_at = datetime.combine(shift_month(today, -4), datetime.min.time(), UTC)
    assert "COMMERCIAL_STALL" in codes()
    project.created_at += timedelta(days=1)
    assert "COMMERCIAL_STALL" not in codes()  # one incomplete month is not three complete months
