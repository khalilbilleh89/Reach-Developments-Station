"""The integrity rules found in the final pre-merge audit.

Each of these is a way the register could have told two stories at once: a
sub-asset visible to somebody who cannot open its phase, a status history whose
dates run backwards, a stored measurement whose unit was changed underneath it,
a weighted total adding metres to feet, and a count describing a page while
claiming to describe a development.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.access.models import User
from app.modules.inventory.models import AreaType, Unit, UnitStatusEvent
from tests.factories import client_for, make_user
from tests.modules.conftest import PROJECTS, inventory_url, unit_payload

# --------------------------------------------------------------------------- #
# Sub-asset phase security
# --------------------------------------------------------------------------- #


@pytest.fixture
def two_phases(
    admin_client: TestClient, project_id: str, inventory_reference_data: None
) -> dict[str, dict[str, str]]:
    built: dict[str, dict[str, str]] = {}
    for index, code in enumerate(("PHASE-A", "PHASE-B"), start=1):
        phase = admin_client.post(
            f"{inventory_url(project_id)}/phases", json={"code": code, "name": code.title()}
        ).json()["id"]
        building = admin_client.post(
            f"{inventory_url(project_id)}/buildings",
            json={"phase_id": phase, "code": f"B{index}", "name": f"Building {index}"},
        ).json()["id"]
        floor = admin_client.post(
            f"{inventory_url(project_id)}/floors",
            json={"building_id": building, "code": "01", "label": "First"},
        ).json()["id"]
        built[code] = {"phase": phase, "building": building, "floor": floor}
    return built


@pytest.fixture
def restricted(
    db: Session,
    admin_client: TestClient,
    project_id: str,
    two_phases: dict[str, dict[str, str]],
) -> User:
    user = make_user(db, email="asset-restricted@example.com", roles=("design_engineering",))
    admin_client.put(f"{PROJECTS}/{project_id}/access/{user.id}")
    admin_client.patch(
        f"{PROJECTS}/{project_id}/access/{user.id}/phase-scope",
        json={"phase_scope": "selected"},
    )
    admin_client.put(
        f"{PROJECTS}/{project_id}/access/{user.id}/phases/{two_phases['PHASE-A']['phase']}"
    )
    return user


def test_a_floor_only_asset_in_a_hidden_phase_never_reaches_a_narrowed_member(
    admin_client: TestClient,
    project_id: str,
    two_phases: dict[str, dict[str, str]],
    restricted: User,
) -> None:
    """Given a bay on a hidden floor, then it is absent, and 404 when named.

    Visibility used to be decided from the linked unit alone. A parking bay with
    no unit carries a null there, and a null passed the filter — so the one
    sub-asset that says which floor of which phase it sits on was the one nobody
    checked.
    """
    hidden = admin_client.post(
        f"{inventory_url(project_id)}/sub-assets",
        json={
            "asset_reference": "P-HIDDEN",
            "asset_type": "parking",
            "floor_id": two_phases["PHASE-B"]["floor"],
        },
    )
    assert hidden.status_code == 201, hidden.text
    asset_id = hidden.json()["id"]
    client = client_for(restricted.email)

    listing = client.get(f"{inventory_url(project_id)}/sub-assets")
    direct = client.get(f"{inventory_url(project_id)}/sub-assets/{asset_id}")
    update = client.patch(
        f"{inventory_url(project_id)}/sub-assets/{asset_id}", json={"notes": "mine now"}
    )

    assert listing.status_code == 200
    assert "P-HIDDEN" not in listing.text
    assert direct.status_code == 404
    assert update.status_code == 404


def test_an_unattached_asset_is_withheld_from_a_narrowed_member(
    admin_client: TestClient,
    project_id: str,
    two_phases: dict[str, dict[str, str]],
    restricted: User,
) -> None:
    """Given no unit and no floor, then there is no phase to check.

    A member narrowed to particular phases has no claim to something that sits
    in none of them. Refusing is the side that fails safe; a member who sees the
    whole project still sees it.
    """
    admin_client.post(
        f"{inventory_url(project_id)}/sub-assets",
        json={"asset_reference": "P-FLOATING", "asset_type": "parking"},
    )

    narrowed = client_for(restricted.email).get(f"{inventory_url(project_id)}/sub-assets")
    everything = admin_client.get(f"{inventory_url(project_id)}/sub-assets")

    assert "P-FLOATING" not in narrowed.text
    assert "P-FLOATING" in everything.text


def test_a_narrowed_member_sees_an_asset_on_a_floor_they_may_see(
    admin_client: TestClient,
    project_id: str,
    two_phases: dict[str, dict[str, str]],
    restricted: User,
) -> None:
    """The rule narrows; it does not hide the caller's own phase from them."""
    admin_client.post(
        f"{inventory_url(project_id)}/sub-assets",
        json={
            "asset_reference": "P-VISIBLE",
            "asset_type": "parking",
            "floor_id": two_phases["PHASE-A"]["floor"],
        },
    )

    listing = client_for(restricted.email).get(f"{inventory_url(project_id)}/sub-assets")

    assert "P-VISIBLE" in listing.text


