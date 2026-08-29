"""Parking, storage and other separately identifiable inventory.

One physical thing is one row. There are deliberately no ``parking_1`` and
``parking_2`` columns on a unit: a unit with two bays has two rows, and its
counts are derived from them.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.inventory.models import InventorySubAsset, Unit
from tests.modules.conftest import PROJECTS, inventory_url, project_payload


def _assets(project_id: str) -> str:
    return f"{inventory_url(project_id)}/sub-assets"


def test_a_parking_bay_is_one_row(
    admin_client: TestClient, project_id: str, unit_id: str, floor_id: str
) -> None:
    response = admin_client.post(
        _assets(project_id),
        json={
            "asset_reference": "P-101-A",
            "asset_type": "parking",
            "subtype_code": "COVERED",
            "linked_unit_id": unit_id,
            "floor_id": floor_id,
            "area": "12.5000",
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["asset_type"] == "parking"
    assert body["area"] == "12.5000"
    assert body["transfer_mode"] == "attached"


def test_two_bays_are_two_rows_and_a_count_of_two(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    """Given a unit with two bays, then the count is derived, never stored."""
    for reference in ("P-101-A", "P-101-B"):
        admin_client.post(
            _assets(project_id),
            json={
                "asset_reference": reference,
                "asset_type": "parking",
                "linked_unit_id": unit_id,
            },
        )
    admin_client.post(
        _assets(project_id),
        json={"asset_reference": "S-101", "asset_type": "storage", "linked_unit_id": unit_id},
    )

    body = admin_client.get(f"{inventory_url(project_id)}/units/{unit_id}").json()

    assert body["parking_count"] == 2
    assert body["storage_count"] == 1


def test_a_deactivated_asset_stops_counting(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    asset = admin_client.post(
        _assets(project_id),
        json={"asset_reference": "P-1", "asset_type": "parking", "linked_unit_id": unit_id},
    ).json()["id"]

    admin_client.patch(f"{_assets(project_id)}/{asset}", json={"is_active": False})

    body = admin_client.get(f"{inventory_url(project_id)}/units/{unit_id}").json()
    assert body["parking_count"] == 0


def test_an_asset_reference_is_unique_within_a_project(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    admin_client.post(_assets(project_id), json={"asset_reference": "P-1", "asset_type": "parking"})

    response = admin_client.post(
        _assets(project_id), json={"asset_reference": "P-1", "asset_type": "storage"}
    )

    assert response.status_code == 409


def test_an_asset_cannot_link_to_another_projects_unit(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    country_pack_id: str,
    currency_id: str,
    inventory_reference_data: None,
) -> None:
    other = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="SECOND")
    ).json()["id"]

    response = admin_client.post(
        _assets(other),
        json={"asset_reference": "P-X", "asset_type": "parking", "linked_unit_id": unit_id},
    )

    assert response.status_code == 404


def test_an_attached_asset_sits_on_its_units_floor(
    admin_client: TestClient, project_id: str, building_id: str, unit_id: str
) -> None:
    """Given a floor that is not the unit's, then the pairing is refused."""
    other_floor = admin_client.post(
        f"{inventory_url(project_id)}/floors",
        json={"building_id": building_id, "code": "02", "label": "Second"},
    ).json()["id"]

    response = admin_client.post(
        _assets(project_id),
        json={
            "asset_reference": "P-2",
            "asset_type": "parking",
            "linked_unit_id": unit_id,
            "floor_id": other_floor,
        },
    )

    assert response.status_code == 422
    assert "that unit's floor" in response.json()["detail"]


def test_an_independent_asset_needs_no_unit(
    admin_client: TestClient, project_id: str, floor_id: str
) -> None:
    response = admin_client.post(
        _assets(project_id),
        json={
            "asset_reference": "P-VISITOR-1",
            "asset_type": "parking",
            "transfer_mode": "independent",
            "floor_id": floor_id,
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["linked_unit_id"] is None


def test_assets_can_be_filtered_by_link_state(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    admin_client.post(
        _assets(project_id),
        json={"asset_reference": "P-1", "asset_type": "parking", "linked_unit_id": unit_id},
    )
    admin_client.post(_assets(project_id), json={"asset_reference": "P-2", "asset_type": "parking"})

    linked = admin_client.get(f"{_assets(project_id)}?linked=true").json()
    unlinked = admin_client.get(f"{_assets(project_id)}?linked=false").json()

    assert [row["asset_reference"] for row in linked] == ["P-1"]
    assert [row["asset_reference"] for row in unlinked] == ["P-2"]


def test_a_sub_asset_carries_no_price_or_sale_state(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    """Given the response, then nothing commercial is in it.

    Whether a parking bay is priced or sold separately is PR-MVP-04 and
    PR-MVP-05's question. Inventory records that the bay exists.
    """
    asset = admin_client.post(
        _assets(project_id),
        json={"asset_reference": "P-1", "asset_type": "parking", "linked_unit_id": unit_id},
    ).json()

    for forbidden in ("price", "amount", "commercial_status", "sold", "reserved"):
        assert forbidden not in asset


def test_a_sub_asset_update_refuses_what_it_does_not_declare(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    asset = admin_client.post(
        _assets(project_id), json={"asset_reference": "P-1", "asset_type": "parking"}
    ).json()["id"]

    for body in ({"price": "1000.00"}, {"asset_type": "storage"}, {"project_id": project_id}):
        response = admin_client.patch(f"{_assets(project_id)}/{asset}", json=body)
        assert response.status_code == 422, body


def test_no_unit_column_repeats_a_parking_slot(db: Session) -> None:
    """Given the unit table, then it has no numbered parking columns.

    The shape this test protects against is ``parking_1``, ``parking_2``,
    ``parking_3`` — the thing the spreadsheet did and the database must not.
    """
    columns = set(Unit.__table__.columns.keys())

    assert not any(name.startswith("parking") for name in columns)
    assert not any(name.startswith("storage") for name in columns)


def test_creating_a_sub_asset_is_audited(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    from app.modules.audit.models import AuditEvent

    admin_client.post(_assets(project_id), json={"asset_reference": "P-1", "asset_type": "parking"})

    assert db.scalars(select(AuditEvent).where(AuditEvent.action == "sub_asset.created")).one()
    assert db.scalars(select(InventorySubAsset)).one().asset_reference == "P-1"
