"""Portfolio security, original currency and source parity against PostgreSQL."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.cashflow import batch as cash_batch
from app.modules.cashflow import service as cashflow
from app.modules.collections.models import CollectionReceipt
from app.modules.portfolio import service
from app.modules.projects.models import Project
from tests.factories import client_for, make_user
from tests.modules.conftest import (
    confirm_receipt,
    grant_access,
    permit_payload,
    project_payload,
    record_receipt,
)
from tests.modules.test_commissions_review import snapshot


def metric(body: dict, code: str, currency: str | None = None) -> dict:
    return next(
        row
        for row in body["money"]
        if row["metric_code"] == code and (currency is None or row["currency"] == currency)
    )


def test_roles_and_phase_scope_exclude_before_sources(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    readers = {
        "system_admin",
        "project_manager",
        "finance",
        "approver_cfo",
        "executive_viewer",
        "auditor",
    }
    for role in sorted(
        readers
        | {"sales_operations", "sales_advisor", "legal", "collections", "design_engineering"}
    ):
        user = make_user(db, email=f"portfolio-{role}@example.com", roles=(role,))
        client = client_for(user.email)
        response = client.get("/api/v1/portfolio/overview")
        assert response.status_code == (200 if role in readers else 403), response.text
        if role not in readers:
            client.close()
            continue
        assert response.json()["project_count"] == (1 if role == "system_admin" else 0)
        grant_access(admin_client, project_id, user)
        assert client.get("/api/v1/portfolio/overview").json()["project_count"] == 1
        assert (
            admin_client.patch(
                f"/api/v1/projects/{project_id}/access/{user.id}/phase-scope",
                json={"phase_scope": "selected"},
            ).status_code
            == 200
        )
        body = client.get("/api/v1/portfolio/overview").json()
        assert body["project_count"] == (1 if role == "system_admin" else 0)
        response = client.get(f"/api/v1/portfolio/projects/{project_id}")
        assert response.status_code == (200 if role == "system_admin" else 404)
        if role != "system_admin":
            assert project_id not in response.text
        client.close()


def test_foreign_and_mixed_cash_refuse_without_losing_collections(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    confirmed_receipt: str,
    db: Session,
) -> None:
    currency = admin_client.post(
        "/api/v1/settings/currencies", json={"code": "USD", "name": "US dollar"}
    )
    assert currency.status_code == 201, currency.text
    usd = uuid.UUID(currency.json()["id"])
    project = db.get(Project, uuid.UUID(project_id))
    receipt = db.get(CollectionReceipt, uuid.UUID(confirmed_receipt))
    # Reproduce a pre-existing denomination conflict in persisted source data.
    project.base_currency_id = usd
    db.commit()
    url = f"/api/v1/portfolio/projects/{project_id}"
    body = finance_client.get(url).json()
    assert metric(body, "confirmed_receipts", "JOD")["amount"] == "10000.00"
    assert body["cashflow_reason_code"] == "cashflow_currency_mismatch"
    assert metric(body, "unrestricted_cash")["amount"] is None
    assert not any(r["category"] == "cashflow" for r in body["risks"])
    values = {
        col.name: getattr(receipt, col.name)
        for col in receipt.__table__.columns
        if col.name != "id"
    }
    values.update(receipt_number="PORTFOLIO-USD", amount=Decimal("20000"), currency_id=usd)
    second = CollectionReceipt(**values)
    db.add(second)
    db.commit()
    body = finance_client.get(url).json()
    assert metric(body, "confirmed_receipts", "USD")["amount"] == "20000.00"
    assert metric(body, "confirmed_receipts", "JOD")["amount"] == "10000.00"
    assert metric(body, "unrestricted_cash")["amount"] is None
    # Once both source denominations match, full owner parity resumes.
    receipt.currency_id = usd
    db.commit()
    body = finance_client.get(url).json()
    expected = cashflow.actual_cash_position(
        cashflow.collect_source_rows(
            db, project=project, version=None, as_of=datetime.now(UTC).date()
        ),
        version=None,
        as_of=datetime.now(UTC).date(),
    )
    assert (
        Decimal(metric(body, "unrestricted_cash")["amount"])
        == expected.unrestricted_cash
        == Decimal("30000")
    )
    assert body["cashflow_reason_code"] is None


def test_unauthorized_large_sources_and_phase_project_do_not_contribute(
    admin_client: TestClient,
    project_id: str,
    confirmed_receipt: str,
    active_construction_forecast: str,
    country_pack_id: str,
    currency_id: str,
    db: Session,
) -> None:
    from app.modules.construction.models import ForecastLine

    lines = list(
        db.scalars(
            select(ForecastLine).where(
                ForecastLine.forecast_version_id == uuid.UUID(active_construction_forecast)
            )
        )
    )
    lines[0].forecast_remaining_amount_ex_tax = Decimal("999999999")
    receipt = db.get(CollectionReceipt, uuid.UUID(confirmed_receipt))
    receipt.amount = Decimal("99999999")
    db.commit()
    blocker = admin_client.post(
        f"/api/v1/projects/{project_id}/permits", json=permit_payload(is_blocking=True)
    )
    assert blocker.status_code == 201, blocker.text
    allowed = admin_client.post(
        "/api/v1/projects",
        json=project_payload(country_pack_id, currency_id, code="ONLY-A", name="Authorized A"),
    )
    assert allowed.status_code == 201, allowed.text
    aid = allowed.json()["id"]
    user = make_user(db, email="portfolio-a-only@example.com", roles=("finance",))
    grant_access(admin_client, aid, user)
    client = client_for(user.email)
    baseline = client.get("/api/v1/portfolio/overview").json()
    assert baseline["project_count"] == 1
    assert metric(baseline, "confirmed_receipts")["amount"] == "0"
    assert baseline["risk_count"] == 0
    for path in ("overview", "projects", "risks"):
        response = client.get(f"/api/v1/portfolio/{path}")
        assert response.status_code == 200
        assert project_id not in response.text and "99999999" not in response.text
    assert client.get(f"/api/v1/portfolio/projects/{project_id}").status_code == 404
    grant_access(admin_client, project_id, user)
    assert (
        admin_client.patch(
            f"/api/v1/projects/{project_id}/access/{user.id}/phase-scope",
            json={"phase_scope": "selected"},
        ).status_code
        == 200
    )
    assert client.get("/api/v1/portfolio/overview").json() == baseline
    assert client.get("/api/v1/portfolio/projects").json()["total"] == 1
    assert client.get("/api/v1/portfolio/risks").json()["total"] == 0
    client.close()


def test_populated_owner_parity_and_allocation_dedup(
    finance_client: TestClient,
    collections_client: TestClient,
    project_id: str,
    collecting_sale: str,
    active_construction_forecast: str,
    db: Session,
) -> None:
    from app.modules.construction import service as construction
    from tests.modules.conftest import allocate, collection_account, governing_installments

    receipt = record_receipt(collections_client, project_id, collecting_sale, "30000")
    assert receipt.status_code == 201, receipt.text
    rid = receipt.json()["id"]
    assert confirm_receipt(finance_client, project_id, rid).status_code == 200
    installments = governing_installments(collections_client, project_id, collecting_sale)
    assert (
        allocate(
            collections_client, project_id, rid, installments[0]["installment_id"], "20000"
        ).status_code
        == 201
    )
    assert (
        allocate(
            collections_client, project_id, rid, installments[1]["installment_id"], "10000"
        ).status_code
        == 201
    )
    assert (
        record_receipt(collections_client, project_id, collecting_sale, "10000").status_code == 201
    )
    body = finance_client.get(f"/api/v1/portfolio/projects/{project_id}").json()
    assert Decimal(metric(body, "confirmed_receipts")["amount"]) == Decimal("30000")
    assert Decimal(metric(body, "unapplied_cash")["amount"]) == 0
    expected = collection_account(finance_client, project_id, collecting_sale)
    assert Decimal(metric(body, "overdue_outstanding")["amount"]) == Decimal(
        expected["overdue_total"]
    )
    cost = construction.cost_control_position(db, project=db.get(Project, uuid.UUID(project_id)))
    assert Decimal(metric(body, "construction_eac")["amount"]) == cost.estimate_at_completion
    assert Decimal(metric(body, "construction_control_budget")["amount"]) == cost.control_budget
    assert body["committed_units"] == body["active_sold_units"] == 1
    before = snapshot(db)
    assert finance_client.get(f"/api/v1/portfolio/projects/{project_id}").status_code == 200
    assert snapshot(db) == before


def test_empty_sources_are_unavailable_and_reads_do_not_write(
    manager_member_client: TestClient, project_id: str, db: Session
) -> None:
    before = snapshot(db)
    for path in ("overview", "projects", "risks", f"projects/{project_id}"):
        response = manager_member_client.get(f"/api/v1/portfolio/{path}")
        assert response.status_code == 200, response.text
    assert snapshot(db) == before
    row = manager_member_client.get(f"/api/v1/portfolio/projects/{project_id}").json()
    assert row["sales_penetration"]["percentage"] is None
    assert row["coverage"] == "partial"
    assert next(m for m in row["money"] if m["metric_code"] == "construction_eac")["amount"] is None
    assert (
        next(e for e in row["risk_evaluations"] if e["risk_code"] == "FORECAST_CASH_DEFICIT")[
            "availability"
        ]
        == "unavailable"
    )


def test_safe_cashflow_owner_parity(project_id: str, db: Session) -> None:
    today = datetime.now(UTC).date()
    pid = uuid.UUID(project_id)
    project = db.get(Project, pid)
    scope = select(Project.id).where(Project.id == pid)
    batch = cash_batch.positions(db, scope, today)[pid]
    sources = cashflow.collect_source_rows(db, project=project, version=None, as_of=today)
    expected = cashflow.actual_cash_position(sources, version=None, as_of=today)
    assert batch.unrestricted_cash == expected.unrestricted_cash == Decimal(0)
    assert batch.reason is None
    assert len(service.summaries(db, scope, today)) == 1