def test_a_narrowed_member_cannot_place_an_asset_on_a_hidden_floor(
    admin_client: TestClient,
    project_id: str,
    two_phases: dict[str, dict[str, str]],
    restricted: User,
) -> None:
    """Writing into a hidden phase is the same leak, running outwards."""
    response = client_for(restricted.email).post(
        f"{inventory_url(project_id)}/sub-assets",
        json={
            "asset_reference": "P-SNEAK",
            "asset_type": "parking",
            "floor_id": two_phases["PHASE-B"]["floor"],
        },
    )

    assert response.status_code == 404


def test_a_filter_cannot_widen_what_a_narrowed_member_sees(
    admin_client: TestClient,
    project_id: str,
    two_phases: dict[str, dict[str, str]],
    restricted: User,
) -> None:
    """Naming the hidden floor in a query parameter narrows to nothing."""
    admin_client.post(
        f"{inventory_url(project_id)}/sub-assets",
        json={
            "asset_reference": "P-HIDDEN",
            "asset_type": "parking",
            "floor_id": two_phases["PHASE-B"]["floor"],
        },
    )

    response = client_for(restricted.email).get(
        f"{inventory_url(project_id)}/sub-assets?floor_id={two_phases['PHASE-B']['floor']}"
    )

    assert response.status_code == 200
    assert response.json() == []


# --------------------------------------------------------------------------- #
# Commercial history runs forwards
# --------------------------------------------------------------------------- #


def _transition(
    client: TestClient,
    project_id: str,
    unit_id: str,
    to_status: str,
    effective: str,
    **extra: str,
) -> Response:
    return client.post(
        f"{inventory_url(project_id)}/units/{unit_id}/commercial-transitions",
        json={"to_status": to_status, "effective_date": effective, **extra},
    )


def test_a_commercial_event_cannot_be_dated_before_the_one_it_follows(
    admin_client: TestClient, project_id: str, unit_id: str, db: Session
) -> None:
    """Given held on the 10th, then available on the 1st is refused.

    The lock already stops two writers forking the chain. It does not stop one
    writer building a chain whose dates run backwards, and a history like that
    has two answers to "what was this unit on the 5th?".
    """
    first = _transition(
        admin_client, project_id, unit_id, "held", "2026-08-10", reason="Board review"
    )
    assert first.status_code == 201, first.text

    response = _transition(admin_client, project_id, unit_id, "available", "2026-08-01")

    assert response.status_code == 422
    assert "2026-08-10" in response.json()["detail"]

    db.expire_all()
    assert db.scalars(
        select(Unit).where(Unit.id == uuid.UUID(unit_id))
    ).one().commercial_status == ("held")
    assert len(db.scalars(select(UnitStatusEvent)).all()) == 1


