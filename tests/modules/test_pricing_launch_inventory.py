"""Inventory launch values follow the full authorised selection, not its page."""

import uuid
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import client_for, make_user
from tests.modules.conftest import PROJECTS, approve_areas, inventory_url, pricing_url


def test_launch_values_count_all_rows_exclude_stale_prices_and_refuse_legal(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    legal_client: TestClient,
    advisor_client: TestClient,
    project_id: str,
    unit_id: str,
    floor_id: str,
    area_types: dict[str, str],
    db: Session,
) -> None:
    approve_areas(admin_client, project_id, unit_id, area_types)
    url = f"{inventory_url(project_id)}/launch-values"
    create = finance_client.post(
        f"{pricing_url(project_id)}/units/{unit_id}/price-versions",
        json={"selling_price": "195123.45"},
    )
    assert create.status_code == 201, create.text
    assert create.json()["change_reason"] is None
    base = f"{pricing_url(project_id)}/price-versions/{create.json()['id']}"
    assert finance_client.post(f"{base}/submit", json={}).status_code == 200
    assert cfo_client.post(f"{base}/approve", json={"reason": "Reviewed"}).status_code == 200
    assert cfo_client.post(f"{base}/activate").status_code == 200
    second = admin_client.post(
        f"{inventory_url(project_id)}/units",
        json={
            "floor_id": floor_id,
            "unit_number": "99",
            "unit_reference": "B1-99",
            "asset_class": "apartment",
        },
    )
    assert second.status_code == 201, second.text
    result = advisor_client.get(url, params={"limit": 1, "offset": 1})
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["total"] == 2
    assert data["priced_count"] == 1
    assert data["unpriced_count"] == 1
    assert len(data["rows"]) == 1
    assert Decimal(data["totals"][0]["amount"]) == Decimal("195123.45")
    assert legal_client.get(url).status_code == 403
    empty = advisor_client.get(url, params={"floor_id": str(uuid.uuid4())}).json()
    assert empty["total"] == 0 and empty["totals"] == [] and empty["rows"] == []

    # A selected-phase member without a grant sees neither rows nor their totals.
    reader = make_user(db, email="launch-scope@example.com", roles=("sales_advisor",))
    assert admin_client.put(f"{PROJECTS}/{project_id}/access/{reader.id}").status_code == 200
    scope = admin_client.patch(
        f"{PROJECTS}/{project_id}/access/{reader.id}/phase-scope", json={"phase_scope": "selected"}
    )
    assert scope.status_code == 200, scope.text
    hidden = client_for(reader.email).get(url)
    assert hidden.status_code == 200, hidden.text
    assert hidden.json()["total"] == 0
    assert hidden.json()["totals"] == []

    approve_areas(admin_client, project_id, unit_id, area_types, internal="101", revision="R2")
    stale = advisor_client.get(url).json()
    assert stale["repricing_count"] == 1
    assert stale["priced_count"] == 0
    assert stale["totals"] == []
    assert all(row["price"] is None for row in stale["rows"])
