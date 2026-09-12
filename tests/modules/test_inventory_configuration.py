"""Project choice isolation, retirement, assignment and upgrade preservation."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_engine
from tests.modules.conftest import PROJECTS, inventory_url, pricing_url, project_payload


@pytest.mark.parametrize(
    "category,source",
    [
        ("unit_type", "unit_type"),
        ("view_class", "view_class"),
        ("sub_asset_subtype", "parking"),
        ("sub_asset_subtype", "storage"),
    ],
)
def test_choice_referenced_by_pricing_cannot_be_deleted(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    draft_configuration: str,
    category: str,
    source: str,
) -> None:
    url = f"{inventory_url(project_id)}/configuration"
    option = admin_client.post(
        url, json={"category": category, "code": "PRICED", "label": "Priced"}
    )
    assert option.status_code == 201, option.text
    rule = finance_client.post(
        f"{pricing_url(project_id)}/configurations/{draft_configuration}/premium-rules",
        json={
            "code": "PREM",
            "label": "Premium",
            "method": "fixed",
            "amount": "500",
            "source_kind": source,
            "match_code": "PRICED",
        },
    )
    assert rule.status_code == 201, rule.text
    deleted = admin_client.delete(f"{url}/{option.json()['id']}", params={"reason": "Remove"})
    assert deleted.status_code == 409, deleted.text
    assert any(row["id"] == option.json()["id"] for row in admin_client.get(url).json())


def test_subtype_used_by_asset_cannot_be_deleted(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
) -> None:
    url = f"{inventory_url(project_id)}/configuration"
    option = admin_client.post(
        url,
        json={
            "category": "sub_asset_subtype",
            "code": "SPECIAL",
            "label": "Special parking",
        },
    )
    assert option.status_code == 201, option.text
    asset = admin_client.post(
        f"{inventory_url(project_id)}/sub-assets",
        json={
            "asset_reference": "P-SPECIAL",
            "asset_type": "parking",
            "subtype_code": "SPECIAL",
            "linked_unit_id": unit_id,
        },
    )
    assert asset.status_code == 201, asset.text
    deleted = admin_client.delete(f"{url}/{option.json()['id']}", params={"reason": "Remove"})
    assert deleted.status_code == 409, deleted.text


@pytest.mark.parametrize(
    "category",
    [
        "unit_type",
        "view_class",
        "orientation",
        "floor_band",
        "furnishing_specification",
        "accessibility",
        "garden_class",
        "sub_asset_subtype",
    ],
)
def test_delete_unused_choice_is_scoped_authorized_and_audited(
    admin_client: TestClient,
    advisor_client: TestClient,
    project_id: str,
    country_pack_id: str,
    currency_id: str,
    db: Session,
    category: str,
) -> None:
    url = f"{inventory_url(project_id)}/configuration"
    payload = {"category": category, "code": "DELETE-ME", "label": "Delete me"}
    response = admin_client.post(url, json=payload)
    assert response.status_code == 201, response.text
    identifier = response.json()["id"]
    endpoint = f"{url}/{identifier}"
    assert advisor_client.delete(endpoint, params={"reason": "Mistake"}).status_code == 403
    assert admin_client.delete(endpoint, params={"reason": " "}).status_code == 422
    other = admin_client.post(
        PROJECTS,
        json=project_payload(country_pack_id, currency_id, code="OTHER", name="Other"),
    ).json()["id"]
    assert (
        admin_client.delete(
            f"{inventory_url(other)}/configuration/{identifier}", params={"reason": "Mistake"}
        ).status_code
        == 404
    )
    assert admin_client.delete(endpoint, params={"reason": "Entered in error"}).status_code == 204
    assert all(row["id"] != identifier for row in admin_client.get(url).json())
    assert admin_client.delete(endpoint, params={"reason": "Again"}).status_code == 404
    assert (
        db.scalar(
            text(
                "SELECT count(*) FROM audit_events WHERE action='inventory_option.deleted' "
                "AND entity_id=:id AND reason='Entered in error'"
            ),
            {"id": identifier},
        )
        == 1
    )
    assert admin_client.post(url, json=payload).status_code == 201


@pytest.mark.parametrize(
    "category",
    [
        "unit_type",
        "view_class",
        "orientation",
        "floor_band",
        "furnishing_specification",
        "accessibility",
        "garden_class",
    ],
)
def test_delete_choice_preserves_unit_references(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    category: str,
) -> None:
    url = f"{inventory_url(project_id)}/configuration"
    created = admin_client.post(url, json={"category": category, "code": "USED", "label": "Used"})
    assert created.status_code == 201, created.text
    identifier = created.json()["id"]
    unit_url = f"{inventory_url(project_id)}/units/{unit_id}"
    field = f"{category}_code"
    assert admin_client.patch(unit_url, json={field: "USED"}).status_code == 200
    deleted = admin_client.delete(f"{url}/{identifier}", params={"reason": "Wrong choice"})
    assert deleted.status_code == 409, deleted.text
    assert admin_client.get(unit_url).json()[field] == "USED"
    assert any(row["id"] == identifier for row in admin_client.get(url).json())
    assert admin_client.patch(unit_url, json={field: None}).status_code == 200
    assert (
        admin_client.delete(f"{url}/{identifier}", params={"reason": "Unused now"}).status_code
        == 204
    )


def test_project_choices_are_isolated_and_retirement_preserves_units(
    admin_client: TestClient,
    advisor_client: TestClient,
    project_id: str,
    country_pack_id: str,
    currency_id: str,
    unit_id: str,
) -> None:
    url = f"{inventory_url(project_id)}/configuration"
    created = admin_client.post(
        url, json={"category": "view_class", "code": "POOL", "label": "Pool view"}
    )
    assert created.status_code == 201, created.text
    option = created.json()
    assert (
        advisor_client.post(
            url, json={"category": "view_class", "code": "BAD", "label": "Bad"}
        ).status_code
        == 403
    )
    assert (
        admin_client.post(
            url, json={"category": "view_class", "code": "POOL", "label": "Duplicate"}
        ).status_code
        == 409
    )
    assert (
        admin_client.post(
            url, json={"category": "view_class", "code": " ", "label": "Blank"}
        ).status_code
        == 422
    )
    other = admin_client.post(
        PROJECTS,
        json=project_payload(country_pack_id, currency_id, code="OTHER", name="Other project"),
    ).json()["id"]
    other_url = f"{inventory_url(other)}/configuration"
    assert admin_client.get(other_url).json() == []
    assert (
        admin_client.patch(
            f"{other_url}/{option['id']}", json={"label": "Wrong project"}
        ).status_code
        == 404
    )
    second = admin_client.post(
        other_url, json={"category": "view_class", "code": "POOL", "label": "Courtyard pool"}
    )
    assert second.status_code == 201, second.text
    unit_url = f"{inventory_url(project_id)}/units/{unit_id}"
    assert admin_client.patch(unit_url, json={"view_class_code": "POOL"}).status_code == 200
    assert (
        admin_client.patch(
            f"{url}/{option['id']}", json={"label": "Pool and garden", "is_active": False}
        ).status_code
        == 200
    )
    assert admin_client.get(other_url).json()[0]["label"] == "Courtyard pool"
    assert (
        admin_client.patch(unit_url, json={"bedrooms": 4, "view_class_code": "POOL"}).status_code
        == 200
    )
    assert admin_client.get(unit_url).json()["view_class_code"] == "POOL"
    assert admin_client.patch(unit_url, json={"view_class_code": None}).status_code == 200
    assert admin_client.patch(unit_url, json={"view_class_code": "POOL"}).status_code == 422
    assert admin_client.patch(f"{url}/{option['id']}", json={"code": "NEW"}).status_code == 422
    assert admin_client.patch(f"{url}/{option['id']}", json={"is_active": None}).status_code == 422


def test_another_projects_choice_cannot_be_assigned(
    admin_client: TestClient,
    project_id: str,
    country_pack_id: str,
    currency_id: str,
    unit_id: str,
) -> None:
    other = admin_client.post(
        PROJECTS,
        json=project_payload(country_pack_id, currency_id, code="OTHER", name="Other project"),
    ).json()["id"]
    response = admin_client.post(
        f"{inventory_url(other)}/configuration",
        json={"category": "orientation", "code": "COURTYARD", "label": "Courtyard facing"},
    )
    assert response.status_code == 201, response.text
    result = admin_client.patch(
        f"{inventory_url(project_id)}/units/{unit_id}", json={"orientation_code": "COURTYARD"}
    )
    assert result.status_code == 422, result.text


def test_migration_snapshots_choices_without_changing_units(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    db: Session,
) -> None:
    db.rollback()
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    try:
        command.downgrade(config, "0022_land_analytics")
        command.upgrade(config, "head")
        with get_engine().connect() as connection:
            assert (
                connection.scalar(
                    text(
                        "SELECT count(*) FROM inventory_options "
                        "WHERE category='unit_type' AND code='2BR'"
                    )
                )
                == 1
            )
            assert (
                connection.scalar(
                    text("SELECT unit_type_code FROM units WHERE id=:id"), {"id": unit_id}
                )
                == "2BR"
            )
        options = admin_client.get(f"{inventory_url(project_id)}/configuration").json()
        assert next(row for row in options if row["code"] == "SEA")["label"] == "Sea view"
        command.downgrade(config, "0022_land_analytics")
        with get_engine().connect() as connection:
            assert (
                connection.scalar(
                    text("SELECT unit_type_code FROM units WHERE id=:id"), {"id": unit_id}
                )
                == "2BR"
            )
    finally:
        command.upgrade(config, "head")
