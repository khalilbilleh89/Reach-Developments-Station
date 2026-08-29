"""Shared arrangement for the project-domain tests.

Configuration (currency, country pack, reference values) is created through the
Settings API by an administrator, exactly as it would be in production: a
project cannot be created against configuration that does not exist, and these
tests should fail if that stops being true.
"""

from __future__ import annotations

from typing import Any

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


# --------------------------------------------------------------------------- #
# Inventory (PR-MVP-03)
# --------------------------------------------------------------------------- #

#: Reference values the inventory domain validates unit codes against, on top of
#: the ones PR-MVP-02's conftest already seeds.
INVENTORY_REFERENCE_VALUES = (
    ("unit_type", "2BR", "Two bedroom"),
    ("unit_type", "3BR", "Three bedroom"),
    ("floor_band", "MID", "Middle floors"),
    ("orientation", "NORTH", "North facing"),
    ("view_class", "SEA", "Sea view"),
    ("furnishing_specification", "STANDARD", "Standard finish"),
    ("accessibility", "STEP_FREE", "Step free"),
    ("garden_class", "PRIVATE", "Private garden"),
    ("sub_asset_subtype", "COVERED", "Covered bay"),
)


def inventory_url(project_id: str) -> str:
    return f"{PROJECTS}/{project_id}/inventory"


@pytest.fixture
def operational_project(admin_client: TestClient, project_id: str) -> str:
    """A project whose basis has been finalised, so inventory may begin.

    Inventory is refused while a project is still in ``setup``, because that is
    exactly the window in which its country pack can still be changed under the
    units already validated against it. The fixture does what an operator does:
    confirm the configuration, then leave setup.
    """
    response = admin_client.patch(f"{PROJECTS}/{project_id}", json={"status": "predevelopment"})
    assert response.status_code == 200, response.text
    return project_id


@pytest.fixture
def inventory_reference_data(
    admin_client: TestClient, country_pack_id: str, operational_project: str
) -> None:
    for category, code, label in INVENTORY_REFERENCE_VALUES:
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


