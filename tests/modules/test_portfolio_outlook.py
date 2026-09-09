"""Outlook goldens use PostgreSQL owner records and their public calculators."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.cashflow import service as cashflow
from app.modules.collections.models import CollectionReceipt
from app.modules.construction.models import ForecastVersion
from app.modules.inventory.models import Unit
from app.modules.payment_plans.models import PaymentPlanInstallment
from app.modules.project_analysis.calculations import forecast, shift_month
from app.modules.projects.models import Project
from app.modules.sales.models import Reservation, SaleContract
from tests.factories import make_user
from tests.modules.conftest import (
    cover_construction_forecast,
    create_cashflow_forecast,
    create_forecast,
    govern_cashflow_forecast,
    govern_forecast,
    grant_access,
    permit_payload,
    set_cashflow_line,
)
from tests.modules.test_portfolio_scale import copy_project


def rows(client: TestClient, kind: str, horizon: int = 90) -> dict:
    response = client.get(
        "/api/v1/portfolio/outlook",
        params={"item_type": kind, "horizon_days": horizon, "limit": 100},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_mixed_cash_refuses_whole_trajectory_and_eac_refuses_comparison(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    confirmed_receipt: str,
    flat_construction_forecast: str,
    cost_codes: dict[str, str],
    db: Session,
) -> None:
    created = create_cashflow_forecast(finance_client, project_id)
    assert created.status_code == 201, created.text
    fid = created.json()["id"]
    assert (
        govern_cashflow_forecast(
            finance_client, cfo_client, project_id, fid, cost_codes=cost_codes
        ).status_code
        == 200
    )
    safe = rows(admin_client, "cashflow_forecast")["items"][0]
    assert safe["availability"] == "available" and safe["amount"] is not None
    currency = admin_client.post(
        "/api/v1/settings/currencies", json={"code": "USD", "name": "US Dollar"}
    )
    assert currency.status_code == 201
    usd = uuid.UUID(currency.json()["id"])
    # Reproduce incompatible persisted source denominations without inventing FX.
    receipt = db.get(CollectionReceipt, uuid.UUID(confirmed_receipt))
    receipt.currency_id = usd
    db.commit()
    for horizon in (30, 60, 90):
        body = rows(admin_client, "cashflow_forecast", horizon)
        assert body["total"] == 1
        item = body["items"][0]
        assert item["availability"] == "unavailable"
        assert all(
            item[key] is None
            for key in ("amount", "peak_deficit", "lowpoint_month", "first_deficit_month")
        )
        assert "currencies" in item["reason"]
    forecast = db.get(ForecastVersion, uuid.UUID(flat_construction_forecast))
    forecast.currency_id = usd
    db.commit()
    item = rows(admin_client, "construction_eac")["items"][0]
    assert item["availability"] == "unavailable" and item["amount"] is None
    assert item["control_budget"] is None


def test_commercial_exact_runrate_and_nonpositive_remain_indeterminate(
    admin_client: TestClient, project_id: str, active_sale: str, db: Session
) -> None:
    today = datetime.now(UTC).date()
    project = db.get(Project, uuid.UUID(project_id))
    project.created_at = datetime.combine(shift_month(today, -4), datetime.min.time(), UTC)
    original_sale = db.get(SaleContract, uuid.UUID(active_sale))
    original_reservation = db.get(Reservation, original_sale.reservation_id)
    original_unit = db.get(Unit, original_sale.unit_id)
    sales = [original_sale]
    for index in range(1, 26):
        values = {
            column.name: getattr(original_unit, column.name)
            for column in Unit.__table__.columns
            if column.name != "id"
        }
        values.update(
            unit_number=f"RUN-{index}", unit_reference=f"RUN-{index}", commercial_status="available"
        )
        unit = Unit(**values)
        db.add(unit)
        db.flush()
        if index < 6:
            values = {
                column.name: getattr(original_reservation, column.name)
                for column in Reservation.__table__.columns
                if column.name != "id"
            }
            values.update(unit_id=unit.id, reservation_number=f"RUN-{index}")
            reservation = Reservation(**values)
            db.add(reservation)
            db.flush()
            values = {
                column.name: getattr(original_sale, column.name)
                for column in SaleContract.__table__.columns
                if column.name != "id"
            }
            values.update(
                unit_id=unit.id,
                reservation_id=reservation.id,
                sale_number=f"RUN-{index}",
                spa_number=f"RUN-{index}",
            )
            sale = SaleContract(**values)
            db.add(sale)
            sales.append(sale)
    for sale, month in zip(sales, (-3, -3, -2, -2, -2, -1), strict=True):
        sale.activated_at = datetime.combine(shift_month(today, month), datetime.min.time(), UTC)
    db.commit()
    for horizon in (30, 60, 90):
        result = rows(admin_client, "commercial_sellout", horizon)["items"][0]["commercial"]
        assert result == forecast(today, 20, [2, 3, 1], 3).model_dump(mode="json")
        assert Decimal(result["average_monthly_absorption"]) == 2
        assert Decimal(result["estimated_months_to_sell"]) == 10
    for sale in sales:
        sale.activated_at = datetime.combine(shift_month(today, -4), datetime.min.time(), UTC)
    sales[0].cancelled_at = datetime.combine(shift_month(today, -2), datetime.min.time(), UTC)
    db.commit()
    result = rows(admin_client, "commercial_sellout")["items"][0]["commercial"]
    assert result["monthly_net_absorption"] == [0, -1, 0]
    assert result["estimated_months_to_sell"] is None and result["availability"] == "unavailable"


def test_cash_forecast_lowpoint_staleness_and_action_independence(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    flat_construction_forecast: str,
    cost_codes: dict[str, str],
    db: Session,
) -> None:
    today = datetime.now(UTC).date()
    created = create_cashflow_forecast(finance_client, project_id)
    assert created.status_code == 201, created.text
    fid = created.json()["id"]
    line = set_cashflow_line(
        finance_client,
        project_id,
        fid,
        period_month=str(today.replace(day=1)),
        source_kind="development",
        category="consultants",
        amount="150000",
    )
    assert line.status_code == 200, line.text
    assert (
        govern_cashflow_forecast(
            finance_client, cfo_client, project_id, fid, cost_codes=cost_codes
        ).status_code
        == 200
    )
    project = db.get(Project, uuid.UUID(project_id))
    version = cashflow.active_forecast(db, project_id=project.id)
    bridge = cashflow.monthly_positions(db, project=project, version=version, as_of=today)
    for horizon in (30, 60, 90):
        item = rows(admin_client, "cashflow_forecast", horizon)["items"][0]
        assert Decimal(item["amount"]) == Decimal("-150000")
        assert item["lowpoint_month"] == str(today.replace(day=1))
        assert item["first_deficit_month"] == str(today.replace(day=1))
        assert Decimal(item["peak_deficit"]) == Decimal("150000")
        months = [
            row
            for row in bridge
            if today.replace(day=1)
            <= row.period_month
            <= (today + timedelta(days=horizon)).replace(day=1)
        ]
        assert Decimal(item["amount"]) == min(row.closing_unrestricted_cash for row in months)
    owner = make_user(db, email="cash-outlook-manager@example.com", roles=("project_manager",))
    grant_access(admin_client, project_id, owner)
    before = admin_client.get("/api/v1/portfolio/risks").json()
    risk = next(row for row in before["items"] if row["risk_code"] == "FORECAST_CASH_DEFICIT")
    action = admin_client.post(
        "/api/v1/portfolio/actions",
        json={
            "project_id": project_id,
            "title": "Review forecast funding",
            "owner_user_id": str(owner.id),
            "due_date": str(today),
            "source_type": "portfolio_risk",
            "source_code": risk["risk_code"],
            "source_key": risk["risk_id"],
            "source_observation_date": risk["observation_date"],
        },
    )
    assert action.status_code == 201, action.text
    assert (
        admin_client.post(
            f"/api/v1/portfolio/actions/{action.json()['id']}/transitions",
            json={"expected_version": 1, "status": "completed"},
        ).status_code
        == 200
    )
    assert admin_client.get("/api/v1/portfolio/risks").json() == before
    replacement = create_forecast(finance_client, project_id)
    assert replacement.status_code == 201, replacement.text
    replacement_id = replacement.json()["id"]
    cover_construction_forecast(finance_client, project_id, replacement_id, cost_codes, hard="0.00")
    assert (
        govern_forecast(finance_client, cfo_client, project_id, replacement_id).status_code == 200
    )
    item = rows(admin_client, "cashflow_forecast")["items"][0]
    assert item["availability"] == "unavailable" and item["amount"] is None
    assert "stale" in item["reason"].lower()


def test_scheduled_due_original_currency_and_no_cash_assumption(
    admin_client: TestClient,
    project_id: str,
    collecting_sale: str,
    db: Session,
) -> None:
    today = datetime.now(UTC).date()
    pid = uuid.UUID(project_id)
    second = copy_project(db, pid, "DUE-USD")
    currency = admin_client.post(
        "/api/v1/settings/currencies", json={"code": "USD", "name": "US Dollar"}
    )
    assert currency.status_code == 201
    usd = uuid.UUID(currency.json()["id"])
    db.scalar(select(SaleContract).where(SaleContract.project_id == second)).currency_id = usd
    for project, amount in ((pid, Decimal("30000")), (second, Decimal("10000"))):
        installments = db.scalars(
            select(PaymentPlanInstallment)
            .where(PaymentPlanInstallment.project_id == project)
            .order_by(PaymentPlanInstallment.sequence)
        ).all()
        for index, installment in enumerate(installments):
            installment.contractual_due_date = today + timedelta(days=20 if index == 0 else 120)
            installment.principal_amount = amount if index == 0 else Decimal("1")
            installment.tax_amount = Decimal(0)
            installment.fee_amount = Decimal(0)
    db.commit()
    before = admin_client.get("/api/v1/portfolio/overview").json()["money"]
    for horizon in (30, 60, 90):
        body = rows(admin_client, "scheduled_collection_due", horizon)
        assert {
            row["currency"]: Decimal(row["scheduled_outstanding_due"])
            for row in body["currency_buckets"]
        } == {"JOD": Decimal("30000"), "USD": Decimal("10000")}
        assert body["total"] == 2
        assert all("not expected or actual cash" in row["basis"].lower() for row in body["items"])
    assert admin_client.get("/api/v1/portfolio/overview").json()["money"] == before


def test_permit_resolution_preserves_open_action_and_design_active_only(
    admin_client: TestClient,
    manager_member_client: TestClient,
    project_id: str,
    db: Session,
) -> None:
    today = datetime.now(UTC).date()
    owner = make_user(db, email="permit-outlook-manager@example.com", roles=("project_manager",))
    grant_access(admin_client, project_id, owner)
    permit = admin_client.post(
        f"/api/v1/projects/{project_id}/permits",
        json=permit_payload(
            is_blocking=True, status_effective_date=str(today), statutory_sla_days=20
        ),
    )
    assert permit.status_code == 201, permit.text
    item = rows(admin_client, "permit_due", 30)["items"][0]
    assert item["due_date"] == str(today + timedelta(days=20)) and item["blocking"]
    linked_payload = {
        "project_id": project_id,
        "title": "Outlook deadline follow-up",
        "owner_user_id": str(owner.id),
        "due_date": str(today),
        "source_type": "portfolio_outlook",
        "source_code": item["item_type"],
        "source_key": item["source_key"],
        "source_observation_date": item["observation_date"],
    }
    linked = admin_client.post("/api/v1/portfolio/actions", json=linked_payload)
    assert linked.status_code == 201, linked.text
    assert (
        admin_client.post(
            "/api/v1/portfolio/actions", json={**linked_payload, "source_key": "forged"}
        ).status_code
        == 422
    )
    assert admin_client.post("/api/v1/portfolio/actions", json=linked_payload).status_code == 201
    risk = next(
        row
        for row in admin_client.get("/api/v1/portfolio/risks").json()["items"]
        if row["risk_code"] == "UNRESOLVED_BLOCKING_PERMIT"
    )
    action = admin_client.post(
        "/api/v1/portfolio/actions",
        json={
            "project_id": project_id,
            "title": "Complete authority follow-up",
            "owner_user_id": str(owner.id),
            "due_date": str(today),
            "source_type": "portfolio_risk",
            "source_key": risk["risk_id"],
            "source_code": risk["risk_code"],
            "source_observation_date": str(today),
        },
    )
    assert action.status_code == 201, action.text
    for state in ("preparing", "submitted", "accepted_for_review", "issued"):
        reply = admin_client.post(
            f"/api/v1/projects/{project_id}/permits/{permit.json()['id']}/transitions",
            json={"to_status": state, "effective_date": str(today), "reason": "Authority progress"},
        )
        assert reply.status_code == 201, reply.text
    assert rows(admin_client, "permit_due", 30)["total"] == 0
    assert (
        admin_client.get(f"/api/v1/portfolio/actions/{linked.json()['id']}").json()["status"]
        == "open"
    )
    url = f"/api/v1/portfolio/actions/{action.json()['id']}"
    assert admin_client.get(url).json()["status"] == "open"
    assert admin_client.get(f"{url}/source").json()["state"] == "resolved"
    base = f"/api/v1/projects/{project_id}/consultant-engineering"
    for index in (1, 2):
        agreement = manager_member_client.post(
            f"{base}/engagements",
            json={"consultant_name": f"Design {index}", "agreement_reference": f"D-{index}"},
        )
        assert agreement.status_code == 201
        eid = agreement.json()["id"]
        assert manager_member_client.post(f"{base}/engagements/{eid}/activate").status_code == 200
        stage = manager_member_client.post(
            f"{base}/engagements/{eid}/stages",
            json={
                "name": f"Stage {index}",
                "planned_date": str(today + timedelta(days=50)),
                "forecast_date": str(today + timedelta(days=20)),
            },
        )
        assert stage.status_code == 201, stage.text
        deliverable = manager_member_client.post(
            f"{base}/engagements/{eid}/deliverables",
            json={
                "name": f"Drawings {index}",
                "stage_id": stage.json()["id"],
                "due_date": str(today + timedelta(days=20)),
            },
        )
        assert deliverable.status_code == 201, deliverable.text
        if index == 1:
            assert (
                manager_member_client.post(f"{base}/engagements/{eid}/terminate").status_code == 200
            )
    assert [row["title"] for row in rows(admin_client, "consultant_stage_due", 30)["items"]] == [
        "Stage 2"
    ]
    assert [
        row["title"] for row in rows(admin_client, "consultant_deliverable_due", 30)["items"]
    ] == ["Drawings 2"]
