"""Shared arrangement for the project-domain tests.

Configuration (currency, country pack, reference values) is created through the
Settings API by an administrator, exactly as it would be in production: a
project cannot be created against configuration that does not exist, and these
tests should fail if that stops being true.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.access.models import User
from tests.factories import client_for, make_user

SETTINGS = "/api/v1/settings"
PROJECTS = "/api/v1/projects"

#: Reference values every project-domain test can rely on existing.
REFERENCE_VALUES = (
    ("project_type", "RESIDENTIAL", "Residential"),
    ("ownership_type", "FREEHOLD", "Freehold"),
    ("title_status", "REGISTERED", "Registered"),
    ("zoning_class", "RES_B", "Residential B"),
    ("permit_type", "BUILDING", "Building permit"),
    ("permit_type", "PLANNING", "Planning approval"),
    ("document_type", "TITLE_DEED", "Title deed"),
)


@pytest.fixture
def admin(db: Session) -> User:
    return make_user(db, email="admin@example.com", roles=("system_admin",))


@pytest.fixture
def admin_client(admin: User) -> TestClient:
    return client_for(admin.email)


@pytest.fixture
def manager(db: Session) -> User:
    return make_user(db, email="pm@example.com", roles=("project_manager",))


@pytest.fixture
def manager_client(manager: User) -> TestClient:
    return client_for(manager.email)


@pytest.fixture
def engineer(db: Session) -> User:
    return make_user(db, email="design@example.com", roles=("design_engineering",))


@pytest.fixture
def advisor(db: Session) -> User:
    """A Sales Advisor: has a real role, but no business seeing development cost."""
    return make_user(db, email="advisor@example.com", roles=("sales_advisor",))


@pytest.fixture
def currency_id(admin_client: TestClient) -> str:
    response = admin_client.post(
        f"{SETTINGS}/currencies", json={"code": "JOD", "name": "Jordanian dinar"}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.fixture
def country_pack_id(admin_client: TestClient, currency_id: str) -> str:
    response = admin_client.post(
        f"{SETTINGS}/country-packs",
        json={
            "country_code": "JO",
            "name": "Jordan",
            "locale": "en-JO",
            "timezone": "Asia/Amman",
            "default_currency_id": currency_id,
            "area_unit": "sqm",
            "fiscal_year_start_month": 4,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.fixture
def reference_data(admin_client: TestClient, country_pack_id: str) -> None:
    """Seed the configured codes the project domain validates against."""
    for category, code, label in REFERENCE_VALUES:
        response = admin_client.post(
            f"{SETTINGS}/reference-values",
            json={
                "country_pack_id": country_pack_id,
                "category": category,
                "code": code,
                "label": label,
            },
        )
        assert response.status_code == 201, response.text


def project_payload(
    country_pack_id: str, currency_id: str, **overrides: object
) -> dict[str, object]:
    payload: dict[str, object] = {
        "code": "GALINI-BLU",
        "name": "Galini Blu",
        "developer_entity": "Reach Developments",
        "country_pack_id": country_pack_id,
        "base_currency_id": currency_id,
        "reporting_currency_id": currency_id,
        "city": "Amman",
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def project_id(
    admin_client: TestClient, country_pack_id: str, currency_id: str, reference_data: None
) -> str:
    response = admin_client.post(PROJECTS, json=project_payload(country_pack_id, currency_id))
    assert response.status_code == 201, response.text
    return response.json()["id"]


def parcel_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "plot_number": "PLOT-1",
        "land_area": "4500.0000",
        "ownership_type_code": "FREEHOLD",
        "title_status_code": "REGISTERED",
        "zoning_class_code": "RES_B",
    }
    payload.update(overrides)
    return payload


def permit_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "permit_code": "BLD-001",
        "permit_type_code": "BUILDING",
        "authority": "Greater Amman Municipality",
        "status_effective_date": "2026-01-01",
    }
    payload.update(overrides)
    return payload


def grant_access(admin_client: TestClient, project_id: str, user: User) -> None:
    response = admin_client.put(f"{PROJECTS}/{project_id}/access/{user.id}")
    assert response.status_code == 200, response.text
