"""Completeness and release: what stops a unit being offered for sale.

Nothing here is stored. Completeness and eligibility are computed from the rows
that hold the facts, so they cannot be true on the day they were written and
quietly wrong afterwards.

Before PR-MVP-04 exists, ``pricing_approved`` is false on every unit and every
unit is therefore blocked. That is the correct answer, not a gap: a development
should not offer a unit it has no approved price for.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.inventory.models import Unit
from tests.modules.conftest import PROJECTS, approve_areas, inventory_url, make_releasable


def _controls(project_id: str, unit_id: str) -> str:
    return f"{inventory_url(project_id)}/units/{unit_id}/release-controls"


def _unit(client: TestClient, project_id: str, unit_id: str) -> dict:
    return client.get(f"{inventory_url(project_id)}/units/{unit_id}").json()


def test_a_new_unit_is_incomplete_and_says_why(
    admin_client: TestClient, project_id: str, unit_id: str, area_types: dict[str, str]
) -> None:
    body = _unit(admin_client, project_id, unit_id)

    assert body["is_complete"] is False
    assert "Approved area schedule" in body["missing_requirements"]
    assert body["completeness_percent"] < 100


def test_completeness_rises_as_facts_are_recorded(
    admin_client: TestClient, project_id: str, unit_id: str, area_types: dict[str, str]
) -> None:
    """Given the areas are approved, then the outstanding items shrink."""
    before = _unit(admin_client, project_id, unit_id)
    approve_areas(admin_client, project_id, unit_id, area_types)
    after = _unit(admin_client, project_id, unit_id)

    assert after["completeness_percent"] > before["completeness_percent"]
    assert after["is_complete"] is True
    assert after["missing_requirements"] == []


def test_unit_without_type_can_be_complete_and_released(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    db: Session,
) -> None:
    response = admin_client.patch(
        f"{inventory_url(project_id)}/units/{unit_id}", json={"unit_type_code": None}
    )
    assert response.status_code == 200
    make_releasable(admin_client, project_id, unit_id, area_types, db)
    body = _unit(admin_client, project_id, unit_id)
    assert body["unit_type_code"] is None
    assert body["is_complete"] is True
    assert body["missing_requirements"] == []
    assert body["release_eligible"] is True
    response = admin_client.post(
        f"{inventory_url(project_id)}/units/{unit_id}/commercial-transitions",
        json={"to_status": "available", "effective_date": "2026-02-01"},
    )
    assert response.status_code == 201, response.text


def test_a_new_required_area_type_makes_a_complete_unit_incomplete_again(
    admin_client: TestClient, project_id: str, unit_id: str, area_types: dict[str, str]
) -> None:
    """Given a newly required area, then units measured before it are incomplete.

    The figure is derived, so a configuration change shows up on the next read
    rather than waiting for somebody to recompute a stored column.
    """
    approve_areas(admin_client, project_id, unit_id, area_types)
    assert _unit(admin_client, project_id, unit_id)["is_complete"] is True

    admin_client.post(
        f"{inventory_url(project_id)}/area-types",
        json={
            "code": "TERRACE",
            "label": "Terrace",
            "area_role": "outdoor",
            "weight_factor": "0.300000",
            "required_for_release": True,
        },
    )

    body = _unit(admin_client, project_id, unit_id)
    assert body["is_complete"] is False
    assert "Area: Terrace" in body["missing_requirements"]


def test_pricing_approval_blocks_release_before_pr_mvp_04(
    admin_client: TestClient, project_id: str, unit_id: str, area_types: dict[str, str]
) -> None:
    """Given everything else is satisfied, then pricing is the remaining blocker."""
    approve_areas(admin_client, project_id, unit_id, area_types)
    admin_client.patch(
        _controls(project_id, unit_id),
        json={
            "drawings_approved": True,
            "legal_sale_eligible": True,
            "release_date": "2026-01-01",
        },
    )

    body = _unit(admin_client, project_id, unit_id)
    assert body["release_eligible"] is False
    assert body["release_blockers"] == ["Pricing not approved"]


def test_pricing_approval_cannot_be_set_through_the_api(
    admin_client: TestClient, project_id: str, unit_id: str, db: Session
) -> None:
    """Given a request naming it, then 422 — on both endpoints that touch a unit.

    PR-MVP-04 sets it when a real approved price exists. A button here would be
    a pricing approval with no price behind it.
    """
    assert (
        admin_client.patch(
            _controls(project_id, unit_id), json={"pricing_approved": True}
        ).status_code
        == 422
    )
    assert (
        admin_client.patch(
            f"{inventory_url(project_id)}/units/{unit_id}", json={"pricing_approved": True}
        ).status_code
        == 422
    )
    assert db.scalars(select(Unit)).one().pricing_approved is False


def test_a_fully_satisfied_unit_is_releasable(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    db: Session,
) -> None:
    """Given every gate including pricing, then the unit may be released."""
    make_releasable(admin_client, project_id, unit_id, area_types, db)

    body = _unit(admin_client, project_id, unit_id)
    assert body["release_blockers"] == []
    assert body["release_eligible"] is True

    response = admin_client.post(
        f"{inventory_url(project_id)}/units/{unit_id}/commercial-transitions",
        json={"to_status": "available", "effective_date": "2026-02-01"},
    )
    assert response.status_code == 201, response.text


@pytest.mark.parametrize("field", ["drawings_approved", "legal_sale_eligible"])
def test_preparation_is_recorded_but_does_not_hold_the_unit_back(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    db: Session,
    field: str,
) -> None:
    """Given drawings or legal sign-off outstanding, then the unit still sells.

    Both are facts worth knowing and both stay on the record. Neither answers
    the question the release gate asks -- whether this unit can be sold at all
    -- and a development that has priced a unit and set its date is not helped
    by a release that waits on a countersignature.
    """
    make_releasable(admin_client, project_id, unit_id, area_types, db)

    admin_client.patch(_controls(project_id, unit_id), json={field: False})

    unit = _unit(admin_client, project_id, unit_id)
    assert unit["release_blockers"] == []
    assert unit[field] is False
    assert unit["commercial_status"] == "available"


def test_a_future_release_date_blocks_until_it_arrives(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    db: Session,
) -> None:
    make_releasable(admin_client, project_id, unit_id, area_types, db, release_date="2099-01-01")

    blockers = _unit(admin_client, project_id, unit_id)["release_blockers"]
    assert any("not reached" in blocker for blocker in blockers)


def test_a_block_reason_blocks_release(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    db: Session,
) -> None:
    make_releasable(admin_client, project_id, unit_id, area_types, db)
    admin_client.patch(_controls(project_id, unit_id), json={"block_reason": "Structural query"})

    blockers = _unit(admin_client, project_id, unit_id)["release_blockers"]
    assert "Commercial block: Structural query" in blockers


def test_an_inactive_unit_is_never_releasable(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    db: Session,
) -> None:
    make_releasable(admin_client, project_id, unit_id, area_types, db)
    admin_client.patch(
        f"{inventory_url(project_id)}/units/{unit_id}",
        json={"is_active": False, "activity_reason": "Removed from active inventory"},
    )

    assert "Unit is not active" in _unit(admin_client, project_id, unit_id)["release_blockers"]


def test_drawings_approval_belongs_to_design(
    db: Session, admin_client: TestClient, project_id: str, unit_id: str, engineer_member: object
) -> None:
    """Given Design / Engineering, then drawings yes, release calendar no."""
    from tests.factories import client_for

    client = client_for("design2@example.com")

    assert (
        client.patch(_controls(project_id, unit_id), json={"drawings_approved": True}).status_code
        == 200
    )
    refused = client.patch(_controls(project_id, unit_id), json={"release_date": "2026-01-01"})
    assert refused.status_code == 403
    assert "release date" in refused.json()["detail"]


def test_legal_eligibility_belongs_to_legal(
    db: Session, admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    from tests.factories import client_for, make_user

    lawyer = make_user(db, email="legal@example.com", roles=("legal",))
    admin_client.put(f"{PROJECTS}/{project_id}/access/{lawyer.id}")
    client = client_for(lawyer.email)

    assert (
        client.patch(_controls(project_id, unit_id), json={"legal_sale_eligible": True}).status_code
        == 200
    )
    assert (
        client.patch(_controls(project_id, unit_id), json={"drawings_approved": True}).status_code
        == 403
    )


def test_the_release_calendar_belongs_to_sales_operations(
    db: Session, admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    from tests.factories import client_for, make_user

    ops = make_user(db, email="ops2@example.com", roles=("sales_operations",))
    admin_client.put(f"{PROJECTS}/{project_id}/access/{ops.id}")
    client = client_for(ops.email)

    assert (
        client.patch(
            _controls(project_id, unit_id),
            json={"release_date": "2026-01-01", "release_batch": "Launch 1"},
        ).status_code
        == 200
    )
    assert (
        client.patch(_controls(project_id, unit_id), json={"legal_sale_eligible": True}).status_code
        == 403
    )


def test_a_partly_permitted_request_is_refused_whole(
    db: Session, admin_client: TestClient, project_id: str, unit_id: str, engineer_member: object
) -> None:
    """Given one allowed field and one refused, then nothing is written.

    A request half-applied would leave the caller believing both changes landed.
    """
    from tests.factories import client_for

    response = client_for("design2@example.com").patch(
        _controls(project_id, unit_id),
        json={"drawings_approved": True, "release_batch": "Launch 1"},
    )

    assert response.status_code == 403
    unit = db.scalars(select(Unit)).one()
    assert unit.drawings_approved is False
    assert unit.release_batch is None


# --------------------------------------------------------------------------- #
# The release date is the release
# --------------------------------------------------------------------------- #


def test_setting_a_release_date_that_has_arrived_puts_the_unit_on_sale(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    db: Session,
) -> None:
    """Given a priced unit, when a past release date is saved, then it is available.

    The date is the decision. Asking the operator to state it and then to
    confirm it is asking the same question twice, and the second question is
    the one that was being forgotten.
    """
    approve_areas(admin_client, project_id, unit_id, area_types)
    unit = db.scalars(select(Unit)).one()
    unit.pricing_approved = True
    db.commit()

    admin_client.patch(_controls(project_id, unit_id), json={"release_date": "2024-01-01"})

    assert _unit(admin_client, project_id, unit_id)["commercial_status"] == "available"


def test_the_status_event_carries_the_release_date_the_operator_set(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    db: Session,
) -> None:
    """The history says the unit went on sale on its release date, not today.

    A release recorded under the date it was typed rather than the date it took
    effect makes every later "what was on the market in January?" wrong.
    """
    approve_areas(admin_client, project_id, unit_id, area_types)
    unit = db.scalars(select(Unit)).one()
    unit.pricing_approved = True
    db.commit()

    admin_client.patch(_controls(project_id, unit_id), json={"release_date": "2024-03-04"})

    history = admin_client.get(f"{inventory_url(project_id)}/units/{unit_id}/status-history").json()
    released = [row for row in history if row["to_status"] == "available"]
    assert released and released[-1]["effective_date"] == "2024-03-04"


def test_an_unpriced_unit_stays_off_the_market_however_the_date_reads(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
) -> None:
    """The one gate the owner kept. A unit with no approved price is not sellable."""
    approve_areas(admin_client, project_id, unit_id, area_types)

    admin_client.patch(_controls(project_id, unit_id), json={"release_date": "2024-01-01"})

    unit = _unit(admin_client, project_id, unit_id)
    assert unit["commercial_status"] == "unreleased"
    assert "Pricing not approved" in unit["release_blockers"]


def test_a_future_release_date_does_not_release_the_unit_early(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    db: Session,
) -> None:
    """Saving tomorrow's date states an intention, not a sale."""
    approve_areas(admin_client, project_id, unit_id, area_types)
    unit = db.scalars(select(Unit)).one()
    unit.pricing_approved = True
    db.commit()

    admin_client.patch(_controls(project_id, unit_id), json={"release_date": "2099-01-01"})

    assert _unit(admin_client, project_id, unit_id)["commercial_status"] == "unreleased"


def test_a_blocked_unit_is_not_released_by_its_date_arriving(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    db: Session,
) -> None:
    """A commercial block is somebody saying stop, and the date does not overrule it."""
    approve_areas(admin_client, project_id, unit_id, area_types)
    unit = db.scalars(select(Unit)).one()
    unit.pricing_approved = True
    db.commit()

    admin_client.patch(
        _controls(project_id, unit_id),
        json={"release_date": "2024-01-01", "block_reason": "Title deed under review"},
    )

    on_file = _unit(admin_client, project_id, unit_id)
    assert on_file["commercial_status"] == "unreleased"
    assert "Commercial block: Title deed under review" in on_file["release_blockers"]
