"""Populated PostgreSQL portfolio size, currency and weighted-ratio goldens."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.modules.inventory.models import Unit
from app.modules.portfolio import service
from app.modules.projects.models import Project
from app.modules.sales.models import Reservation, SaleContract
from tests.modules.test_portfolio import metric


def copy_project(db: Session, source: uuid.UUID, code: str) -> uuid.UUID:
    """Replicate a synthetic governed fixture graph, preserving its foreign keys.

    Setup only: never used by a measured read or by production. Shared users and
    country configuration stay shared, while every project-owned row gets a new ID.
    """
    tables = [
        table
        for table in Base.metadata.sorted_tables
        if "project_id" in table.c or table.name == "projects"
    ]
    data = {
        table.name: [
            dict(row)
            for row in db.execute(
                select(table).where(
                    table.c.id == source
                    if table.name == "projects"
                    else table.c.project_id == source
                )
            ).mappings()
        ]
        for table in tables
    }
    ids = {row["id"]: uuid.uuid4() for rows in data.values() for row in rows if "id" in row}
    for table in tables:
        for row in data[table.name]:
            values = {
                key: ids.get(value, value) if isinstance(value, uuid.UUID) else value
                for key, value in row.items()
            }
            if table.name == "projects":
                values.update(code=code, name=code)
            db.execute(table.insert().values(**values))
    db.commit()
    return ids[source]


def test_populated_one_vs_twenty_queries_and_currency_buckets(
    project_id: str,
    confirmed_receipt: str,
    active_construction_forecast: str,
    admin_client: TestClient,
    db: Session,
) -> None:
    source = uuid.UUID(project_id)
    pids = [source]
    for index in range(1, 20):
        pids.append(copy_project(db, source, f"SCALE-{index:02}"))
    today = datetime.now(UTC).date()
    counts = []
    captured: list[tuple[str, object]] = []

    def count(
        conn: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        captured.append((statement, parameters))

    for population in (pids[:1], pids):
        captured.clear()
        event.listen(db.bind, "before_cursor_execute", count)
        try:
            rows = service.summaries(
                db, select(Project.id).where(Project.id.in_(population)), today
            )
        finally:
            event.remove(db.bind, "before_cursor_execute", count)
        counts.append(len(captured))
        assert len(rows) == len(population)
        assert all(row.committed_units == 1 and row.active_sold_units == 1 for row in rows)
    assert counts[1] <= counts[0] + 2, counts
    assert counts[1] < 80, counts
    assert all(sql.lstrip().upper().startswith("SELECT") for sql, _ in captured)
    print(f"Portfolio populated query counts: 1={counts[0]}, 20={counts[1]}")
    # Explain actual scoped production statements with their original bind values.
    for table in (
        "units",
        "collection_receipts",
        "construction_budget_versions",
        "construction_forecast_lines",
        "cashflow_development_movements",
    ):
        sql, parameters = next(
            (sql, params)
            for sql, params in captured
            if f"FROM {table} " in sql or f"FROM {table}\n" in sql
        )
        plan = (
            db.connection()
            .exec_driver_sql("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql, parameters)
            .scalar_one()
        )
        assert any(
            key in sql for key in ("projects.id", "forecast_version_id IN", "sale_contract_id IN")
        )
        print(
            f"EXPLAIN {table}: {plan[0]['Plan']['Node Type']}, "
            f"rows={plan[0]['Plan']['Actual Rows']}, {plan[0]['Execution Time']} ms"
        )
    # A and B remain JOD; C contributes original USD contract values.
    currency = admin_client.post(
        "/api/v1/settings/currencies", json={"code": "USD", "name": "US dollar"}
    )
    assert currency.status_code == 201, currency.text
    usd = uuid.UUID(currency.json()["id"])
    project = db.get(Project, pids[2])
    project.base_currency_id = usd
    sale = db.scalar(select(SaleContract).where(SaleContract.project_id == pids[2]))
    sale.currency_id = usd
    db.commit()
    summary = service.overview(
        service.summaries(db, select(Project.id).where(Project.id.in_(pids[:3])), today), today
    ).model_dump(mode="json")
    price = sale.total_contract_price
    assert Decimal(metric(summary, "contracted_value", "JOD")["amount"]) == price * 2
    assert Decimal(metric(summary, "contracted_value", "USD")["amount"]) == price
    assert "contracted_value" not in summary


def test_weighted_penetration_is_ten_percent(
    active_sale: str, project_id: str, db: Session
) -> None:
    source = uuid.UUID(project_id)
    second = copy_project(db, source, "WEIGHTED-B")
    sale = db.get(SaleContract, uuid.UUID(active_sale))
    reservation = db.get(Reservation, sale.reservation_id)
    for pid, population, commitments in ((source, 10, 9), (second, 90, 1)):
        original = db.scalar(select(Unit).where(Unit.project_id == pid))
        for index in range(1, population):
            values = {
                col.name: getattr(original, col.name)
                for col in Unit.__table__.columns
                if col.name != "id"
            }
            values.update(
                unit_number=f"P-{index}",
                unit_reference=f"PORT-{index}",
                commercial_status="available",
            )
            unit = Unit(**values)
            db.add(unit)
            db.flush()
            if index < commitments:
                values = {
                    col.name: getattr(reservation, col.name)
                    for col in Reservation.__table__.columns
                    if col.name != "id"
                }
                values.update(unit_id=unit.id, reservation_number=f"PORT-{index}")
                reserved = Reservation(**values)
                db.add(reserved)
                db.flush()
                values = {
                    col.name: getattr(sale, col.name)
                    for col in SaleContract.__table__.columns
                    if col.name != "id"
                }
                values.update(
                    unit_id=unit.id,
                    sale_number=f"PORT-{index}",
                    spa_number=f"SPA-{index}",
                    reservation_id=reserved.id,
                )
                db.add(SaleContract(**values))
        db.commit()
    today = datetime.now(UTC).date()
    rows = service.summaries(db, select(Project.id).where(Project.id.in_([source, second])), today)
    overview = service.overview(rows, today)
    assert overview.eligible_units == 100
    assert overview.committed_units == 10
    assert overview.sales_penetration.percentage == Decimal("10.00")
    assert overview.sales_penetration.numerator == 10
    assert overview.sales_penetration.denominator == 100
