"""Inventory deletion keeps dependent measurements, pricing and released stock intact."""

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.modules.conftest import approve_areas, inventory_url


def test_area_type_delete_is_authorized_and_protects_measurements(
    admin_client: TestClient,
    advisor_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    db: Session,
) -> None:
    base = inventory_url(project_id)
    spare = admin_client.post(
        f"{base}/area-types",
        json={
            "code": "SPARE",
            "label": "Spare area",
            "area_role": "other",
            "weight_factor": "1",
        },
    )
    assert spare.status_code == 201, spare.text
    identifier = spare.json()["id"]
    url = f"{base}/area-types/{identifier}"
    assert advisor_client.delete(url, params={"reason": "Unused"}).status_code == 403
    assert admin_client.delete(url, params={"reason": "Unused"}).status_code == 204
    assert all(row["id"] != identifier for row in admin_client.get(f"{base}/area-types").json())
    approve_areas(admin_client, project_id, unit_id, area_types)
    blocked = admin_client.delete(
        f"{base}/area-types/{area_types['INTERNAL']}", params={"reason": "Used"}
    )
    assert blocked.status_code == 409, blocked.text
    assert (
        db.scalar(text("SELECT count(*) FROM audit_events WHERE action='area_type.deleted'")) == 1
    )


def test_draft_measurement_can_be_deleted_but_approved_revision_is_retained(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
) -> None:
    base = inventory_url(project_id)
    url = f"{base}/units/{unit_id}/area-schedules"
    created = admin_client.post(
        url,
        json={
            "revision_code": "MISTAKE",
            "values": [
                {"area_type_id": area_types["INTERNAL"], "raw_area": "100"},
            ],
        },
    )
    assert created.status_code == 201, created.text
    identifier = created.json()["id"]
    assert (
        admin_client.delete(
            f"{base}/area-schedules/{identifier}", params={"reason": "Bad measurement"}
        ).status_code
        == 204
    )
    assert admin_client.get(url).json() == []
    approved = approve_areas(admin_client, project_id, unit_id, area_types)
    assert (
        admin_client.delete(
            f"{base}/area-schedules/{approved}", params={"reason": "Remove"}
        ).status_code
        == 409
    )
    assert admin_client.get(url).json()[0]["id"] == approved


def test_removing_draft_unit_asset_updates_counts_and_protects_released_unit(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    db: Session,
) -> None:
    base = inventory_url(project_id)

    def create_asset(reference: str) -> str:
        created = admin_client.post(
            f"{base}/sub-assets",
            json={
                "asset_reference": reference,
                "asset_type": "parking",
                "linked_unit_id": unit_id,
            },
        )
        assert created.status_code == 201, created.text
        return created.json()["id"]

    identifier = create_asset("P-DELETE")
    assert admin_client.get(f"{base}/units/{unit_id}").json()["parking_count"] == 1
    assert (
        admin_client.delete(
            f"{base}/sub-assets/{identifier}", params={"reason": "Duplicate entry"}
        ).status_code
        == 204
    )
    assert admin_client.get(f"{base}/units/{unit_id}").json()["parking_count"] == 0
    identifier = create_asset("P-KEEP")
    db.execute(text("UPDATE units SET commercial_status='available' WHERE id=:id"), {"id": unit_id})
    db.commit()
    assert (
        admin_client.delete(
            f"{base}/sub-assets/{identifier}", params={"reason": "Remove"}
        ).status_code
        == 409
    )
    assert admin_client.get(f"{base}/units/{unit_id}").json()["parking_count"] == 1