def test_a_same_day_correction_is_allowed(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    """A change recorded the same day is ordinary; the event order carries it."""
    _transition(admin_client, project_id, unit_id, "held", "2026-08-10", reason="Board review")

    response = _transition(
        admin_client, project_id, unit_id, "unreleased", "2026-08-10", reason="Reversed"
    )

    assert response.status_code == 201, response.text


def test_the_first_event_may_be_backdated(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    """There is nothing before the first event, so nothing to contradict."""
    response = _transition(
        admin_client, project_id, unit_id, "held", "2020-01-01", reason="Historic backfill"
    )

    assert response.status_code == 201, response.text


def test_a_refused_backdate_records_nothing(
    admin_client: TestClient, project_id: str, unit_id: str, db: Session
) -> None:
    from app.modules.audit.models import AuditEvent

    _transition(admin_client, project_id, unit_id, "held", "2026-08-10", reason="Board review")
    before = len(db.scalars(select(AuditEvent)).all())

    _transition(admin_client, project_id, unit_id, "available", "2026-08-01")

    db.expire_all()
    assert len(db.scalars(select(AuditEvent)).all()) == before


# --------------------------------------------------------------------------- #
# Area semantics
# --------------------------------------------------------------------------- #


def _area_type(client: TestClient, project_id: str, **overrides: object) -> dict:
    payload: dict[str, object] = {
        "code": "INTERNAL",
        "label": "Internal area",
        "area_role": "internal",
        "weight_factor": "1.000000",
    }
    payload.update(overrides)
    response = client.post(f"{inventory_url(project_id)}/area-types", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_an_unused_area_type_can_still_be_corrected(
    admin_client: TestClient, project_id: str, inventory_reference_data: None
) -> None:
    """Before anything has been measured, a mistake is just a mistake."""
    area_type = _area_type(admin_client, project_id, code="BALCONY", area_role="outdoor")

    response = admin_client.patch(
        f"{inventory_url(project_id)}/area-types/{area_type['id']}",
        json={"unit_of_measure": "sqft", "weight_factor": "0.000000"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["unit_of_measure"] == "sqft"


@pytest.mark.parametrize(
    ("field", "value"), [("unit_of_measure", "sqft"), ("area_role", "outdoor")]
)
def test_a_used_area_type_cannot_be_given_a_new_meaning(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    db: Session,
    field: str,
    value: str,
) -> None:
    """Given a stored 100.0000, then changing sqm to sqft is refused.

    Nobody re-measured the building. The number would keep its digits and lose
    its meaning, and every figure derived from it would be wrong without a
    single row changing.
    """
    admin_client.post(
        f"{inventory_url(project_id)}/units/{unit_id}/area-schedules",
        json={
            "revision_code": "R1",
            "reconciled": True,
            "values": [{"area_type_id": area_types["INTERNAL"], "raw_area": "100.0000"}],
        },
    )

    response = admin_client.patch(
        f"{inventory_url(project_id)}/area-types/{area_types['INTERNAL']}", json={field: value}
    )

    assert response.status_code == 409
    db.expire_all()
    area_type = db.scalars(
        select(AreaType).where(AreaType.id == uuid.UUID(area_types["INTERNAL"]))
    ).one()
    assert getattr(area_type, field) != value


def test_a_used_area_types_factor_may_still_change(
    admin_client: TestClient, project_id: str, unit_id: str, area_types: dict[str, str], db: Session
) -> None:
    """The factor is a commercial decision, not a reinterpretation of a measurement.

    Changing it moves every weighted figure derived from it, on purpose, and
    leaves every raw measurement exactly where it was.
    """
    admin_client.post(
        f"{inventory_url(project_id)}/units/{unit_id}/area-schedules",
        json={
            "revision_code": "R1",
            "reconciled": True,
            "values": [{"area_type_id": area_types["BALCONY"], "raw_area": "20.0000"}],
        },
    )

    response = admin_client.patch(
        f"{inventory_url(project_id)}/area-types/{area_types['BALCONY']}",
        json={"weight_factor": "0.250000"},
    )

    assert response.status_code == 200, response.text
    db.expire_all()
    from app.modules.inventory.models import UnitAreaValue

    assert db.scalars(
        select(UnitAreaValue).where(UnitAreaValue.area_type_id == uuid.UUID(area_types["BALCONY"]))
    ).one().raw_area == Decimal("20.0000")


def test_a_weighted_total_cannot_mix_units_of_measure(
    admin_client: TestClient, project_id: str, inventory_reference_data: None
) -> None:
    """Given a project that weighs in sqm, then a contributing sqft area is refused.

    100 sqm plus 200 sqft is not a number. There is no conversion here and there
    should not be one; the project picks a unit and everything it weighs uses it.
    """
    _area_type(admin_client, project_id)

    response = admin_client.post(
        f"{inventory_url(project_id)}/area-types",
        json={
            "code": "BALCONY",
            "label": "Balcony",
            "area_role": "outdoor",
            "unit_of_measure": "sqft",
            "weight_factor": "0.500000",
        },
    )

    assert response.status_code == 422
    assert "sqm" in response.json()["detail"]
    assert "sqft" in response.json()["detail"]


def test_an_area_that_contributes_nothing_may_measure_differently(
    admin_client: TestClient, project_id: str, inventory_reference_data: None
) -> None:
    """A zero factor adds nothing to the sum, so it cannot corrupt the sum."""
    _area_type(admin_client, project_id)

    response = admin_client.post(
        f"{inventory_url(project_id)}/area-types",
        json={
            "code": "PLOT",
            "label": "Plot",
            "area_role": "plot",
            "unit_of_measure": "sqft",
            "weight_factor": "0.000000",
        },
    )

    assert response.status_code == 201, response.text


def test_the_weighted_total_says_what_unit_it_is_in(
    admin_client: TestClient, project_id: str, unit_id: str, area_types: dict[str, str]
) -> None:
    """A weighted area on a screen without its unit is a number two people read two ways."""
    schedule = admin_client.post(
        f"{inventory_url(project_id)}/units/{unit_id}/area-schedules",
        json={
            "revision_code": "R1",
            "reconciled": True,
            "values": [{"area_type_id": area_types["INTERNAL"], "raw_area": "100.0000"}],
        },
    ).json()["id"]
    admin_client.post(
        f"{inventory_url(project_id)}/units/{unit_id}/area-schedules/{schedule}/approve"
    )

    body = admin_client.get(f"{inventory_url(project_id)}/units/{unit_id}").json()

    assert body["weighted_saleable_area"] == "100.0000"
    assert body["weighted_saleable_area_unit"] == "sqm"


# --------------------------------------------------------------------------- #
# The register's counts
# --------------------------------------------------------------------------- #


def test_the_register_publishes_no_count_it_measured_on_one_page(
    admin_client: TestClient, project_id: str, floor_id: str, inventory_reference_data: None
) -> None:
    """Given five units and a page of two, then every count still describes five.

    A release-eligible total computed from the page was the PR-MVP-02 permit bug
    returning in a new place. It is gone rather than made expensive: eligibility
    is a per-unit fact, and a development-wide total is a reporting question.
    """
    for number in range(1, 6):
        admin_client.post(
            f"{inventory_url(project_id)}/units",
            json=unit_payload(floor_id, unit_number=f"10{number}", unit_reference=f"B1-10{number}"),
        )

    body = admin_client.get(f"{inventory_url(project_id)}/units?limit=2").json()

    assert len(body["units"]) == 2
    assert body["total"] == 5
    assert body["unreleased_count"] == 5
    assert "release_eligible_count" not in body
    # The per-unit fact survives, where it can be read against its own unit.
    assert all("release_eligible" in unit for unit in body["units"])
