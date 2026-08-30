"""A price is never overwritten, and never approved against a unit that moved.

The two rules this file protects. **Versions, not updates**: every change to a
unit's price is a new row, the old one is superseded, and both stay readable for
ever. **Frozen basis**: a draft records the unit it priced, and submission,
approval and activation all refuse if that unit has changed since — because a
price says "this unit, measured this way, costs this", and an approval that
waved through re-measured geometry would be signing a different sentence.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.inventory.models import Unit
from app.modules.pricing.models import UnitPriceComponent, UnitPriceVersion
from tests.modules.conftest import approve_areas, inventory_url, pricing_url


def _version_url(project_id: str, version_id: str) -> str:
    return f"{pricing_url(project_id)}/price-versions/{version_id}"


def _draft(client: TestClient, project_id: str, unit_id: str, **body: object) -> dict:
    response = client.post(f"{pricing_url(project_id)}/units/{unit_id}/price-versions", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _reprice(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
) -> str:
    """Draft, submit, approve and activate a replacement price."""
    version = _draft(finance_client, project_id, unit_id)
    base = _version_url(project_id, version["id"])
    assert finance_client.post(f"{base}/submit", json={}).status_code == 200
    assert cfo_client.post(f"{base}/approve", json={"reason": "Repriced"}).status_code == 200
    activated = cfo_client.post(f"{base}/activate")
    assert activated.status_code == 200, activated.text
    return version["id"]


# --------------------------------------------------------------------------- #
# The lifecycle
# --------------------------------------------------------------------------- #


def test_a_draft_is_not_a_price(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    active_configuration: str,
    db: Session,
) -> None:
    """Drafting sets no release gate: nobody has agreed to the number yet."""
    approve_areas(admin_client, project_id, unit_id, area_types)

    _draft(finance_client, project_id, unit_id)

    db.expire_all()
    assert db.scalars(select(Unit)).one().pricing_approved is False


def test_approval_alone_does_not_open_the_release_gate(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    active_configuration: str,
    db: Session,
) -> None:
    """Approved means may be activated. Active means this is the list price."""
    approve_areas(admin_client, project_id, unit_id, area_types)
    version = _draft(finance_client, project_id, unit_id)
    base = _version_url(project_id, version["id"])
    finance_client.post(f"{base}/submit", json={})

    cfo_client.post(f"{base}/approve", json={"reason": "Within feasibility"})

    db.expire_all()
    assert db.scalars(select(Unit)).one().pricing_approved is False


def test_activation_is_the_only_thing_that_sets_pricing_approved(
    project_id: str, unit_id: str, priced_unit: str, db: Session
) -> None:
    db.expire_all()
    assert db.scalars(select(Unit)).one().pricing_approved is True


def test_a_unit_cannot_have_its_pricing_approved_by_patching_the_unit(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    """There is no button, no override and no back door. There never was."""
    response = admin_client.patch(
        f"{inventory_url(project_id)}/units/{unit_id}", json={"pricing_approved": True}
    )

    assert response.status_code == 422


def test_the_submitter_cannot_approve_their_own_price(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    active_configuration: str,
    db: Session,
) -> None:
    from tests.factories import client_for, make_user
    from tests.modules.conftest import grant_access

    both = make_user(db, email="both2@example.com", roles=("finance", "approver_cfo"))
    grant_access(admin_client, project_id, both)
    client = client_for(both.email)
    approve_areas(admin_client, project_id, unit_id, area_types)
    version = _draft(client, project_id, unit_id)
    base = _version_url(project_id, version["id"])
    client.post(f"{base}/submit", json={})

    response = client.post(f"{base}/approve", json={"reason": "Mine"})

    assert response.status_code == 403
    assert "may not approve it" in response.json()["detail"]


def test_versions_are_numbered_in_sequence_per_unit(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
    priced_unit: str,
) -> None:
    second = _draft(finance_client, project_id, unit_id)

    assert second["version_number"] == 2


def test_activating_a_replacement_supersedes_the_one_before_it(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
    priced_unit: str,
    db: Session,
) -> None:
    """The old price stays exactly as it was, marked as what it now is."""
    second = _reprice(admin_client, finance_client, cfo_client, project_id, unit_id)

    db.expire_all()
    rows = {str(row.id): row for row in db.scalars(select(UnitPriceVersion))}
    assert rows[priced_unit].status == "superseded"
    assert rows[priced_unit].superseded_at is not None
    assert rows[priced_unit].valid_to is not None
    assert rows[priced_unit].reference_price_ex_tax == Decimal("165000.00")
    assert rows[second].status == "active"
    assert sum(1 for row in rows.values() if row.status == "active") == 1


def test_a_superseded_price_is_still_in_the_history(
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    priced_unit: str,
    admin_client: TestClient,
    cfo_client: TestClient,
) -> None:
    _reprice(admin_client, finance_client, cfo_client, project_id, unit_id)

    body = finance_client.get(f"{pricing_url(project_id)}/units/{unit_id}").json()

    assert [item["version_number"] for item in body["history"]] == [2, 1]
    assert [item["status"] for item in body["history"]] == ["active", "superseded"]


def test_an_active_price_cannot_be_edited(
    finance_client: TestClient, project_id: str, priced_unit: str
) -> None:
    response = finance_client.patch(
        _version_url(project_id, priced_unit), json={"change_reason": "Second thoughts"}
    )

    assert response.status_code == 409
    assert "draft" in response.json()["detail"]


def test_there_is_no_delete_route_for_a_price(
    finance_client: TestClient, project_id: str, priced_unit: str
) -> None:
    assert finance_client.delete(_version_url(project_id, priced_unit)).status_code == 404


def test_status_cannot_be_patched_onto_a_price(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    active_configuration: str,
) -> None:
    approve_areas(admin_client, project_id, unit_id, area_types)
    version = _draft(finance_client, project_id, unit_id)

    response = finance_client.patch(
        _version_url(project_id, version["id"]), json={"status": "active"}
    )

    assert response.status_code == 422


# --------------------------------------------------------------------------- #
# Overrides
# --------------------------------------------------------------------------- #


def test_an_override_keeps_the_calculation_beside_it(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    active_configuration: str,
) -> None:
    """The approver has to be able to see what the rules said and what a person said."""
    approve_areas(admin_client, project_id, unit_id, area_types)
    version = _draft(finance_client, project_id, unit_id)

    response = finance_client.patch(
        _version_url(project_id, version["id"]),
        json={
            "overrides": [
                {
                    "sequence": 2,
                    "override_amount": "12000.00",
                    "override_reason": "Balcony faces the service yard",
                }
            ]
        },
    )

    assert response.status_code == 200, response.text
    line = response.json()["components"][1]
    assert (line["calculated_amount"], line["override_amount"], line["final_amount"]) == (
        "15000.00",
        "12000.00",
        "12000.00",
    )
    assert response.json()["reference_price_ex_tax"] == "162000.00"


def test_an_override_without_a_reason_is_refused(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    active_configuration: str,
) -> None:
    approve_areas(admin_client, project_id, unit_id, area_types)
    version = _draft(finance_client, project_id, unit_id)

    response = finance_client.patch(
        _version_url(project_id, version["id"]),
        json={"overrides": [{"sequence": 1, "override_amount": "1.00"}]},
    )

    assert response.status_code == 422
    assert "reason" in response.json()["detail"]


def test_the_total_always_equals_the_sum_of_the_lines(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    active_configuration: str,
    db: Session,
) -> None:
    """Including after an override. There is one addition, over the visible lines."""
    approve_areas(admin_client, project_id, unit_id, area_types)
    version = _draft(finance_client, project_id, unit_id)
    finance_client.patch(
        _version_url(project_id, version["id"]),
        json={
            "overrides": [
                {"sequence": 1, "override_amount": "149999.99", "override_reason": "Rounded down"}
            ]
        },
    )

    db.expire_all()
    row = db.scalars(select(UnitPriceVersion).where(UnitPriceVersion.id == version["id"])).one()
    components = db.scalars(
        select(UnitPriceComponent).where(UnitPriceComponent.unit_price_version_id == row.id)
    ).all()
    assert sum(item.final_amount for item in components) == row.reference_price_ex_tax
    assert row.reference_price_ex_tax == Decimal("164999.99")


# --------------------------------------------------------------------------- #
# The frozen basis
# --------------------------------------------------------------------------- #


def test_a_re_measured_unit_cannot_have_its_old_draft_submitted(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    active_configuration: str,
) -> None:
    """Given a new approved measurement, then the draft that predates it is refused.

    This is the check that stops an approval signing off geometry that has
    already been superseded — the failure mode that makes a price list and a
    drawing set disagree.
    """
    approve_areas(admin_client, project_id, unit_id, area_types)
    version = _draft(finance_client, project_id, unit_id)
    approve_areas(admin_client, project_id, unit_id, area_types, internal="120.0000", revision="R1")

    response = finance_client.post(f"{_version_url(project_id, version['id'])}/submit", json={})

    assert response.status_code == 409
    assert response.json()["detail"] == "Unit pricing basis changed. Generate a new price version."


def test_a_changed_feature_stops_an_approved_price_being_activated(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    active_configuration: str,
    db: Session,
) -> None:
    """The last gate before a price goes live re-reads the unit under its lock."""
    approve_areas(admin_client, project_id, unit_id, area_types)
    version = _draft(finance_client, project_id, unit_id)
    base = _version_url(project_id, version["id"])
    finance_client.post(f"{base}/submit", json={})
    cfo_client.post(f"{base}/approve", json={"reason": "Fine"})
    admin_client.patch(
        f"{inventory_url(project_id)}/units/{unit_id}", json={"view_class_code": "SEA"}
    )

    response = cfo_client.post(f"{base}/activate")

    assert response.status_code == 409
    db.expire_all()
    assert db.scalars(select(Unit)).one().pricing_approved is False


def test_there_is_no_way_to_force_a_stale_price_through(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    active_configuration: str,
) -> None:
    """No override flag, no query parameter, no second endpoint."""
    approve_areas(admin_client, project_id, unit_id, area_types)
    version = _draft(finance_client, project_id, unit_id)
    approve_areas(admin_client, project_id, unit_id, area_types, internal="120.0000", revision="R1")

    forced = finance_client.post(
        f"{_version_url(project_id, version['id'])}/submit?force=true",
        json={"reason": "Ship it"},
    )

    assert forced.status_code == 409


def test_the_price_lifecycle_is_audited(project_id: str, priced_unit: str, db: Session) -> None:
    actions = {
        event.action
        for event in db.scalars(
            select(AuditEvent).where(AuditEvent.action.like("unit_price_version.%"))
        )
    }

    assert {
        "unit_price_version.created",
        "unit_price_version.submitted",
        "unit_price_version.approved",
        "unit_price_version.activated",
    } <= actions


def test_a_sales_advisor_never_sees_a_draft_price(
    admin_client: TestClient,
    finance_client: TestClient,
    advisor_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    active_configuration: str,
    priced_unit: str,
) -> None:
    """A quote from a draft is a quote from a number nobody has agreed to."""
    draft = _draft(finance_client, project_id, unit_id)

    listed = advisor_client.get(f"{pricing_url(project_id)}/units/{unit_id}").json()
    direct = advisor_client.get(_version_url(project_id, draft["id"]))

    assert [item["status"] for item in listed["history"]] == ["active"]
    assert direct.status_code == 404
    assert listed["active_price"]["reference_price_ex_tax"] == "165000.00"


def test_a_sales_advisor_cannot_reach_the_pricing_configuration(
    advisor_client: TestClient, project_id: str, active_configuration: str
) -> None:
    response = advisor_client.get(f"{pricing_url(project_id)}/configurations")

    assert response.status_code == 403
