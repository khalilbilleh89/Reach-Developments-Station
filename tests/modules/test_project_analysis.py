"""PostgreSQL analysis contracts: sources, immutable reads and denied access."""

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.project_analysis.calculations import forecast, ratio
from app.modules.sales.models import SaleContract
from tests.factories import client_for, make_user
from tests.modules.conftest import grant_access
from tests.modules.test_commissions_review import snapshot


def root(project_id: str) -> str:
    return f"/api/v1/projects/{project_id}/analysis"


def test_decimal_denominators_and_run_rate() -> None:
    assert ratio(40, 100, "eligible inventory").percentage == Decimal("40.00")
    assert ratio(20, 40, "type A").percentage == Decimal("50.00")
    assert ratio(10, 60, "type B").percentage == Decimal("16.67")
    assert ratio(20, 30, "demand share").percentage == Decimal("66.67")
    assert ratio(0, 0, "empty").percentage is None
    assert ratio(None, None, "unknown").percentage is None
    golden = forecast(date(2026, 9, 8), 30, [4, 5, 6], 3)
    assert golden.average_monthly_absorption == Decimal("5")
    assert golden.estimated_months_to_sell == Decimal("6")
    for values, observed in (([0, 0, 0], 3), ([1, -3, 0], 3), ([4, 5, 6], 2)):
        result = forecast(date(2026, 9, 8), 30, values, observed)
        assert result.availability == "unavailable" and result.estimated_months_to_sell is None
    assert forecast(date(2026, 9, 8), 0, [0, 0, 0], 3).estimated_months_to_sell == 0


def test_empty_sources_and_reads_have_no_side_effects(
    manager_member_client: TestClient,
    project_id: str,
    db: Session,
) -> None:
    before = snapshot(db)
    for section in ("fundamental", "financial", "technical"):
        response = manager_member_client.get(f"{root(project_id)}/{section}")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["context"]["project_id"] == project_id
        if section == "fundamental":
            assert body["position"]["penetration"]["percentage"] is None
            assert body["view_basis"]["availability"] == "unavailable"
        if section == "technical":
            for key in ("permit_basis", "consultant_basis", "construction_basis", "area_coverage"):
                assert body[key]["availability"] == "unavailable"
        if section == "financial":
            assert len(body["monthly"]) == 12
        assert snapshot(db) == before


