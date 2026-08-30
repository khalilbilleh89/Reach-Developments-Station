"""When a unit changes, its pricing approval goes — and its price history stays.

The rule: an active price describes a unit as it was when the price was made.
If a priced fact about the unit moves, the approval that price produced no
longer describes anything, so ``pricing_approved`` is withdrawn and the unit
stops being releasable. The price row itself is untouched: it is what the unit
was offered at, and deleting it would erase a commercial fact.

The mirror rule matters just as much. A note, a spelling correction, a new
benchmark or a draft policy do **not** invalidate anything, because unnecessary
repricing is its own kind of noise.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.inventory.models import Unit
from app.modules.pricing.models import UnitPriceVersion
from tests.modules.conftest import (
    PROJECTS,
    approve_areas,
    configuration_payload,
    inventory_url,
    pricing_url,
)


def _approved(db: Session) -> bool:
    db.expire_all()
    return db.scalars(select(Unit)).one().pricing_approved


def _price_is_intact(db: Session, version_id: str) -> bool:
    """The historical price still exists, still active, still saying what it said."""
    row = db.scalars(select(UnitPriceVersion).where(UnitPriceVersion.id == version_id)).one()
    return row.status == "active" and str(row.reference_price_ex_tax) == "165000.00"


# --------------------------------------------------------------------------- #
# Changes that withdraw the approval
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("unit_type_code", "3BR"),
        ("view_class_code", "SEA"),
        ("orientation_code", "NORTH"),
        ("floor_band_code", "MID"),
        ("accessibility_code", "STEP_FREE"),
        ("garden_class_code", "PRIVATE"),
        ("furnishing_specification_code", "STANDARD"),
        ("is_corner", True),
        ("pool_access", True),
        ("plot_coverage_fraction", "0.450000"),
    ],
)
def test_a_priced_fact_changing_withdraws_the_pricing_approval(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    priced_unit: str,
    db: Session,
    field: str,
    value: object,
) -> None:
    """Each of these is read by the calculation, so each of them stales the price."""
    assert _approved(db) is True

    response = admin_client.patch(
        f"{inventory_url(project_id)}/units/{unit_id}", json={field: value}
    )

    assert response.status_code == 200, response.text
    assert _approved(db) is False
    assert _price_is_intact(db, priced_unit)


def test_moving_a_unit_to_another_floor_withdraws_the_approval(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    building_id: str,
    priced_unit: str,
    db: Session,
) -> None:
    """A floor change is a building and a phase change, and both can be priced."""
    second = admin_client.post(
        f"{inventory_url(project_id)}/floors",
        json={"building_id": building_id, "code": "02", "label": "Second floor"},
    ).json()["id"]
    admin_client.post(
        f"{inventory_url(project_id)}/units/{unit_id}/commercial-transitions",
        json={"to_status": "held", "effective_date": "2026-02-01", "reason": "Repricing"},
    )
    admin_client.post(
        f"{inventory_url(project_id)}/units/{unit_id}/commercial-transitions",
        json={"to_status": "unreleased", "effective_date": "2026-02-02", "reason": "Move"},
    )

    response = admin_client.patch(
        f"{inventory_url(project_id)}/units/{unit_id}", json={"floor_id": second}
    )

    assert response.status_code == 200, response.text
    assert _approved(db) is False
    assert _price_is_intact(db, priced_unit)


def test_approving_a_new_measurement_withdraws_the_approval(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    priced_unit: str,
    db: Session,
) -> None:
    """A price is calculated from measured areas. New areas, stale price."""
    approve_areas(admin_client, project_id, unit_id, area_types, internal="120.0000", revision="R1")

    assert _approved(db) is False
    assert _price_is_intact(db, priced_unit)


def test_linking_a_parking_bay_withdraws_the_approval(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    floor_id: str,
    priced_unit: str,
    db: Session,
) -> None:
    created = admin_client.post(
        f"{inventory_url(project_id)}/sub-assets",
        json={
            "asset_reference": "P-1",
            "asset_type": "parking",
            "floor_id": floor_id,
            "linked_unit_id": unit_id,
        },
    )

    assert created.status_code == 201, created.text
    assert _approved(db) is False


def test_unlinking_a_bay_withdraws_the_approval_of_the_unit_it_left(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
    floor_id: str,
    area_types: dict[str, str],
    active_configuration: str,
    db: Session,
) -> None:
    """Both ends of a move. The source unit is priced for a bay it no longer has."""
    asset = admin_client.post(
        f"{inventory_url(project_id)}/sub-assets",
        json={
            "asset_reference": "P-1",
            "asset_type": "parking",
            "floor_id": floor_id,
            "linked_unit_id": unit_id,
        },
    ).json()["id"]
    approve_areas(admin_client, project_id, unit_id, area_types)
    version = finance_client.post(
        f"{pricing_url(project_id)}/units/{unit_id}/price-versions", json={}
    ).json()["id"]
    base = f"{pricing_url(project_id)}/price-versions/{version}"
    finance_client.post(f"{base}/submit", json={})
    cfo_client.post(f"{base}/approve", json={"reason": "ok"})
    cfo_client.post(f"{base}/activate")
    assert _approved(db) is True

    admin_client.patch(
        f"{inventory_url(project_id)}/sub-assets/{asset}", json={"linked_unit_id": None}
    )

    assert _approved(db) is False


def test_a_custom_value_change_withdraws_the_approval(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    priced_unit: str,
    db: Session,
) -> None:
    """Conservative by design: a premium may read any configured field."""
    admin_client.post(
        f"{PROJECTS}/{project_id}/field-definitions",
        json={
            "entity_type": "unit",
            "field_key": "corner_glazing",
            "display_label": "Corner glazing",
            "data_type": "boolean",
            "scope_type": "project",
            "project_id": project_id,
        },
    )

    response = admin_client.put(
        f"{inventory_url(project_id)}/units/{unit_id}/custom-values",
        json={"values": {"corner_glazing": True}},
    )

    assert response.status_code == 200, response.text
    assert _approved(db) is False


def test_pricing_again_restores_the_approval(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
    priced_unit: str,
    db: Session,
) -> None:
    """Activation is the only thing that puts the gate back, exactly as it opened it."""
    admin_client.patch(
        f"{inventory_url(project_id)}/units/{unit_id}", json={"view_class_code": "SEA"}
    )
    assert _approved(db) is False

    version = finance_client.post(
        f"{pricing_url(project_id)}/units/{unit_id}/price-versions", json={}
    ).json()["id"]
    base = f"{pricing_url(project_id)}/price-versions/{version}"
    finance_client.post(f"{base}/submit", json={})
    cfo_client.post(f"{base}/approve", json={"reason": "Repriced for the view"})
    cfo_client.post(f"{base}/activate")

    assert _approved(db) is True
    body = finance_client.get(f"{pricing_url(project_id)}/units/{unit_id}").json()
    assert body["repricing_required"] is False
    assert [item["version_number"] for item in body["history"]] == [2, 1]


def test_a_stale_price_reports_that_repricing_is_required(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    priced_unit: str,
) -> None:
    """The register has to say so, or a stale price looks like a live one."""
    admin_client.patch(f"{inventory_url(project_id)}/units/{unit_id}", json={"is_corner": True})

    body = finance_client.get(f"{pricing_url(project_id)}/units/{unit_id}").json()
    register = finance_client.get(f"{pricing_url(project_id)}/register").json()

    assert body["repricing_required"] is True
    assert body["active_price"] is not None
    assert register["repricing_required"] == 1
    assert register["rows"][0]["repricing_required"] is True


# --------------------------------------------------------------------------- #
# Changes that do not
# --------------------------------------------------------------------------- #


def test_a_note_does_not_withdraw_the_approval(
    admin_client: TestClient, project_id: str, unit_id: str, priced_unit: str, db: Session
) -> None:
    admin_client.patch(
        f"{inventory_url(project_id)}/units/{unit_id}", json={"block_reason": "Awaiting keys"}
    )

    assert _approved(db) is True


def test_correcting_the_unit_reference_does_not_withdraw_the_approval(
    admin_client: TestClient, project_id: str, unit_id: str, priced_unit: str, db: Session
) -> None:
    """Renumbering A-101 to A1-101 is a label change, not a different unit."""
    admin_client.patch(
        f"{inventory_url(project_id)}/units/{unit_id}", json={"unit_reference": "A1-101"}
    )

    assert _approved(db) is True


def test_recording_a_market_benchmark_does_not_withdraw_the_approval(
    finance_client: TestClient, project_id: str, currency_id: str, priced_unit: str, db: Session
) -> None:
    """An observation about the market does not change what a unit was priced at."""
    created = finance_client.post(
        f"{pricing_url(project_id)}/market-benchmarks",
        json={
            "area_basis": "internal",
            "benchmark_price_per_area": "1600.00",
            "currency_id": currency_id,
            "comparison_date": "2026-03-01",
            "source_name": "Local agency survey",
            "tolerance_fraction": "0.100000",
        },
    )

    assert created.status_code == 201, created.text
    assert _approved(db) is True


def test_drafting_a_new_pricing_configuration_does_not_withdraw_the_approval(
    finance_client: TestClient, project_id: str, currency_id: str, priced_unit: str, db: Session
) -> None:
    """A policy nobody has activated has not repriced anything."""
    created = finance_client.post(
        f"{pricing_url(project_id)}/configurations",
        json=configuration_payload(currency_id, name="Next year"),
    )

    assert created.status_code == 201, created.text
    assert _approved(db) is True


def test_drafting_an_escalation_rule_does_not_withdraw_the_approval(
    finance_client: TestClient,
    project_id: str,
    currency_id: str,
    priced_unit: str,
    db: Session,
) -> None:
    second = finance_client.post(
        f"{pricing_url(project_id)}/configurations",
        json=configuration_payload(currency_id, name="Next year"),
    ).json()["id"]

    created = finance_client.post(
        f"{pricing_url(project_id)}/configurations/{second}/escalation-rules",
        json={
            "code": "Q3",
            "label": "Q3 uplift",
            "trigger_type": "date",
            "threshold_date": "2026-07-01",
            "adjustment_method": "percentage",
            "adjustment_percentage_fraction": "0.030000",
        },
    )

    assert created.status_code == 201, created.text
    assert _approved(db) is True
