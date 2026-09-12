"""Project choice isolation, retirement, assignment and upgrade preservation."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_engine
from tests.modules.conftest import PROJECTS, inventory_url, project_payload


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