def test_authoritative_activation_advisor_branch_and_asof(
    finance_client: TestClient,
    active_sale: str,
    project_id: str,
    db: Session,
) -> None:
    sale = db.get(SaleContract, uuid.UUID(active_sale))
    sale.activated_at = datetime(2026, 6, 30, 23, 59, tzinfo=UTC)
    sale.sales_branch_code = "BRANCH-A"
    advisor = make_user(db, email="analysis-advisor@example.com", roles=("sales_advisor",))
    sale.advisor_user_id = advisor.id
    db.commit()
    response = finance_client.get(
        f"{root(project_id)}/fundamental",
        params={"as_of": "2026-07-31", "period_from": "2026-06-01"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["monthly_sales"][0]["activations"] == 1
    assert body["monthly_sales"][1]["activations"] == 0
    assert body["branches"][0]["label"] == "BRANCH-A"
    assert body["salespeople"][0]["label"] == advisor.display_name
    assert (
        Decimal(body["monthly_sales"][0]["contracted_value"][0]["amount"])
        == sale.total_contract_price
    )
    assert body["position"]["availability"] == "unavailable"
    assert body["forecast"]["estimated_months_to_sell"] is None
    sale.cancelled_at = datetime(2026, 7, 1, tzinfo=UTC)
    db.commit()
    response = finance_client.get(
        f"{root(project_id)}/fundamental",
        params={"as_of": "2026-07-31", "period_from": "2026-06-01"},
    )
    body = response.json()
    assert body["monthly_sales"][1]["cancellations"] == 1
    assert body["monthly_sales"][1]["net_absorption"] == -1
    assert body["branches"] == []
    before = finance_client.get(
        f"{root(project_id)}/fundamental",
        params={"as_of": "2026-06-29", "period_from": "2026-06-01"},
    ).json()
    assert before["monthly_sales"][0]["activations"] == 0
    assert "buyer" not in str(body["branches"]).lower()


def test_role_matrix_phase_scope_and_cross_project(
    admin_client: TestClient,
    project_id: str,
    phase_id: str,
    db: Session,
) -> None:
    common = {
        "system_admin",
        "project_manager",
        "finance",
        "approver_cfo",
        "executive_viewer",
        "auditor",
    }
    expected = {
        "fundamental": common | {"sales_operations"},
        "financial": common,
        "technical": common | {"design_engineering"},
    }
    for role in sorted(
        common | {"sales_advisor", "sales_operations", "design_engineering", "legal", "collections"}
    ):
        user = make_user(db, email=f"analysis-{role}@example.com", roles=(role,))
        grant_access(admin_client, project_id, user)
        client = client_for(user.email)
        for section, allowed in expected.items():
            response = client.get(f"{root(project_id)}/{section}")
            assert response.status_code == (200 if role in allowed else 403), (
                role,
                section,
                response.text,
            )
    scoped = make_user(db, email="analysis-phase@example.com", roles=("project_manager",))
    grant_access(admin_client, project_id, scoped)
    assert (
        admin_client.patch(
            f"/api/v1/projects/{project_id}/access/{scoped.id}/phase-scope",
            json={"phase_scope": "selected"},
        ).status_code
        == 200
    )
    admin_client.put(f"/api/v1/projects/{project_id}/access/{scoped.id}/phases/{phase_id}")
    client = client_for(scoped.email)
    for section in expected:
        assert client.get(f"{root(project_id)}/{section}").status_code == 403
        assert client.get(f"{root(str(uuid.uuid4()))}/{section}").status_code == 404


def test_section_authorization_precedes_context_lookup(
    admin_client: TestClient,
    manager_member_client: TestClient,
    project_id: str,
    phase_id: str,
    building_id: str,
    db: Session,
) -> None:
    other_phase = admin_client.post(
        f"/api/v1/projects/{project_id}/inventory/phases",
        json={"code": "PHASE-2", "name": "Phase 2", "sequence": 2},
    )
    assert other_phase.status_code == 201, other_phase.text
    filters = (
        {},
        {"phase_id": phase_id},
        {"phase_id": str(uuid.uuid4())},
        {"building_id": building_id},
        {"building_id": str(uuid.uuid4())},
        {"phase_id": other_phase.json()["id"], "building_id": building_id},
    )
    for role, sections in (
        ("sales_advisor", ("fundamental", "financial", "technical")),
        ("design_engineering", ("financial",)),
    ):
        user = make_user(db, email=f"precedence-{role}@example.com", roles=(role,))
        grant_access(admin_client, project_id, user)
        client = client_for(user.email)
        # Project access queries are allowed; Analysis preparation must never start.
        with patch("app.modules.project_analysis.service.context") as prepare_context:
            for section in sections:
                for params in filters:
                    response = client.get(f"{root(project_id)}/{section}", params=params)
                    assert response.status_code == 403, (role, section, params, response.text)
            prepare_context.assert_not_called()
    for section in ("fundamental", "financial", "technical"):
        for index in (2, 4, 5):
            response = manager_member_client.get(
                f"{root(project_id)}/{section}", params=filters[index]
            )
            assert response.status_code == 404, (section, filters[index], response.text)


def test_date_and_scope_validation(manager_member_client: TestClient, project_id: str) -> None:
    url = f"{root(project_id)}/fundamental"
    for params in (
        {"period_from": "2026-12-10", "period_to": "2026-12-01"},
        {"as_of": (datetime.now(UTC).date() + timedelta(days=1)).isoformat()},
        {"period_from": "2000-01-01"},
    ):
        assert manager_member_client.get(url, params=params).status_code == 422
    assert manager_member_client.get(url, params={"phase_id": str(uuid.uuid4())}).status_code == 404


def test_observed_premium_requires_comparable_measurements() -> None:
    from types import SimpleNamespace

    from app.modules.inventory.physical import COMPONENTS
    from app.modules.project_analysis.service import observed_premiums

    currency = uuid.uuid4()
    units = [
        SimpleNamespace(id=uuid.uuid4(), unit_type_code="A", view_class_code=view)
        for view in ("SEA", "CITY")
    ]
    rows = [
        SimpleNamespace(unit_id=unit.id, currency_id=currency, total_contract_price=Decimal(value))
        for unit, value in zip(units, ("120000", "100000"), strict=True)
    ]
    lines = {
        unit.id: [
            {
                "physical_component": key,
                "unit_of_measure": "sqm",
                "raw_area": Decimal("100") if key == "internal" else Decimal("0"),
            }
            for key in COMPONENTS
        ]
        for unit in units
    }
    results = observed_premiums(units, rows, {currency: "EUR"}, lines)
    sea = next(row for row in results if row.view == "SEA")
    assert sea.percentage == Decimal("20.00")
    assert sea.sample_size == sea.baseline_sample == 1
    assert sea.view_price_per_gross_area == Decimal("1200.00")
    missing = observed_premiums(units, rows, {currency: "EUR"}, {})
    assert all(row.percentage is None and row.availability == "unavailable" for row in missing)
    other = uuid.uuid4()
    rows[1].currency_id = other
    mixed = observed_premiums(units, rows, {currency: "EUR", other: "USD"}, lines)
    assert all(row.percentage is None and "Currencies differ" in row.reason for row in mixed)


def test_current_inventory_branch_currency_and_query_count(
    finance_client: TestClient,
    active_sale: str,
    project_id: str,
    db: Session,
) -> None:
    from sqlalchemy import event

    from app.core.database import get_engine
    from app.modules.inventory.models import Unit
    from app.modules.sales.models import Reservation
    from app.modules.settings.models import Currency

    original = db.get(SaleContract, uuid.UUID(active_sale))
    original.sales_branch_code = "A"
    unit = db.get(Unit, original.unit_id)
    unit.unit_type_code = "TYPE-A"
    unit.view_class_code = "SEA"

    def clone(model: type, row: object, **changes: object) -> object:
        values = {column.name: getattr(row, column.name) for column in model.__table__.columns}
        values.update(id=uuid.uuid4(), **changes)
        created = model(**values)
        db.add(created)
        db.flush()
        return created

    other = Currency(code="USD", name="US Dollar", minor_units=2)
    db.add(other)
    db.flush()
    for index, branch in enumerate(("A", "B")):
        new_unit = clone(
            Unit,
            unit,
            unit_number=f"AN-{index}",
            unit_reference=f"AN-{index}",
            unit_type_code="TYPE-B" if index else "TYPE-A",
            view_class_code=None,
        )
        reservation = clone(
            Reservation,
            db.get(Reservation, original.reservation_id),
            unit_id=new_unit.id,
            reservation_number=f"AN-{index}",
        )
        clone(
            SaleContract,
            original,
            unit_id=new_unit.id,
            reservation_id=reservation.id,
            sale_number=f"AN-{index}",
            spa_number=f"AN-{index}",
            sales_branch_code=branch,
            currency_id=other.id if index else original.currency_id,
        )
    clone(
        Unit,
        unit,
        unit_number="AN-unknown",
        unit_reference="AN-unknown",
        commercial_status="available",
        unit_type_code=None,
        view_class_code=None,
    )
    clone(Unit, unit, unit_number="AN-held", unit_reference="AN-held", commercial_status="held")
    db.commit()
    before = snapshot(db)
    statements = []
    engine = get_engine()

    def capture(
        connection: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        response = finance_client.get(f"{root(project_id)}/fundamental")
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["position"]["eligible_units"] == 4
    assert body["position"]["committed_units"] == 3
    assert body["position"]["penetration"]["percentage"] == "75.00"
    assert [row["label"] for row in body["branches"]] == ["A", "B"]
    assert [row["sales_count"] for row in body["branches"]] == [2, 1]
    assert len(body["monthly_sales"][-1]["contracted_value"]) == 2
    assert body["view_basis"]["availability"] == "partial"
    assert any(row["label"] == "Unknown / Unclassified" for row in body["property_types"])
    assert snapshot(db) == before
    assert 0 < len(statements) < 30, len(statements)


def test_deployed_main_upgrade_retains_source_data(
    manager_member_client: TestClient,
    project_id: str,
    unit_id: str,
    confirmed_receipt: str,
    db: Session,
) -> None:
    from alembic import command
    from sqlalchemy import text

    from tests.conftest import alembic_config
    from tests.test_migrations import HEAD_REVISION

    del manager_member_client, project_id, unit_id, confirmed_receipt
    excluded = (
        "alembic_version",
        "management_report_snapshots",
        "management_report_snapshot_projects",
    )
    before = snapshot(db, excluded)
    db.rollback()
    config = alembic_config()
    # Capture the source schema at the historical upgrade boundary. Tables added
    # later (including project inventory choices) do not exist at that boundary;
    # their migration/backfill contracts have dedicated migration tests.
    command.downgrade(config, "0019_management_actions")
    assert db.scalar(text("SELECT version_num FROM alembic_version")) == "0019_management_actions"
    source_tables = snapshot(db, excluded).keys()
    db.rollback()
    command.upgrade(config, "head")
    command.check(config)
    assert db.scalar(text("SELECT version_num FROM alembic_version")) == HEAD_REVISION
    after = snapshot(db, excluded)
    assert {table: after[table] for table in source_tables} == {
        table: before[table] for table in source_tables
    }


def test_financial_confirmation_reversal_and_business_date(
    collections_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    collecting_sale: str,
    db: Session,
) -> None:
    from tests.modules.conftest import (
        at,
        backdate,
        collections_url,
        confirm_receipt,
        record_receipt,
    )

    today = datetime.now(UTC).date()
    business_day = today - timedelta(days=12)
    receipt = record_receipt(
        collections_client,
        project_id,
        collecting_sale,
        "400.00",
        receipt_date=business_day.isoformat(),
    )
    assert receipt.status_code == 201, receipt.text
    receipt_id = receipt.json()["id"]
    assert confirm_receipt(finance_client, project_id, receipt_id).status_code == 200
    backdate(
        db,
        table="collection_receipts",
        row_id=receipt_id,
        confirmed_at=at(today - timedelta(days=10)),
    )

    def received_at(cutoff: date) -> Decimal:
        response = finance_client.get(
            f"{root(project_id)}/financial",
            params={"as_of": cutoff.isoformat(), "period_from": business_day.isoformat()},
        )
        assert response.status_code == 200, response.text
        months = response.json()["monthly"]
        receipt_month = business_day.replace(day=1).isoformat()
        return sum(
            (
                Decimal(row["customer_cash_received"])
                for row in months
                if row["month"] == receipt_month
            ),
            Decimal("0"),
        )

    assert received_at(today - timedelta(days=11)) == 0
    assert received_at(today - timedelta(days=5)) == Decimal("400")
    response = finance_client.post(
        f"{collections_url(project_id)}/receipts/{receipt_id}/reverse",
        json={"reason": "Returned transfer"},
    )
    assert response.status_code == 200, response.text
    assert received_at(today) == 0
    assert received_at(today - timedelta(days=5)) == Decimal("400")
