"""Explicit financial, coverage, composition and event-boundary goldens."""

import uuid
from datetime import timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.access.models import User
from app.modules.management_actions.models import ManagementActionHistory
from app.modules.management_reporting.comparison import compare
from app.modules.management_reporting.schemas import SnapshotOut
from app.modules.portfolio.schemas import MoneyMetric, Risk
from app.modules.portfolio.service import overview
from app.modules.project_analysis.calculations import ratio
from tests.modules.test_management_reporting import capture


def pair(admin_client: TestClient, project_id: str) -> tuple[SnapshotOut, SnapshotOut]:
    a = SnapshotOut.model_validate(capture(admin_client, project_id))
    b = a.model_copy(deep=True)
    b.id = uuid.uuid4()
    b.captured_at = a.captured_at + timedelta(seconds=10)
    return a, b


def metric(
    code: str, currency: str, amount: Decimal | None, availability: str = "available"
) -> MoneyMetric:
    return MoneyMetric(
        metric_code=code,
        currency=currency,
        amount=amount,
        availability=availability,
        source_basis="Governed source basis",
        contributing_project_count=int(amount is not None),
        missing_project_count=int(amount is None),
        drilldown="/projects/",
    )


def refresh(report: SnapshotOut) -> None:
    report.payload.overview = overview(report.payload.projects, report.as_of_date)


