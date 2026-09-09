"""Unknown coverage must never become a zero-valued financial observation."""

from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import client_for, make_user
from tests.modules.conftest import create_cashflow_forecast, govern_cashflow_forecast, grant_access
from tests.modules.test_portfolio_outlook import rows


def test_missing_schedule_is_unavailable_not_zero(
    admin_client: TestClient,
    active_sale: str,
) -> None:
    body = rows(admin_client, "scheduled_collection_due")
    assert body["total"] == 0
    bucket = body["currency_buckets"][0]
    assert bucket["scheduled_outstanding_due"] is None
    assert bucket["availability"] == "unavailable"
    assert bucket["unavailable_project_count"] == 1


def test_short_governed_cash_horizon_is_partial(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    flat_construction_forecast: str,
    cost_codes: dict[str, str],
) -> None:
    month = datetime.now(UTC).date().replace(day=1)
    created = create_cashflow_forecast(
        finance_client,
        project_id,
        forecast_end_month=str(month),
        opening_unrestricted_cash="1250.00",
    )
    assert created.status_code == 201, created.text
    governed = govern_cashflow_forecast(
        finance_client,
        cfo_client,
        project_id,
        created.json()["id"],
        cost_codes=cost_codes,
    )
    assert governed.status_code == 200, governed.text
    item = rows(admin_client, "cashflow_forecast", 90)["items"][0]
    assert item["availability"] == "partial"
    assert "ends before" in item["reason"]
    assert Decimal(item["amount"]) == Decimal("1250")


def test_inactive_and_phase_only_assignees_are_rejected(
    admin_client: TestClient,
    project_id: str,
    db: Session,
) -> None:
    user = make_user(db, email="assignee-coverage@example.com", roles=("finance",))
    grant_access(admin_client, project_id, user)
    payload = {
        "project_id": project_id,
        "title": "Validate ownership",
        "owner_user_id": str(user.id),
        "due_date": str(datetime.now(UTC).date()),
    }
    user.is_active = False
    db.commit()
    assert admin_client.post("/api/v1/portfolio/actions", json=payload).status_code == 422
    user.is_active = True
    db.commit()
    changed = admin_client.patch(
        f"/api/v1/projects/{project_id}/access/{user.id}/phase-scope",
        json={"phase_scope": "selected"},
    )
    assert changed.status_code == 200
    assert admin_client.post("/api/v1/portfolio/actions", json=payload).status_code == 422
    choices = admin_client.get(
        "/api/v1/portfolio/actions/assignees", params={"project_id": project_id}
    )
    assert choices.status_code == 200
    assert str(user.id) not in {row["user_id"] for row in choices.json()}


def test_master_administrator_can_own_and_manage_without_project_grant(
    admin_client: TestClient,
    project_id: str,
    db: Session,
) -> None:
    master = make_user(db, email="master-action@example.com", roles=("master_admin",))
    with client_for(master.email) as client:
        choices = client.get(
            "/api/v1/portfolio/actions/assignees", params={"project_id": project_id}
        )
        assert choices.status_code == 200
        assert str(master.id) in {row["user_id"] for row in choices.json()}
        created = client.post(
            "/api/v1/portfolio/actions",
            json={
                "project_id": project_id,
                "title": "Master management commitment",
                "owner_user_id": str(master.id),
                "due_date": str(datetime.now(UTC).date()),
            },
        )
        assert created.status_code == 201, created.text
        aid = created.json()["id"]
        finished = client.post(
            f"/api/v1/portfolio/actions/{aid}/transitions",
            json={
                "expected_version": 1,
                "status": "completed",
            },
        )
        assert finished.status_code == 200, finished.text
        assert client.get(f"/api/v1/portfolio/actions/{aid}/history").json()["total"] == 2
