"""The physical unit record preserves measurements, scope and approval boundaries."""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.inventory.physical import COMPONENTS, gross_measurement
from tests.factories import client_for, make_user
from tests.modules.conftest import PROJECTS, inventory_url, unit_payload


def test_gross_requires_six_explicit_compatible_measurements() -> None:
    lines = [
        {"physical_component": key, "raw_area": Decimal(value), "unit_of_measure": "sqm"}
        for key, value in zip(COMPONENTS, ("100.1234", "20", "30", "40", "5", "0"), strict=True)
    ]
    assert gross_measurement(lines)["gross_area"] == Decimal("195.1234")
    assert gross_measurement(lines[:-1])["gross_area"] is None
    assert gross_measurement(lines[:-1])["gross_missing_components"] == ["porches"]
    assert gross_measurement([*lines, lines[0]])["gross_area"] is None
    mixed = [*lines[:-1], {**lines[-1], "unit_of_measure": "sqft"}]
    assert gross_measurement(mixed)["gross_area"] is None
    assert gross_measurement([*lines, {"physical_component": None, "raw_area": Decimal("999")}])[
        "gross_area"
    ] == Decimal("195.1234")
    assert gross_measurement([])["gross_area"] is None


def test_approved_gross_excludes_weights_and_attached_assets(
    admin_client: TestClient, project_id: str, unit_id: str, area_types: dict[str, str]
) -> None:
    base = inventory_url(project_id)
    url = f"{base}/units/{unit_id}"
    mapped = admin_client.patch(
        f"{base}/area-types/{area_types['BALCONY']}", json={"physical_component": "balcony"}
    )
    assert mapped.status_code == 200, mapped.text
    types = {"internal": area_types["INTERNAL"], "balcony": area_types["BALCONY"]}
    for key in COMPONENTS[2:]:
        result = admin_client.post(
            f"{base}/area-types",
            json={
                "code": key,
                "label": key,
                "area_role": "outdoor",
                "physical_component": key,
                "weight_factor": "0.250000",
            },
        )
        assert result.status_code == 201, result.text
        types[key] = result.json()["id"]
    values = [
        {"area_type_id": types[key], "raw_area": value}
        for key, value in zip(COMPONENTS, ("100", "20", "30", "40", "5", "0"), strict=True)
    ]
    revision = admin_client.post(
        f"{url}/area-schedules", json={"revision_code": "R1", "values": values, "reconciled": True}
    )
    assert revision.status_code == 201, revision.text
    assert admin_client.get(url).json()["gross_area"] is None
    approved = admin_client.post(f"{url}/area-schedules/{revision.json()['id']}/approve")
    assert approved.status_code == 200, approved.text
    for kind in ("parking", "storage"):
        attached = admin_client.post(
            f"{base}/sub-assets",
            json={
                "asset_reference": kind,
                "asset_type": kind,
                "linked_unit_id": unit_id,
                "transfer_mode": "attached",
                "area": "999",
            },
        )
        assert attached.status_code == 201, attached.text
    record = admin_client.get(url).json()
    assert Decimal(record["gross_area"]) == Decimal("195")
    assert record["gross_area_unit"] == "sqm"
    assert record["gross_missing_components"] == []
    assert Decimal(record["weighted_saleable_area"]) != Decimal(record["gross_area"])
    remap = admin_client.patch(
        f"{base}/area-types/{types['balcony']}", json={"physical_component": "terrace"}
    )
    assert remap.status_code == 409
    duplicate = admin_client.post(
        f"{base}/area-types",
        json={
            "code": "SECOND",
            "label": "Second balcony",
            "area_role": "outdoor",
            "physical_component": "balcony",
            "weight_factor": "0",
        },
    )
    assert duplicate.status_code == 409


