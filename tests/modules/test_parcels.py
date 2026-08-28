"""The land register: factual parcel data, with development cost held back."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.access.models import User
from app.modules.audit.models import AuditEvent
from app.modules.projects.models import LandParcel
from tests.factories import client_for
from tests.modules.conftest import (
    PROJECTS,
    SETTINGS,
    grant_access,
    parcel_payload,
    project_payload,
)


def test_a_parcel_records_the_legal_and_physical_facts(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    """Given a parcel, then it stores what the title and the survey say."""
    response = admin_client.post(
        f"{PROJECTS}/{project_id}/parcels",
        json=parcel_payload(
            title_deed_number="TD-9911",
            purchase_price="987654.32",
            acquisition_fees="12345.67",
            power_available=True,
            sewer_available=False,
            utility_notes="Sewer connection pending municipal works.",
        ),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["plot_number"] == "PLOT-1"
    # Defaulted from the country pack rather than guessed.
    assert body["area_unit"] == "sqm"
    assert body["power_available"] is True
    assert body["sewer_available"] is False
    stored = db.scalars(select(LandParcel)).one()
    assert stored.purchase_price == Decimal("987654.32")
    assert isinstance(stored.purchase_price, Decimal)


def test_an_unknown_utility_state_stays_unknown(admin_client: TestClient, project_id: str) -> None:
    """Given no survey yet, then a utility flag is null rather than a false 'no'."""
    response = admin_client.post(f"{PROJECTS}/{project_id}/parcels", json=parcel_payload())

    assert response.status_code == 201
    assert response.json()["water_available"] is None


def test_a_duplicate_plot_number_conflicts_within_a_project(
    admin_client: TestClient, project_id: str
) -> None:
    """Given the plot number is taken, then a second parcel is refused."""
    admin_client.post(f"{PROJECTS}/{project_id}/parcels", json=parcel_payload())

    response = admin_client.post(f"{PROJECTS}/{project_id}/parcels", json=parcel_payload())

    assert response.status_code == 409
    assert "plot number" in response.json()["detail"]


def test_the_same_plot_number_is_free_in_another_project(
    admin_client: TestClient, project_id: str, country_pack_id: str, currency_id: str
) -> None:
    """Given plot numbers come from different authorities, then they collide only per project."""
    admin_client.post(f"{PROJECTS}/{project_id}/parcels", json=parcel_payload())
    other = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="OTHER")
    ).json()["id"]

    response = admin_client.post(f"{PROJECTS}/{other}/parcels", json=parcel_payload())

    assert response.status_code == 201


@pytest.mark.parametrize("area", ["0", "-1.0000"])
def test_a_parcel_must_have_a_positive_area(
    admin_client: TestClient, project_id: str, area: str
) -> None:
    """Given no land, then there is no parcel to register."""
    response = admin_client.post(
        f"{PROJECTS}/{project_id}/parcels", json=parcel_payload(land_area=area)
    )

    assert response.status_code == 422


@pytest.mark.parametrize("share", ["0", "1.500000", "-0.100000"])
def test_an_ownership_share_outside_its_bounds_is_rejected(
    admin_client: TestClient, project_id: str, share: str
) -> None:
    """Given a share that is not a fraction of one, then it is refused."""
    response = admin_client.post(
        f"{PROJECTS}/{project_id}/parcels",
        json=parcel_payload(ownership_share_fraction=share),
    )

    assert response.status_code == 422


def test_a_half_share_round_trips_as_an_exact_fraction(
    admin_client: TestClient, project_id: str
) -> None:
    """Given a half share, then it is carried as an explicit fraction string."""
    response = admin_client.post(
        f"{PROJECTS}/{project_id}/parcels",
        json=parcel_payload(ownership_share_fraction="0.500000"),
    )

    assert response.status_code == 201
    assert response.json()["ownership_share_fraction"] == "0.500000"


@pytest.mark.parametrize("field", ["purchase_price", "acquisition_fees"])
def test_negative_acquisition_money_is_rejected(
    admin_client: TestClient, project_id: str, field: str
) -> None:
    """Given a negative cost, then it is refused rather than stored."""
    response = admin_client.post(
        f"{PROJECTS}/{project_id}/parcels", json=parcel_payload(**{field: "-1.00"})
    )

    assert response.status_code == 422


def test_an_unconfigured_land_code_is_rejected(admin_client: TestClient, project_id: str) -> None:
    """Given a title status nobody configured, then the parcel is refused.

    Jurisdictional legal categories belong to country configuration, not to a
    list hardcoded in Python.
    """
    response = admin_client.post(
        f"{PROJECTS}/{project_id}/parcels", json=parcel_payload(title_status_code="MADE_UP")
    )

    assert response.status_code == 422
    assert "title_status" in response.json()["detail"]


def test_a_retired_land_code_stays_on_existing_parcels(
    admin_client: TestClient, project_id: str, country_pack_id: str
) -> None:
    """Given the code is retired later, then history keeps it and reads fine."""
    created = admin_client.post(f"{PROJECTS}/{project_id}/parcels", json=parcel_payload()).json()
    values = admin_client.get(f"{SETTINGS}/reference-values?category=title_status").json()
    retired = next(value for value in values if value["code"] == "REGISTERED")
    admin_client.patch(f"{SETTINGS}/reference-values/{retired['id']}", json={"is_active": False})

    read = admin_client.get(f"{PROJECTS}/{project_id}/parcels/{created['id']}")

    assert read.status_code == 200
    assert read.json()["title_status_code"] == "REGISTERED"


def test_the_area_unit_may_be_overridden_where_the_record_uses_the_other(
    admin_client: TestClient, project_id: str
) -> None:
    """Given a title recorded in square feet, then the parcel may say so.

    Stored as the authoritative record states it. Nothing converts.
    """
    response = admin_client.post(
        f"{PROJECTS}/{project_id}/parcels", json=parcel_payload(area_unit="sqft")
    )

    assert response.status_code == 201
    assert response.json()["area_unit"] == "sqft"


def test_a_project_manager_may_maintain_the_land_register(
    admin_client: TestClient, manager: User, project_id: str
) -> None:
    """Given project access and the manager role, then parcels can be written."""
    grant_access(admin_client, project_id, manager)
    client = client_for(manager.email)

    response = client.post(f"{PROJECTS}/{project_id}/parcels", json=parcel_payload())

    assert response.status_code == 201


def test_design_engineering_may_read_but_not_change_land(
    admin_client: TestClient, engineer: User, project_id: str
) -> None:
    """Given an engineer, then the land deal is outside what they maintain."""
    grant_access(admin_client, project_id, engineer)
    admin_client.post(f"{PROJECTS}/{project_id}/parcels", json=parcel_payload())
    client = client_for(engineer.email)

    assert client.get(f"{PROJECTS}/{project_id}/parcels").status_code == 200
    assert (
        client.post(
            f"{PROJECTS}/{project_id}/parcels", json=parcel_payload(plot_number="PLOT-2")
        ).status_code
        == 403
    )


def test_a_parcel_from_another_project_cannot_be_read_through_this_one(
    admin_client: TestClient, project_id: str, country_pack_id: str, currency_id: str
) -> None:
    """Given a foreign parcel identifier, then the project scoping refuses it."""
    other = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="OTHER")
    ).json()["id"]
    foreign = admin_client.post(f"{PROJECTS}/{other}/parcels", json=parcel_payload()).json()["id"]

    response = admin_client.get(f"{PROJECTS}/{project_id}/parcels/{foreign}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Land parcel not found."}


def test_an_unknown_parcel_is_not_found(admin_client: TestClient, project_id: str) -> None:
    response = admin_client.get(f"{PROJECTS}/{project_id}/parcels/{uuid.uuid4()}")

    assert response.status_code == 404


def test_a_parcel_is_retired_rather_than_deleted(admin_client: TestClient, project_id: str) -> None:
    """Given a parcel leaves the deal, then it is deactivated and still listed."""
    created = admin_client.post(f"{PROJECTS}/{project_id}/parcels", json=parcel_payload()).json()

    deleted = admin_client.delete(f"{PROJECTS}/{project_id}/parcels/{created['id']}")
    deactivated = admin_client.patch(
        f"{PROJECTS}/{project_id}/parcels/{created['id']}", json={"is_active": False}
    )

    assert deleted.status_code == 404
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False
    assert len(admin_client.get(f"{PROJECTS}/{project_id}/parcels").json()) == 1


def test_parcel_changes_are_audited(admin_client: TestClient, project_id: str, db: Session) -> None:
    """Given a create and an update, then both carry actor and before/after."""
    created = admin_client.post(
        f"{PROJECTS}/{project_id}/parcels", json=parcel_payload(seller="Original Owner")
    ).json()
    admin_client.patch(
        f"{PROJECTS}/{project_id}/parcels/{created['id']}", json={"seller": "Corrected Owner"}
    )

    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.action.like("land_parcel.%"))
        .order_by(AuditEvent.occurred_at)
    ).all()

    assert [event.action for event in events] == ["land_parcel.created", "land_parcel.updated"]
    assert events[1].before_data["seller"] == "Original Owner"
    assert events[1].after_data["seller"] == "Corrected Owner"
