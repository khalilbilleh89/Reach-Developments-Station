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


class TestClassificationIsTheWordingOnTheRecord:
    """Ownership, title status and zoning are text, not a configured code.

    They were reference codes validated against the project's country pack
    until PR-V2-01, and the dictionary was the wrong shape for the fact: a
    title office writes "Mortgage release pending" and a planning authority
    issues "Residential 4-storey". A register that can only hold the wordings
    somebody configured in advance is one the operator works around, and the
    truth ends up in a notes field.

    Permit type stayed a controlled vocabulary, and the difference is the
    point: a permit's type is filtered and counted, a parcel's zoning is read.
    """

    @pytest.mark.parametrize(
        ("field", "wording"),
        [
            ("ownership_type", "75% acquired \u2014 balance under negotiation"),
            ("title_status", "Mortgage release pending"),
            ("zoning", "Residential / mixed use, 4 storeys"),
        ],
    )
    def test_a_wording_nobody_configured_is_recorded_as_given(
        self, admin_client: TestClient, project_id: str, field: str, wording: str
    ) -> None:
        """Given wording matching no reference value, then it is stored verbatim."""
        response = admin_client.post(
            f"{PROJECTS}/{project_id}/parcels", json=parcel_payload(**{field: wording})
        )

        assert response.status_code == 201, response.text
        assert response.json()[field] == wording

    def test_the_reference_categories_are_not_consulted(
        self, admin_client: TestClient, project_id: str, db: Session
    ) -> None:
        """Given every land reference value is retired, then a parcel still saves.

        The old model would have refused all three fields here. Settings keeps
        the categories so a screen can go on suggesting the usual wordings, but
        a suggestion that can refuse a parcel is not a suggestion.
        """
        for category in ("ownership_type", "title_status", "zoning_class"):
            for value in admin_client.get(
                f"{SETTINGS}/reference-values?category={category}"
            ).json():
                admin_client.patch(
                    f"{SETTINGS}/reference-values/{value['id']}", json={"is_active": False}
                )

        response = admin_client.post(
            f"{PROJECTS}/{project_id}/parcels",
            json=parcel_payload(
                ownership_type="Government allocation",
                title_status="Under consolidation",
                zoning="Special development zone",
            ),
        )

        assert response.status_code == 201, response.text
        stored = db.scalars(select(LandParcel).where(LandParcel.id == response.json()["id"])).one()
        assert stored.zoning == "Special development zone"

    def test_surrounding_whitespace_is_not_part_of_the_classification(
        self, admin_client: TestClient, project_id: str
    ) -> None:
        """Given padded wording, then it is stored trimmed.

        Two parcels typed a day apart would otherwise be "Freehold" and
        "Freehold ", which sort apart and filter apart while reading the same.
        """
        response = admin_client.post(
            f"{PROJECTS}/{project_id}/parcels",
            json=parcel_payload(ownership_type="  Long leasehold  "),
        )

        assert response.status_code == 201, response.text
        assert response.json()["ownership_type"] == "Long leasehold"

    def test_an_empty_box_means_not_yet_established(
        self, admin_client: TestClient, project_id: str
    ) -> None:
        """Given a blank classification, then it is stored as absent.

        A stored ``""`` reads on screen as "not recorded" while sorting,
        filtering and exporting as a recorded value. One of those has to win,
        and it is the one the operator meant.
        """
        response = admin_client.post(
            f"{PROJECTS}/{project_id}/parcels", json=parcel_payload(title_status="   ")
        )

        assert response.status_code == 201, response.text
        assert response.json()["title_status"] is None

    def test_a_classification_can_be_cleared_after_the_fact(
        self, admin_client: TestClient, project_id: str
    ) -> None:
        """Given an explicit null, then the recorded wording goes away."""
        created = admin_client.post(
            f"{PROJECTS}/{project_id}/parcels", json=parcel_payload()
        ).json()

        response = admin_client.patch(
            f"{PROJECTS}/{project_id}/parcels/{created['id']}", json={"zoning": None}
        )

        assert response.status_code == 200, response.text
        assert response.json()["zoning"] is None

    def test_a_description_longer_than_the_column_is_refused(
        self, admin_client: TestClient, project_id: str
    ) -> None:
        """Given 501 characters, then it is refused rather than truncated.

        Flexible is not unbounded: a bounded column is what keeps this a
        classification rather than a second notes field, and silently storing
        the first 500 characters of a planning description is worse than
        saying no.
        """
        response = admin_client.post(
            f"{PROJECTS}/{project_id}/parcels", json=parcel_payload(zoning="z" * 501)
        )

        assert response.status_code == 422

    @pytest.mark.parametrize(
        "field", ["ownership_type_code", "title_status_code", "zoning_class_code"]
    )
    def test_the_retired_code_field_is_refused_rather_than_ignored(
        self, admin_client: TestClient, project_id: str, field: str
    ) -> None:
        """Given the pre-V2 field name, then the request is refused.

        There is one truth per classification and this is what keeps it that
        way. Accepting the old name beside the new one — or ignoring it — is
        how a caller ends up believing it set a value that was dropped.
        """
        response = admin_client.post(
            f"{PROJECTS}/{project_id}/parcels", json=parcel_payload(**{field: "FREEHOLD"})
        )

        assert response.status_code == 422

    def test_the_audit_trail_carries_the_classification_that_changed(
        self, admin_client: TestClient, project_id: str, db: Session
    ) -> None:
        """Given a re-zoning, then before and after both name it."""
        created = admin_client.post(
            f"{PROJECTS}/{project_id}/parcels", json=parcel_payload()
        ).json()

        admin_client.patch(
            f"{PROJECTS}/{project_id}/parcels/{created['id']}",
            json={"zoning": "Residential C, following the 2026 plan"},
        )

        event = db.scalars(
            select(AuditEvent)
            .where(AuditEvent.action == "land_parcel.updated")
            .order_by(AuditEvent.occurred_at.desc())
        ).first()
        assert event is not None
        assert event.before_data["zoning"] == "Residential B"
        assert event.after_data["zoning"] == "Residential C, following the 2026 plan"


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
