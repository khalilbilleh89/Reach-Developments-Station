"""Real PostgreSQL risk-source bounds, global pages and scoped coverage."""

import uuid
from collections import Counter
from datetime import UTC, datetime
from time import perf_counter

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.modules.portfolio import calculations, risk_projection, schemas, service
from app.modules.projects.models import Permit, Project
from tests.factories import client_for, make_user
from tests.modules.conftest import (
    create_cashflow_forecast,
    govern_cashflow_forecast,
    grant_access,
    permit_payload,
    set_cashflow_line,
)
from tests.modules.test_portfolio_scale import copy_project
from tests.modules.test_prelaunch import editable
from tests.modules.test_prelaunch import payload as expense_payload


def test_risk_pages_skip_summaries_and_scale_with_global_order(
    project_id: str,
    confirmed_receipt: str,
    active_construction_forecast: str,
    admin_client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocker = admin_client.post(
        f"/api/v1/projects/{project_id}/permits", json=permit_payload(is_blocking=True)
    )
    assert blocker.status_code == 201, blocker.text
    pids = [uuid.UUID(project_id)]
    for index in range(1, 50):
        pids.append(copy_project(db, pids[0], f"RISK-{index:02}"))
    today = datetime.now(UTC).date()
    scope = select(Project.id).where(Project.id.in_(pids))
    summaries = service.summaries(db, scope, today)
    expected = sorted(
        (risk for row in summaries for risk in row.risks), key=calculations.risk_order
    )
    assert {row.severity for row in expected} == {"high", "attention"}
    expected_coverage = sum(
        any(item.availability != "available" for item in row.risk_evaluations) for row in summaries
    )

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("Risk pagination must not compose full summaries or unrelated KPIs")

    # These tripwires fail the reviewed implementation, even if its output is sliced.
    monkeypatch.setattr(service, "summaries", forbidden)
    monkeypatch.setattr(service, "_project_summary", forbidden)
    monkeypatch.setattr(schemas.ProjectSummary, "__init__", forbidden)
    monkeypatch.setattr(schemas.MoneyMetric, "__init__", forbidden)
    monkeypatch.setattr(schemas.Design, "__init__", forbidden)
    monkeypatch.setattr(service.commissions, "released", forbidden)
    monkeypatch.setattr(service, "forecast", forbidden)
    calls: Counter = Counter()

    def instrument(owner: str) -> None:
        module = getattr(service, owner)
        original = module.positions

        def measured(*args: object, **kwargs: object) -> dict:
            calls[owner] += 1
            if owner in {"sales", "collections", "construction", "development"}:
                assert kwargs["risk_only"] is True
            return original(*args, **kwargs)

        monkeypatch.setattr(module, "positions", measured)

    for owner in (
        "inventory",
        "sales",
        "collections",
        "cashflow",
        "construction",
        "development",
        "consultant",
    ):
        instrument(owner)
    constructed = []
    original_init = schemas.Risk.__init__

    def risk_init(self: schemas.Risk, **fields: object) -> None:
        constructed.append(fields["risk_id"])
        original_init(self, **fields)

    monkeypatch.setattr(schemas.Risk, "__init__", risk_init)
    first = admin_client.get("/api/v1/portfolio/risks?limit=1&offset=0")
    assert first.status_code == 200, first.text
    assert first.json()["items"] == [expected[0].model_dump(mode="json")]
    assert constructed == [expected[0].risk_id]
    assert set(calls.values()) == {1} and len(calls) == 7

    counts = []
    statements = []

    def capture(
        conn: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        statements.append(statement)

    for population in (pids[:1], pids[:20], pids):
        statements.clear()
        calls.clear()
        constructed.clear()
        event.listen(db.bind, "before_cursor_execute", capture)
        started = perf_counter()
        try:
            page = risk_projection.page(
                db, select(Project.id).where(Project.id.in_(population)), today, limit=20, offset=0
            )
        finally:
            elapsed = perf_counter() - started
            event.remove(db.bind, "before_cursor_execute", capture)
        counts.append(len(statements))
        assert len(constructed) == min(20, page.total)
        assert set(calls.values()) == {1} and len(calls) == 7
        assert all(sql.lstrip().upper().startswith("SELECT") for sql in statements)
        assert not any(
            "land_parcels" in sql or "commission_distributions" in sql for sql in statements
        )
        assert page.total == sum(row.project_id in population for row in expected)
        print(
            f"Risk page limit=20 projects={len(population)} queries={len(statements)} "
            f"runtime_ms={elapsed * 1000:.2f} summaries=0 response_risks={len(constructed)}"
        )
    assert max(counts) <= counts[0] + 2, counts

    # Three pages concatenate to the exact logical global set, including the
    # high/attention boundary across projects; totals never mean current page.
    size = (len(expected) + 2) // 3
    pages = [risk_projection.page(db, scope, today, limit=size, offset=i * size) for i in range(3)]
    assert [item for page in pages for item in page.items] == expected
    assert all(page.total == len(expected) for page in pages)
    assert all(page.unavailable_project_count == expected_coverage for page in pages)
    for offset in (len(expected), len(expected) + 100):
        page = risk_projection.page(db, scope, today, limit=1, offset=offset)
        assert page.items == [] and page.total == len(expected)
        assert page.unavailable_project_count == expected_coverage


def test_hidden_high_risks_do_not_change_counts_coverage_or_offsets(
    project_id: str,
    confirmed_receipt: str,
    admin_client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Clone before granting A: fixture copying also copies existing memberships.
    hidden = copy_project(db, uuid.UUID(project_id), "AAA-HIDDEN")
    user = make_user(db, email="risk-a-only@example.com", roles=("finance",))
    grant_access(admin_client, project_id, user)
    client = client_for(user.email)
    offsets = (0, 1, 2, 30, 1000)

    def pages() -> list[dict]:
        responses = [client.get(f"/api/v1/portfolio/risks?limit=1&offset={i}") for i in offsets]
        assert all(response.status_code == 200 for response in responses)
        return [response.json() for response in responses]

    before = pages()
    assert before[0]["total"] >= 1
    created = admin_client.post(
        f"/api/v1/projects/{hidden}/permits", json=permit_payload(is_blocking=True)
    )
    assert created.status_code == 201, created.text
    template = db.get(Permit, uuid.UUID(created.json()["id"]))
    for index in range(29):
        values = {
            col.name: getattr(template, col.name)
            for col in Permit.__table__.columns
            if col.name != "id"
        }
        values["permit_code"] = f"HIDDEN-{index}"
        db.add(Permit(**values))
    db.commit()
    global_page = admin_client.get("/api/v1/portfolio/risks?limit=100").json()
    assert (
        sum(
            row["project_id"] == str(hidden) and row["severity"] == "high"
            for row in global_page["items"]
        )
        == 30
    )
    assert global_page["unavailable_project_count"] == before[0]["unavailable_project_count"] + 1

    def instrument(owner: str) -> None:
        module = getattr(service, owner)
        original = module.positions

        def scoped(session: Session, project_ids: object, *args: object, **kwargs: object) -> dict:
            assert list(session.scalars(project_ids)) == [uuid.UUID(project_id)]
            result = original(session, project_ids, *args, **kwargs)
            assert hidden not in result
            return result

        monkeypatch.setattr(module, "positions", scoped)

    for owner in (
        "inventory",
        "sales",
        "collections",
        "cashflow",
        "construction",
        "development",
        "consultant",
    ):
        instrument(owner)
    assert pages() == before
    grant_access(admin_client, str(hidden), user)
    changed = admin_client.patch(
        f"/api/v1/projects/{hidden}/access/{user.id}/phase-scope", json={"phase_scope": "selected"}
    )
    assert changed.status_code == 200, changed.text
    assert pages() == before
    client.close()


def test_cashflow_mismatch_removes_both_candidates_and_keeps_coverage(
    project_id: str,
    currency_id: str,
    flat_construction_forecast: str,
    cost_codes: dict[str, str],
    finance_client: TestClient,
    cfo_client: TestClient,
    admin_client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = create_cashflow_forecast(finance_client, project_id)
    assert created.status_code == 201, created.text
    fid = created.json()["id"]
    line = set_cashflow_line(
        finance_client,
        project_id,
        fid,
        period_month=datetime.now(UTC).date().replace(day=1).isoformat(),
        source_kind="development",
        category="consultants",
        amount="20000",
    )
    assert line.status_code == 200, line.text
    governed = govern_cashflow_forecast(
        finance_client, cfo_client, project_id, fid, cost_codes=cost_codes
    )
    assert governed.status_code == 200, governed.text
    expenses = f"/api/v1/projects/{project_id}/pre-launch/expenses"
    expense = finance_client.post(expenses, json=expense_payload(currency_id))
    assert expense.status_code == 201, expense.text
    assert (
        cfo_client.post(
            f"{expenses}/{expense.json()['id']}/confirm",
            json={"expected": editable(expense.json())},
        ).status_code
        == 200
    )
    url = "/api/v1/portfolio/risks?limit=100"
    cash_codes = {"ACTUAL_CASH_DEFICIT", "FORECAST_CASH_DEFICIT"}
    safe = finance_client.get(url).json()
    assert cash_codes <= {row["risk_code"] for row in safe["items"]}
    currency = admin_client.post(
        "/api/v1/settings/currencies", json={"code": "USD", "name": "US dollar"}
    )
    assert currency.status_code == 201, currency.text
    db.get(Project, uuid.UUID(project_id)).base_currency_id = uuid.UUID(currency.json()["id"])
    db.commit()
    captured = []
    original = service._risks

    def evaluate(*args: object, **kwargs: object) -> None:
        original(*args, **kwargs)
        captured.append(args[0])

    monkeypatch.setattr(service, "_risks", evaluate)
    unsafe = finance_client.get(url).json()
    assert not cash_codes & {row["risk_code"] for row in unsafe["items"]}
    assert unsafe["unavailable_project_count"] == 1
    assert all(isinstance(facts, risk_projection.RiskFacts) for facts in captured)
    assert {
        item.risk_code
        for item in captured[0].risk_evaluations
        if item.availability == "unavailable"
    } >= cash_codes
    assert not cash_codes & {row.fields["risk_code"] for row in captured[0].risks}