def test_features_and_documents_are_scoped_audited_and_not_release_approvals(
    admin_client: TestClient, project_id: str, unit_id: str, floor_id: str, db: Session
) -> None:
    base = inventory_url(project_id)
    url = f"{base}/units/{unit_id}"
    before = admin_client.get(url).json()
    feature = admin_client.post(f"{url}/features", json={"label": "  Sea-facing study  "})
    assert feature.status_code == 201, feature.text
    assert feature.json()["label"] == "Sea-facing study"
    assert (
        admin_client.post(f"{url}/features", json={"label": "SEA-FACING STUDY"}).status_code == 409
    )
    assert admin_client.post(f"{url}/features", json={"label": "  "}).status_code == 422
    for unsafe in ("javascript:alert(1)", "file:///etc/passwd", "data:text/html,hello"):
        assert (
            admin_client.post(f"{url}/documents", json={"title": "Plan", "url": unsafe}).status_code
            == 422
        )
    document = admin_client.post(
        f"{url}/documents",
        json={"title": "Plan", "url": "https://example.com/unit-plan.pdf", "revision": "A"},
    )
    assert document.status_code == 201, document.text
    other = admin_client.post(
        f"{base}/units", json=unit_payload(floor_id, unit_number="102", unit_reference="B1-102")
    )
    assert other.status_code == 201, other.text
    other_url = f"{base}/units/{other.json()['id']}"
    assert (
        admin_client.post(f"{other_url}/features/{feature.json()['id']}/retire").status_code == 404
    )
    assert (
        admin_client.post(f"{other_url}/documents/{document.json()['id']}/retire").status_code
        == 404
    )
    after = admin_client.get(url).json()
    for field in (
        "completeness_percent",
        "drawings_approved",
        "legal_sale_eligible",
        "pricing_approved",
        "release_eligible",
    ):
        assert after[field] == before[field]
    assert (
        admin_client.post(f"{url}/features/{feature.json()['id']}/retire").json()["is_active"]
        is False
    )
    assert (
        admin_client.post(f"{url}/documents/{document.json()['id']}/retire").json()["is_active"]
        is False
    )
    assert len(admin_client.get(f"{url}/documents").json()) == 1
    actions = (
        db.execute(
            text(
                "SELECT action FROM audit_events "
                "WHERE entity_type IN ('unit_feature', 'unit_document')"
            )
        )
        .scalars()
        .all()
    )
    assert set(actions) == {
        "unit_feature.created",
        "unit_feature.retired",
        "unit_document.created",
        "unit_document.retired",
    }


def test_annotations_honor_reader_and_phase_permissions(
    admin_client: TestClient, project_id: str, unit_id: str, db: Session
) -> None:
    url = f"{inventory_url(project_id)}/units/{unit_id}"
    reader = make_user(db, email="unit-reader@example.com", roles=("sales_advisor",))
    assert admin_client.put(f"{PROJECTS}/{project_id}/access/{reader.id}").status_code == 200
    client = client_for(reader.email)
    for path, payload in (
        ("features", {"label": "Sea view"}),
        ("documents", {"title": "Plan", "url": "https://example.com/plan"}),
    ):
        assert client.get(f"{url}/{path}").status_code == 200
        assert client.post(f"{url}/{path}", json=payload).status_code == 403
    writer = make_user(db, email="unit-restricted@example.com", roles=("design_engineering",))
    assert admin_client.put(f"{PROJECTS}/{project_id}/access/{writer.id}").status_code == 200
    assert (
        admin_client.patch(
            f"{PROJECTS}/{project_id}/access/{writer.id}/phase-scope",
            json={"phase_scope": "selected"},
        ).status_code
        == 200
    )
    hidden = client_for(writer.email)
    for path, payload in (
        ("features", {"label": "Sea view"}),
        ("documents", {"title": "Plan", "url": "https://example.com/plan"}),
    ):
        assert hidden.get(f"{url}/{path}").status_code == 404
        assert hidden.post(f"{url}/{path}", json=payload).status_code == 404
