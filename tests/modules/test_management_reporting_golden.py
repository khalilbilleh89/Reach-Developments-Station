"""The complete management meeting story through legitimate owner workflows."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.access.models import User
from tests.modules.conftest import (
    confirm_receipt,
    cover_construction_forecast,
    create_cashflow_forecast,
    create_forecast,
    govern_cashflow_forecast,
    govern_forecast,
    permit_payload,
    record_receipt,
    set_cashflow_line,
)
from tests.modules.test_management_reporting import ROOT, capture


def test_full_project_before_after_meeting_story(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    collections_client: TestClient,
    manager_member_client: TestClient,
    project_id: str,
    collecting_sale: str,
    confirmed_receipt: str,
    flat_construction_forecast: str,
    cost_codes: dict[str, str],
    land_cost: str,
    db: Session,
    request: pytest.FixtureRequest,
) -> None:
    today = datetime.now(UTC).date()
    owner = db.scalar(select(User).where(User.email == "admin@example.com"))
    fid = create_cashflow_forecast(finance_client, project_id).json()["id"]
    assert (
        set_cashflow_line(
            finance_client,
            project_id,
            fid,
            period_month=str(today.replace(day=1)),
            source_kind="development",
            category="consultants",
            amount="600000",
        ).status_code
        == 200
    )
    response = govern_cashflow_forecast(
        finance_client, cfo_client, project_id, fid, cost_codes=cost_codes
    )
    assert response.status_code == 200, response.text
    permit = admin_client.post(
        f"/api/v1/projects/{project_id}/permits",
        json=permit_payload(
            is_blocking=True, status_effective_date=str(today), statutory_sla_days=20
        ),
    ).json()
    base = f"/api/v1/projects/{project_id}/consultant-engineering"
    engagement = manager_member_client.post(
        base + "/engagements",
        json={"consultant_name": "Board design consultant", "agreement_reference": "BOARD-01"},
    ).json()
    assert (
        manager_member_client.post(f"{base}/engagements/{engagement['id']}/activate").status_code
        == 200
    )
    assert (
        manager_member_client.post(
            f"{base}/engagements/{engagement['id']}/stages",
            json={
                "name": "Authority drawings",
                "planned_date": str(today + timedelta(days=30)),
                "forecast_date": str(today + timedelta(days=20)),
            },
        ).status_code
        == 201
    )

    def action(title: str) -> dict[str, Any]:
        r = admin_client.post(
            "/api/v1/portfolio/actions",
            json={
                "project_id": project_id,
                "title": title,
                "owner_user_id": str(owner.id),
                "due_date": str(today - timedelta(days=1)),
            },
        )
        assert r.status_code == 201, r.text
        return r.json()

    def transition(a: dict[str, Any], status: str) -> dict[str, Any]:
        r = admin_client.post(
            f"/api/v1/portfolio/actions/{a['id']}/transitions",
            json={
                "expected_version": a["version"],
                "status": status,
                "reason": "Management meeting decision",
            },
        )
        assert r.status_code == 200, r.text
        return r.json()

    funding = action("Secure funding response")
    permit_action = action("Coordinate permit follow-up")
    a = capture(admin_client, project_id)
    first_board = admin_client.get(f"{ROOT}/snapshots/{a['id']}/board-pack").json()
    # New unit, measured/priced/released, reservation, signatures, active sale,
    # reconciled plan and independent CFO approval through existing fixture routes.
    second = request.getfixturevalue("other_phase_plan")
    forecast_date = collections_client.patch(
        f"/api/v1/projects/{project_id}/payment-plans/{second['plan_id']}"
        f"/installments/{second['manual_installment_id']}/forecast",
        json={
            "forecast_due_date": str(today + timedelta(days=15)),
            "reason": "Lender drawdown expected within the governed cashflow horizon",
        },
    )
    assert forecast_date.status_code == 200, forecast_date.text
    receipt = record_receipt(collections_client, project_id, collecting_sale, "20000", str(today))
    assert receipt.status_code == 201, receipt.text
    assert confirm_receipt(finance_client, project_id, receipt.json()["id"]).status_code == 200
    next_cost = create_forecast(finance_client, project_id).json()["id"]
    cover_construction_forecast(finance_client, project_id, next_cost, cost_codes, hard="12000000")
    assert govern_forecast(finance_client, cfo_client, project_id, next_cost).status_code == 200
    next_cash = create_cashflow_forecast(
        finance_client, project_id, change_reason="Updated cost and capital review"
    ).json()["id"]
    assert (
        set_cashflow_line(
            finance_client,
            project_id,
            next_cash,
            period_month=str(today.replace(day=1)),
            source_kind="construction",
            category="construction",
            amount="12000000",
            construction_cost_code_id=cost_codes["hard"],
        ).status_code
        == 200
    )
    assert (
        govern_cashflow_forecast(
            finance_client, cfo_client, project_id, next_cash, cost_codes=cost_codes
        ).status_code
        == 200
    )
    for state in ("preparing", "submitted", "accepted_for_review", "issued"):
        r = admin_client.post(
            f"/api/v1/projects/{project_id}/permits/{permit['id']}/transitions",
            json={"to_status": state, "effective_date": str(today), "reason": "Authority progress"},
        )
        assert r.status_code == 201, r.text
    funding = transition(funding, "completed")
    followup = action("Review lender confirmation")
    action("Confirm next board date")
    followup = transition(followup, "in_progress")
    followup = transition(followup, "completed")
    transition(followup, "open")
    b = capture(admin_client, project_id)
    result = admin_client.get(
        f"{ROOT}/comparisons?from_snapshot_id={a['id']}&to_snapshot_id={b['id']}"
    )
    assert result.status_code == 200, result.text
    c = result.json()

    def delta(code: str) -> Decimal:
        return Decimal(
            next(
                m["delta"]
                for m in c["movements"]
                if m["metric"] == code and m["project_id"] == project_id
            )
        )

    assert delta("active_sold_units") == 1
    assert delta("confirmed_receipts") == 20000
    assert delta("construction_eac") == 12000000
    assert c["execution"]["created"] == 2 and c["execution"]["started"] == 1
    assert c["execution"]["completed"] == 2 and c["execution"]["reopened"] == 1
    risks = {(r["current"] or r["prior"])["risk_code"]: r["classification"] for r in c["risks"]}
    assert risks["FORECAST_CASH_DEFICIT"] == "continuing"
    assert risks["CONSTRUCTION_COST_EXCEEDANCE"] == "new"
    assert risks["UNRESOLVED_BLOCKING_PERMIT"] == "resolved"
    assert all(x["id"] != funding["id"] for x in b["payload"]["actions"])
    assert b["payload"]["action_counts"]["completed"] == 1
    assert next(x for x in b["payload"]["action_frontier"] if x["id"] == funding["id"])
    assert (
        next(x for x in b["payload"]["actions"] if x["id"] == permit_action["id"])["status"]
        == "open"
    )
    assert any(f["fact"].endswith("/ status") and f["current"] == "issued" for f in c["facts"])
    assert any(f["prior"] == fid and f["current"] == next_cash for f in c["facts"])
    # A second live mutation after both retained captures must change neither
    # the earlier Board Pack nor the already computed historical interval.
    later_receipt = record_receipt(
        collections_client, project_id, collecting_sale, "1000", str(today)
    )
    assert later_receipt.status_code == 201, later_receipt.text
    assert (
        confirm_receipt(finance_client, project_id, later_receipt.json()["id"]).status_code == 200
    )
    transition(funding, "open")
    assert admin_client.get(f"{ROOT}/snapshots/{a['id']}/board-pack").json() == first_board
    assert (
        admin_client.get(
            f"{ROOT}/comparisons?from_snapshot_id={a['id']}&to_snapshot_id={b['id']}"
        ).json()
        == c
    )