def test_original_currency_and_penetration_goldens(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    a, b = pair(admin_client, project_id)
    ap, bp = a.payload.projects[0], b.payload.projects[0]
    ap.money = [
        metric("contracted_value", "JOD", "1000000"),
        metric("contracted_value", "USD", "500000"),
    ]
    bp.money = [
        metric("contracted_value", "JOD", "1250000"),
        metric("contracted_value", "USD", "450000"),
    ]
    ap.committed_units = 40
    ap.eligible_units = 100
    ap.sales_penetration = ratio(40, 100, "Owner penetration")
    bp.committed_units = 47
    bp.eligible_units = 110
    bp.sales_penetration = ratio(47, 110, "Owner penetration")
    refresh(a)
    refresh(b)
    c = compare(db, a, b)
    rows = {
        m.currency: m
        for m in c.movements
        if m.metric == "contracted_value" and m.project_id is None
    }
    assert rows["JOD"].delta == Decimal("250000")
    assert rows["USD"].delta == Decimal("-50000")
    assert len(rows) == 2
    penetration = next(
        m for m in c.movements if m.metric == "sales_penetration" and m.project_id is None
    )
    assert penetration.delta == Decimal("2.73") and penetration.unit == "percentage_points"
    assert (
        next(m for m in c.movements if m.metric == "eligible_units" and m.project_id is None).delta
        == 10
    )
    bp.eligible_units = 100
    bp.sales_penetration = ratio(47, 100, "Owner penetration")
    refresh(b)
    assert next(
        m
        for m in compare(db, a, b).movements
        if m.metric == "sales_penetration" and m.project_id is None
    ).delta == Decimal("7.00")


def test_unavailable_missing_currency_and_composition_never_become_zero(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    a, b = pair(admin_client, project_id)
    a.scope_type = b.scope_type = "portfolio"
    a.project_id = b.project_id = None
    a.payload.projects[0].money = [metric("unrestricted_cash", "JOD", None, "unavailable")]
    b.payload.projects[0].money = [
        metric("unrestricted_cash", "JOD", "300000"),
        metric("contracted_value", "USD", "500000"),
    ]
    refresh(a)
    refresh(b)
    c = compare(db, a, b)
    assert all(m.delta is None for m in c.movements if m.unit == "money")
    assert any(
        m.prior_availability == "unavailable" and m.current_availability == "available"
        for m in c.movements
    )
    added = b.payload.projects[0].model_copy(deep=True)
    added.project_id = uuid.uuid4()
    added.code = "ADDED"
    b.payload.projects.append(added)
    refresh(b)
    c = compare(db, a, b)
    assert c.composition_changed and c.added_projects[0].project_id == added.project_id
    assert all(m.delta is None for m in c.movements if m.project_id is None)
    a.payload.projects.append(added)
    b.payload.projects.pop()
    refresh(a)
    refresh(b)
    assert compare(db, a, b).removed_projects[0].project_id == added.project_id


def test_forecast_currency_and_version_changes_keep_actual_denominations(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    a, b = pair(admin_client, project_id)
    for report, currency, amount in ((a, "JOD", "-600000"), (b, "USD", "-400000")):
        for outlook in report.payload.outlooks:
            item = next(i for i in outlook.items if i.item_type == "cashflow_forecast")
            item.currency = currency
            item.amount = Decimal(amount)
            item.peak_deficit = -Decimal(amount)
            item.availability = "available"
            item.source_version_id = uuid.uuid4()
    c = compare(db, a, b)
    rows = [m for m in c.movements if m.metric.startswith("cashflow_forecast_amount")]
    assert len(rows) == 3
    assert all(
        m.prior_currency == "JOD" and m.current_currency == "USD" and m.delta is None for m in rows
    )
    for outlook in b.payload.outlooks:
        next(i for i in outlook.items if i.item_type == "cashflow_forecast").currency = "JOD"
    rows = [
        m
        for m in compare(db, a, b).movements
        if m.metric.startswith("cashflow_forecast_peak_deficit")
    ]
    assert all(m.delta == Decimal("-200000") for m in rows)


def test_cash_coverage_deterioration_and_decimal_construction_basis(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    a, b = pair(admin_client, project_id)
    ap, bp = a.payload.projects[0], b.payload.projects[0]
    ap.money = [
        metric("unrestricted_cash", "JOD", Decimal("300000.123")),
        metric("construction_eac", "JOD", Decimal("12000000.001")),
        metric("construction_budget", "JOD", Decimal("10000000.001")),
    ]
    bp.money = [
        metric("unrestricted_cash", "JOD", None, "unavailable"),
        metric("construction_eac", "JOD", Decimal("12000000.003")),
        metric("construction_budget", "JOD", Decimal("10000000.002")),
    ]
    bp.money[0].reason = "Cashflow source currency mismatch."
    refresh(a)
    refresh(b)
    result = compare(db, a, b)
    rows = {m.metric: m for m in result.movements if m.project_id == ap.project_id}
    cash = rows["unrestricted_cash"]
    assert cash.prior == Decimal("300000.123") and cash.current is None and cash.delta is None
    assert cash.prior_availability == "available" and cash.current_availability == "unavailable"
    assert not cash.comparable
    assert rows["construction_eac"].delta == Decimal("0.002")
    assert rows["construction_budget"].delta == Decimal("0.001")
    bp.money[1].source_basis = "Different estimate basis"
    assert (
        next(
            m
            for m in compare(db, a, b).movements
            if m.project_id == ap.project_id and m.metric == "construction_eac"
        ).delta
        is None
    )


def test_risks_use_stable_identity_and_missing_coverage_is_not_resolution(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    a, b = pair(admin_client, project_id)

    def risk(key: str) -> Risk:
        return Risk(
            risk_id=key,
            risk_code="UNRESOLVED_BLOCKING_PERMIT",
            category="permits",
            severity="high",
            project_id=project_id,
            project_code="P",
            project_name="Project",
            title=key,
            reason="Unresolved source",
            source_metric=key,
            source_value="1",
            basis="Owner predicate",
            observation_date=a.as_of_date,
            drilldown="/projects/",
        )

    a.payload.projects[0].risks = [risk("resolved"), risk("continuing")]
    b.payload.projects[0].risks = [risk("new"), risk("continuing")]
    c = compare(db, a, b)
    assert {r.classification for r in c.risks} == {"new", "resolved", "continuing"}
    next(
        e
        for e in b.payload.projects[0].risk_evaluations
        if e.risk_code == "UNRESOLVED_BLOCKING_PERMIT"
    ).availability = "unavailable"
    assert (
        next(
            r for r in compare(db, a, b).risks if r.prior and r.prior.risk_id == "resolved"
        ).classification
        == "coverage_changed"
    )


def test_history_exact_interval_and_visibility_watermark(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    owner = db.scalar(select(User).where(User.email == "admin@example.com"))
    action = admin_client.post(
        "/api/v1/portfolio/actions",
        json={
            "project_id": project_id,
            "title": "Boundary commitment",
            "owner_user_id": str(owner.id),
            "due_date": "2026-01-01",
        },
    ).json()
    a, b = pair(admin_client, project_id)
    b.payload.actions[0].version = 5
    b.payload.action_frontier[0].version = 5
    for version, when, state in (
        (2, a.captured_at, "completed"),
        (3, a.captured_at + timedelta(seconds=1), "in_progress"),
        (4, b.captured_at, "completed"),
        (5, b.captured_at + timedelta(seconds=1), "open"),
        (6, b.captured_at - timedelta(seconds=1), "completed"),
    ):
        db.add(
            ManagementActionHistory(
                action_id=uuid.UUID(action["id"]),
                version=version,
                actor_user_id=owner.id,
                occurred_at=when,
                event_type="reopened" if state == "open" else "status_changed",
                changes={"status": {"old": "open", "new": state}},
            )
        )
    db.commit()
    c = compare(db, a, b)
    assert c.execution.started == 1 and c.execution.completed == 1 and c.execution.reopened == 0
    assert c.execution.created == 0
    # A later backdated event is above the captured version frontier and excluded.
    db.add(
        ManagementActionHistory(
            action_id=uuid.UUID(action["id"]),
            version=7,
            actor_user_id=owner.id,
            occurred_at=b.captured_at,
            event_type="reopened",
            changes={},
        )
    )
    db.commit()
    assert compare(db, a, b) == c


def test_terminal_retention_reopen_and_consecutive_intervals(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    from tests.modules.test_management_reporting import ROOT

    owner = db.scalar(select(User).where(User.email == "admin@example.com"))
    a = capture(admin_client, project_id)
    response = admin_client.post(
        "/api/v1/portfolio/actions",
        json={
            "project_id": project_id,
            "title": "Terminal details must not accumulate in snapshots",
            "owner_user_id": str(owner.id),
            "due_date": "2026-01-01",
        },
    )
    assert response.status_code == 201, response.text
    action = response.json()

    def transition(status: str) -> None:
        nonlocal action
        response = admin_client.post(
            f"/api/v1/portfolio/actions/{action['id']}/transitions",
            json={
                "expected_version": action["version"],
                "status": status,
                "reason": "Historical interval golden",
            },
        )
        assert response.status_code == 200, response.text
        action = response.json()

    def comparison(prior: dict, current: dict) -> dict:
        response = admin_client.get(
            f"{ROOT}/comparisons?from_snapshot_id={prior['id']}&to_snapshot_id={current['id']}"
        )
        assert response.status_code == 200, response.text
        return response.json()

    transition("cancelled")
    b = capture(admin_client, project_id)
    assert b["payload"]["actions"] == []
    assert b["payload"]["action_counts"]["cancelled"] == 1
    assert b["payload"]["action_frontier"] == [
        {"id": action["id"], "project_id": project_id, "version": action["version"]}
    ]
    ab = comparison(a, b)
    board = admin_client.get(f"{ROOT}/snapshots/{b['id']}/board-pack").json()
    assert ab["execution"]["created"] == ab["execution"]["cancelled"] == 1
    transition("open")
    transition("in_progress")
    transition("completed")
    c = capture(admin_client, project_id)
    bc = comparison(b, c)
    assert bc["execution"]["created"] == bc["execution"]["cancelled"] == 0
    assert all(bc["execution"][key] == 1 for key in ("started", "completed", "reopened"))
    assert comparison(a, b) == ab
    assert admin_client.get(f"{ROOT}/snapshots/{b['id']}/board-pack").json() == board
    ac = comparison(a, c)
    for key in ("created", "started", "completed", "reopened", "cancelled"):
        assert ac["execution"][key] == ab["execution"][key] + bc["execution"][key]