@pytest.fixture
def phase_id(admin_client: TestClient, project_id: str, inventory_reference_data: None) -> str:
    response = admin_client.post(
        f"{inventory_url(project_id)}/phases",
        json={"code": "PHASE-1", "name": "Phase 1", "sequence": 1},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.fixture
def building_id(admin_client: TestClient, project_id: str, phase_id: str) -> str:
    response = admin_client.post(
        f"{inventory_url(project_id)}/buildings",
        json={"phase_id": phase_id, "code": "B1", "name": "Building 1"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.fixture
def floor_id(admin_client: TestClient, project_id: str, building_id: str) -> str:
    response = admin_client.post(
        f"{inventory_url(project_id)}/floors",
        json={"building_id": building_id, "code": "01", "label": "First floor"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def unit_payload(floor_id: str, **overrides: object) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "floor_id": floor_id,
        "unit_number": "101",
        "unit_reference": "B1-101",
        "asset_class": "apartment",
        "unit_type_code": "2BR",
        "bedrooms": 2,
        "bathrooms": 2,
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def unit_id(admin_client: TestClient, project_id: str, floor_id: str) -> str:
    response = admin_client.post(f"{inventory_url(project_id)}/units", json=unit_payload(floor_id))
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.fixture
def area_types(
    admin_client: TestClient, project_id: str, operational_project: str
) -> dict[str, str]:
    """An internal area required for release, and a half-weighted balcony.

    Area types are a project's own inventory configuration, so like every other
    inventory fixture this one needs the project's basis settled first.
    """
    created: dict[str, str] = {}
    for code, label, role, factor, required in (
        ("INTERNAL", "Internal area", "internal", "1.000000", True),
        ("BALCONY", "Balcony", "outdoor", "0.500000", False),
    ):
        response = admin_client.post(
            f"{inventory_url(project_id)}/area-types",
            json={
                "code": code,
                "label": label,
                "area_role": role,
                "weight_factor": factor,
                "required_for_release": required,
            },
        )
        assert response.status_code == 201, response.text
        created[code] = response.json()["id"]
    return created


def approve_areas(
    client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    *,
    internal: str = "100.0000",
    balcony: str | None = "20.0000",
    revision: str = "R0",
) -> str:
    """Record and approve one measured revision, the way the UI would."""
    values = [{"area_type_id": area_types["INTERNAL"], "raw_area": internal}]
    if balcony is not None:
        values.append({"area_type_id": area_types["BALCONY"], "raw_area": balcony})
    created = client.post(
        f"{inventory_url(project_id)}/units/{unit_id}/area-schedules",
        json={"revision_code": revision, "reconciled": True, "values": values},
    )
    assert created.status_code == 201, created.text
    schedule_id = created.json()["id"]
    approved = client.post(
        f"{inventory_url(project_id)}/units/{unit_id}/area-schedules/{schedule_id}/approve"
    )
    assert approved.status_code == 200, approved.text
    return schedule_id


def make_releasable(
    client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    db: Session,
    *,
    release_date: str = "2026-01-01",
) -> None:
    """Satisfy every release gate, including the one no API may set.

    ``pricing_approved`` is written directly because PR-MVP-03 deliberately
    exposes no way to set it: PR-MVP-04 does that when a real approved price
    exists. A test of the final release formula still needs the flag, and using
    the database for it keeps the API honest.
    """
    from sqlalchemy import select

    from app.modules.inventory.models import Unit

    approve_areas(client, project_id, unit_id, area_types)
    response = client.patch(
        f"{inventory_url(project_id)}/units/{unit_id}/release-controls",
        json={
            "drawings_approved": True,
            "legal_sale_eligible": True,
            "release_date": release_date,
        },
    )
    assert response.status_code == 200, response.text
    unit = db.scalars(select(Unit).where(Unit.id == unit_id)).one()
    unit.pricing_approved = True
    db.commit()


@pytest.fixture
def engineer_member(db: Session, admin_client: TestClient, project_id: str) -> User:
    """A Design / Engineering user who is a member of the project."""
    user = make_user(db, email="design2@example.com", roles=("design_engineering",))
    response = admin_client.put(f"{PROJECTS}/{project_id}/access/{user.id}")
    assert response.status_code == 200, response.text
    return user


# --------------------------------------------------------------------------- #
# Pricing (PR-MVP-04)
# --------------------------------------------------------------------------- #


def pricing_url(project_id: str) -> str:
    return f"{PROJECTS}/{project_id}/pricing"


@pytest.fixture
def finance(db: Session) -> User:
    """Somebody who prepares pricing but may not sanction it."""
    return make_user(db, email="finance@example.com", roles=("finance",))


@pytest.fixture
def finance_client(admin_client: TestClient, project_id: str, finance: User) -> TestClient:
    """Finance, and a member of the project.

    A global role says what somebody may do inside a project; membership says
    which projects exist for them. Pricing needs both, so the fixture grants the
    membership rather than letting every pricing test discover the 404.
    """
    grant_access(admin_client, project_id, finance)
    return client_for(finance.email)


@pytest.fixture
def cfo(db: Session) -> User:
    """The second signature. Deliberately not an administrator."""
    return make_user(db, email="cfo@example.com", roles=("approver_cfo",))


@pytest.fixture
def cfo_client(admin_client: TestClient, project_id: str, cfo: User) -> TestClient:
    grant_access(admin_client, project_id, cfo)
    return client_for(cfo.email)


@pytest.fixture
def advisor_client(admin_client: TestClient, project_id: str, advisor: User) -> TestClient:
    grant_access(admin_client, project_id, advisor)
    return client_for(advisor.email)


@pytest.fixture
def sales_ops(db: Session) -> User:
    return make_user(db, email="salesops@example.com", roles=("sales_operations",))


def configuration_payload(currency_id: str, **overrides: object) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": "Launch pricing",
        "pricing_currency_id": currency_id,
        "base_internal_rate": "1500.00",
        "valid_from": "2026-01-01",
        "maximum_premium_fraction": "0.200000",
        "offer_valid_days": 14,
        "reservation_expiry_days": 7,
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def draft_configuration(
    finance_client: TestClient,
    project_id: str,
    currency_id: str,
    area_types: dict[str, str],
) -> str:
    """A draft policy that prices internal area at 1,500 and balcony at half.

    Built through the API by Finance, exactly as an operator would: a
    configuration nobody could have created through the real routes is not a
    fixture worth testing against.
    """
    created = finance_client.post(
        f"{pricing_url(project_id)}/configurations", json=configuration_payload(currency_id)
    )
    assert created.status_code == 201, created.text
    configuration_id = created.json()["id"]
    for area_type_id, method, extra in (
        (area_types["INTERNAL"], "internal_base", {}),
        (area_types["BALCONY"], "factor_of_internal_rate", {"internal_rate_factor": "0.500000"}),
    ):
        rule = finance_client.post(
            f"{pricing_url(project_id)}/configurations/{configuration_id}/area-rules",
            json={"area_type_id": area_type_id, "pricing_method": method, **extra},
        )
        assert rule.status_code == 201, rule.text
    return configuration_id


@pytest.fixture
def active_configuration(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    draft_configuration: str,
) -> str:
    """The same policy, submitted by Finance and put live by the CFO."""
    base = f"{pricing_url(project_id)}/configurations/{draft_configuration}"
    submitted = finance_client.post(f"{base}/submit", json={"reason": "Launch pricing"})
    assert submitted.status_code == 200, submitted.text
    approved = cfo_client.post(f"{base}/approve", json={"reason": "Reviewed against feasibility"})
    assert approved.status_code == 200, approved.text
    activated = cfo_client.post(f"{base}/activate")
    assert activated.status_code == 200, activated.text
    return draft_configuration


@pytest.fixture
def priced_unit(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    active_configuration: str,
) -> str:
    """A unit with measured areas and a live list price.

    Runs the whole governed path — measure, approve, draft, submit, approve,
    activate — because a price that arrived any other way would not exercise the
    thing every later test depends on.
    """
    approve_areas(admin_client, project_id, unit_id, area_types)
    draft = finance_client.post(
        f"{pricing_url(project_id)}/units/{unit_id}/price-versions", json={}
    )
    assert draft.status_code == 201, draft.text
    version_id = draft.json()["id"]
    base = f"{pricing_url(project_id)}/price-versions/{version_id}"
    assert finance_client.post(f"{base}/submit", json={}).status_code == 200
    approved = cfo_client.post(f"{base}/approve", json={"reason": "Within feasibility"})
    assert approved.status_code == 200, approved.text
    activated = cfo_client.post(f"{base}/activate")
    assert activated.status_code == 200, activated.text
    return version_id
