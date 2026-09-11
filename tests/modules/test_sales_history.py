"""Search and history cross page boundaries without widening transaction access."""

import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.inventory.models import Unit
from app.modules.sales.models import Client, Reservation, SaleContract
from tests.factories import client_for, make_user
from tests.modules.conftest import PROJECTS, grant_access, sales_url


def test_current_search_matches_the_displayed_reservation_not_an_older_attempt(
    db: Session, sales_ops_client: TestClient, project_id: str, reservation_id: str
) -> None:
    original = db.get(Reservation, uuid.UUID(reservation_id))
    template = {
        column.name: getattr(original, column.name) for column in Reservation.__table__.columns
    }
    newest = Reservation(
        **{
            **template,
            "id": uuid.uuid4(),
            "reservation_number": "NEWEST-ATTEMPT",
            "created_at": datetime(2099, 1, 1, tzinfo=UTC),
        }
    )
    db.add(newest)
    db.commit()
    base = sales_url(project_id)
    result = sales_ops_client.get(f"{base}/register", params={"search": "NEWEST-ATTEMPT"}).json()
    assert result["total"] == 1
    assert result["rows"][0]["reservation_id"] == str(newest.id)
    assert (
        sales_ops_client.get(
            f"{base}/register", params={"search": original.reservation_number}
        ).json()["total"]
        == 0
    )
    assert (
        sales_ops_client.get(
            f"{base}/history", params={"search": original.reservation_number}
        ).json()["total"]
        == 1
    )
    newest.status = "expired"
    db.commit()
    assert (
        sales_ops_client.get(f"{base}/register", params={"search": "NEWEST-ATTEMPT"}).json()[
            "total"
        ]
        == 0
    )
    assert (
        sales_ops_client.get(f"{base}/history", params={"search": "NEWEST-ATTEMPT"}).json()["total"]
        == 1
    )


def test_current_search_finds_unit_201_and_scopes_financial_totals(
    db: Session, sales_ops_client: TestClient, project_id: str, active_sale: str
) -> None:
    sale = db.get(SaleContract, uuid.UUID(active_sale))
    unit = db.get(Unit, sale.unit_id)
    buyer = db.get(Client, sale.client_id)
    unit.unit_reference = "ZZ-last-unit"
    buyer.display_name = "Beyond Page Buyer"
    sale.spa_number = "SPA-201-EXACT"
    template = {column.name: getattr(unit, column.name) for column in Unit.__table__.columns}
    for index in range(201):
        db.add(
            Unit(
                **{
                    **template,
                    "id": uuid.uuid4(),
                    "unit_reference": f"AA-{index:03}",
                    "unit_number": f"extra-{index}",
                    "commercial_status": "unreleased",
                }
            )
        )
    db.commit()
    base = f"{sales_url(project_id)}/register"
    first = sales_ops_client.get(base, params={"limit": 200}).json()
    assert first["total"] == 202
    assert all(row["sale_id"] != active_sale for row in first["rows"])
    for term in ("ZZ-last-unit", "beyond page buyer", "SPA-201-EXACT", sale.sale_number):
        response = sales_ops_client.get(base, params={"search": term, "limit": 200})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["total"] == result["totals"]["units"] == 1
        assert result["rows"][0]["sale_id"] == active_sale
        assert result["totals"]["active_contracts"] == 1
    assert sales_ops_client.get(base, params={"search": "%"}).json()["total"] == 0
    empty = sales_ops_client.get(base, params={"search": "missing"}).json()
    assert empty["totals"]["active_contracts"] == 0
    assert empty["totals"]["contracted_value"] == "0.00"


def test_history_keeps_older_reservations_and_cancelled_sales_on_inactive_units(
    db: Session, sales_ops_client: TestClient, project_id: str, active_sale: str
) -> None:
    sale = db.get(SaleContract, uuid.UUID(active_sale))
    reservation = db.get(Reservation, sale.reservation_id)
    template = {
        column.name: getattr(reservation, column.name) for column in Reservation.__table__.columns
    }
    for index in range(105):
        db.add(
            Reservation(
                **{
                    **template,
                    "id": uuid.uuid4(),
                    "reservation_number": f"OLD-{index:03}",
                    "status": "expired",
                    "created_at": datetime(2025, 1, 10, tzinfo=UTC),
                }
            )
        )
    # Fixture a closed historical lifecycle; these readers must not reactivate it.
    sale.status = "cancelled"
    db.get(Unit, sale.unit_id).is_active = False
    db.commit()
    base = f"{sales_url(project_id)}/history"
    page1 = sales_ops_client.get(base, params={"limit": 100}).json()
    page2 = sales_ops_client.get(base, params={"limit": 100, "offset": 100}).json()
    assert page1["total"] == page2["total"] == 107
    assert len(page1["items"]) == 100 and len(page2["items"]) == 7
    assert not ({row["id"] for row in page1["items"]} & {row["id"] for row in page2["items"]})
    closed = sales_ops_client.get(base, params={"kind": "sale", "status": "cancelled"}).json()
    assert closed["total"] == 1 and closed["items"][0]["id"] == active_sale
    old = sales_ops_client.get(
        base, params={"search": "OLD-104", "created_from": "2025-01-10", "created_to": "2025-01-10"}
    ).json()
    assert old["total"] == 1
    assert old["items"][0]["status"] == "expired"
    assert sales_ops_client.get(base, params={"created_to": "2025-01-09"}).json()["total"] == 0
    assert sales_ops_client.get(base, params={"status": "converted"}).json()["total"] == 1
    assert sales_ops_client.get(f"{sales_url(project_id)}/register").json()["total"] == 0
    assert (
        sales_ops_client.get(f"{sales_url(project_id)}/contracts/{active_sale}").status_code == 200
    )


def test_search_and_history_preserve_phase_and_buyer_scope(
    db: Session,
    admin_client: TestClient,
    sales_ops_client: TestClient,
    advisor_client: TestClient,
    project_id: str,
    active_sale: str,
) -> None:
    sale = db.get(SaleContract, uuid.UUID(active_sale))
    buyer = db.get(Client, sale.client_id)
    buyer.display_name = "Private Other Buyer"
    buyer.owner_advisor_user_id = None
    sale.spa_number = "PRIVATE-SPA"
    db.commit()
    base = sales_url(project_id)
    assert advisor_client.get(f"{base}/history").json()["total"] == 0
    for term in ("Private Other Buyer", "PRIVATE-SPA", sale.sale_number):
        assert advisor_client.get(f"{base}/register", params={"search": term}).json()["total"] == 0
        assert (
            sales_ops_client.get(f"{base}/register", params={"search": term}).json()["total"] == 1
        )
    general = advisor_client.get(f"{base}/register").json()
    assert general["rows"][0]["client_display_name"] is None
    hidden = make_user(db, email="history-hidden@example.com", roles=("sales_operations",))
    grant_access(admin_client, project_id, hidden)
    assert (
        admin_client.patch(
            f"{PROJECTS}/{project_id}/access/{hidden.id}/phase-scope",
            json={"phase_scope": "selected"},
        ).status_code
        == 200
    )
    with client_for(hidden.email) as restricted:
        for route in ("register", "history"):
            result = restricted.get(f"{base}/{route}", params={"search": "PRIVATE-SPA"})
            assert result.status_code == 200, result.text
            assert result.json()["total"] == 0
