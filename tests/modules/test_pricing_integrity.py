"""Financial integrity: the ways a price could quietly stop meaning what it says.

Each test here is about a *specific* silent failure — a number that stays on
screen after the thing it described moved. They are grouped by the fact under
protection rather than by endpoint, because the endpoint is rarely where the
damage would show.

Four themes:

**A label is not a price.** Correcting what a unit is called must not invalidate
a price, and changing what it *is* must.

**A price has one effective date.** The date chose which escalations applied, so
nothing may move it afterwards.

**A market flag describes the price beside it.** An override that moves the price
moves the flag with it, against the benchmark as it read when the price was
calculated.

**A withdrawn approval is withdrawn everywhere.** A stale live price stays
readable and stops being quotable.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.inventory.custom_fields import business_today
from app.modules.pricing.models import UnitPriceVersion
from tests.modules.conftest import (
    PROJECTS,
    approve_areas,
    configuration_payload,
    inventory_url,
    pricing_url,
    unit_payload,
)


def _versions(client: TestClient, project_id: str, unit_id: str) -> list[dict[str, Any]]:
    response = client.get(f"{pricing_url(project_id)}/units/{unit_id}/price-versions")
    assert response.status_code == 200, response.text
    return response.json()


def _draft(client: TestClient, project_id: str, unit_id: str, **body: object) -> dict[str, Any]:
    response = client.post(
        f"{pricing_url(project_id)}/units/{unit_id}/price-versions", json=dict(body)
    )
    assert response.status_code == 201, response.text
    return response.json()


def _put_live(
    finance_client: TestClient, cfo_client: TestClient, project_id: str, version_id: str
) -> None:
    base = f"{pricing_url(project_id)}/price-versions/{version_id}"
    assert finance_client.post(f"{base}/submit", json={}).status_code == 200
    assert cfo_client.post(f"{base}/approve", json={"reason": "Reviewed"}).status_code == 200
    assert cfo_client.post(f"{base}/activate").status_code == 200


def _reprice(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
) -> str:
    version = _draft(finance_client, project_id, unit_id)["id"]
    _put_live(finance_client, cfo_client, project_id, version)
    return version


# --------------------------------------------------------------------------- #
# A label is not a price
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("unit_reference", "A1-101"),
        ("unit_number", "101A"),
        ("asset_class", "townhouse"),
    ],
)
def test_a_descriptive_correction_does_not_stale_a_draft(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    active_configuration: str,
    field: str,
    value: str,
) -> None:
    """A-101 becoming A1-101 is a spelling correction, not a different apartment.

    Inventory already decided this: none of these fields clears
    ``pricing_approved``. A fingerprint that compared them anyway would refuse
    the very approval inventory had just declared still valid, and an approver
    who is told "the unit changed" when it did not soon stops reading the
    message at all.
    """
    approve_areas(admin_client, project_id, unit_id, area_types)
    version = _draft(finance_client, project_id, unit_id)["id"]

    corrected = admin_client.patch(
        f"{inventory_url(project_id)}/units/{unit_id}", json={field: value}
    )
    assert corrected.status_code == 200, corrected.text

    base = f"{pricing_url(project_id)}/price-versions/{version}"
    submitted = finance_client.post(f"{base}/submit", json={})
    approved = cfo_client.post(f"{base}/approve", json={"reason": "Unchanged unit"})
    activated = cfo_client.post(f"{base}/activate")

    assert submitted.status_code == 200, submitted.text
    assert approved.status_code == 200, approved.text
    assert activated.status_code == 200, activated.text


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("view_class_code", "SEA"),
        ("orientation_code", "NORTH"),
        ("floor_band_code", "MID"),
    ],
)
def test_a_priced_feature_change_still_stales_a_draft(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    active_configuration: str,
    field: str,
    value: str,
) -> None:
    """The narrowing must not have gone too far: a real feature still refuses."""
    approve_areas(admin_client, project_id, unit_id, area_types)
    version = _draft(finance_client, project_id, unit_id)["id"]

    admin_client.patch(f"{inventory_url(project_id)}/units/{unit_id}", json={field: value})

    response = finance_client.post(
        f"{pricing_url(project_id)}/price-versions/{version}/submit", json={}
    )
    assert response.status_code == 409
    assert "basis changed" in response.json()["detail"]


def test_a_floor_move_stales_a_draft(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    building_id: str,
    area_types: dict[str, str],
    active_configuration: str,
) -> None:
    """Hierarchy is priced: a premium matches a phase or a building by its code."""
    approve_areas(admin_client, project_id, unit_id, area_types)
    version = _draft(finance_client, project_id, unit_id)["id"]
    second = admin_client.post(
        f"{inventory_url(project_id)}/floors",
        json={"building_id": building_id, "code": "02", "label": "Second floor"},
    )
    assert second.status_code == 201, second.text

    moved = admin_client.patch(
        f"{inventory_url(project_id)}/units/{unit_id}", json={"floor_id": second.json()["id"]}
    )
    assert moved.status_code == 200, moved.text

    response = finance_client.post(
        f"{pricing_url(project_id)}/price-versions/{version}/submit", json={}
    )
    assert response.status_code == 409


def test_a_new_area_revision_stales_a_draft(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    active_configuration: str,
) -> None:
    """The measurement is the one thing an approval must never wave through."""
    approve_areas(admin_client, project_id, unit_id, area_types)
    version = _draft(finance_client, project_id, unit_id)["id"]
    approve_areas(
        admin_client,
        project_id,
        unit_id,
        area_types,
        revision="R1",
        internal="120.0000",
    )

    response = finance_client.post(
        f"{pricing_url(project_id)}/price-versions/{version}/submit", json={}
    )
    assert response.status_code == 409


def test_the_snapshot_keeps_the_labels_it_refuses_to_compare(
    finance_client: TestClient, project_id: str, priced_unit: str
) -> None:
    """Kept for the auditor, held apart from the fingerprint so it cannot be compared."""
    version = finance_client.get(f"{pricing_url(project_id)}/price-versions/{priced_unit}").json()
    snapshot = version["basis_snapshot_json"]

    assert snapshot["descriptive"]["unit_reference"] == "B1-101"
    assert snapshot["descriptive"]["asset_class"] == "apartment"
    assert "unit_reference" not in snapshot["pricing_basis"]["unit"]
    assert "asset_class" not in snapshot["pricing_basis"]["unit"]
    assert snapshot["pricing_basis"]["unit"]["unit_type_code"] == "2BR"


# --------------------------------------------------------------------------- #
# One frozen effective date
# --------------------------------------------------------------------------- #


def test_an_omitted_effective_date_stores_todays_business_date(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    active_configuration: str,
) -> None:
    """The date the escalations were evaluated against is the date that is stored.

    Previously the calculation used today and the row kept nothing, which left
    the version claiming no effective date at all while its components had been
    chosen by one.
    """
    approve_areas(admin_client, project_id, unit_id, area_types)

    draft = _draft(finance_client, project_id, unit_id)

    assert draft["valid_from"] == business_today().isoformat()
    assert draft["basis_snapshot_json"]["effective_from"] == business_today().isoformat()


def test_a_draft_effective_date_cannot_be_patched(
    finance_client: TestClient, project_id: str, priced_unit: str, unit_id: str, db: Session
) -> None:
    """Not "ignored" — refused, so nobody believes they changed it."""
    version = db.scalars(select(UnitPriceVersion)).one()

    response = finance_client.patch(
        f"{pricing_url(project_id)}/price-versions/{version.id}",
        json={"valid_from": "2027-01-01"},
    )

    assert response.status_code == 422


def test_bulk_activation_cannot_change_the_effective_date(
    cfo_client: TestClient, project_id: str, priced_unit: str
) -> None:
    """Activation publishes the date the price was calculated for, and no other."""
    response = cfo_client.post(
        f"{pricing_url(project_id)}/price-versions/activate",
        json={"version_ids": [priced_unit], "valid_from": "2027-01-01"},
    )

    assert response.status_code == 422


def test_activation_keeps_the_date_the_price_was_calculated_for(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    active_configuration: str,
) -> None:
    approve_areas(admin_client, project_id, unit_id, area_types)
    future = (business_today() + timedelta(days=30)).isoformat()
    version = _draft(finance_client, project_id, unit_id, valid_from=future)

    assert version["valid_from"] == future
    _put_live(finance_client, cfo_client, project_id, version["id"])

    live = finance_client.get(f"{pricing_url(project_id)}/price-versions/{version['id']}").json()
    assert live["valid_from"] == future


def test_a_date_escalation_is_selected_by_the_frozen_effective_date(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    currency_id: str,
    db: Session,
) -> None:
    """A future-dated price carries only the escalations in force by its own date.

    The activation lands a fortnight out. A price effective today must not have
    it; a price effective a month out must. Both are calculated from the same
    rules on the same afternoon, and the only thing separating them is the date
    the caller asked for — which is exactly what "the effective date is a
    calculation input" means.
    """
    approve_areas(admin_client, project_id, unit_id, area_types)
    _, rule = _configuration_with_date_escalation(
        finance_client, cfo_client, project_id, currency_id, area_types
    )
    fortnight = business_today() + timedelta(days=14)
    activated = cfo_client.post(
        f"{pricing_url(project_id)}/escalation-rules/{rule}/activate",
        json={
            "effective_date": fortnight.isoformat(),
            "evidence_reference": "Board minute 12",
            "reason": "Launch phase closed",
        },
    )
    assert activated.status_code == 201, activated.text

    today_price = _draft(finance_client, project_id, unit_id)
    later_price = _draft(
        finance_client,
        project_id,
        unit_id,
        valid_from=(business_today() + timedelta(days=30)).isoformat(),
    )

    assert today_price["escalation_total"] == "0.00"
    assert later_price["escalation_total"] == "8250.00"
    assert today_price["reference_price_ex_tax"] == "165000.00"
    assert later_price["reference_price_ex_tax"] == "173250.00"


def _configuration_with_date_escalation(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    currency_id: str,
    area_types: dict[str, str],
) -> tuple[str, str]:
    """A live policy carrying one activatable 5% date escalation.

    Built the way an operator has to build it: rules are written on a draft, and
    an activation is recorded against the configuration once it is live.
    """
    created = finance_client.post(
        f"{pricing_url(project_id)}/configurations", json=configuration_payload(currency_id)
    )
    assert created.status_code == 201, created.text
    configuration = created.json()["id"]
    base = f"{pricing_url(project_id)}/configurations/{configuration}"
    for area_type_id, method, extra in (
        (area_types["INTERNAL"], "internal_base", {}),
        (area_types["BALCONY"], "factor_of_internal_rate", {"internal_rate_factor": "0.500000"}),
    ):
        rule = finance_client.post(
            f"{base}/area-rules",
            json={"area_type_id": area_type_id, "pricing_method": method, **extra},
        )
        assert rule.status_code == 201, rule.text
    escalation = finance_client.post(
        f"{base}/escalation-rules",
        json={
            "code": "LAUNCH",
            "label": "Post-launch uplift",
            "trigger_type": "date",
            "threshold_date": (business_today() + timedelta(days=14)).isoformat(),
            "adjustment_method": "percentage",
            "adjustment_percentage_fraction": "0.050000",
        },
    )
    assert escalation.status_code == 201, escalation.text
    assert finance_client.post(f"{base}/submit", json={}).status_code == 200
    assert cfo_client.post(f"{base}/approve", json={"reason": "Reviewed"}).status_code == 200
    assert cfo_client.post(f"{base}/activate").status_code == 200
    return configuration, escalation.json()["id"]


# --------------------------------------------------------------------------- #
# Configuration validity
# --------------------------------------------------------------------------- #


def test_a_price_before_the_configuration_validity_is_refused(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    active_configuration: str,
) -> None:
    """A policy adopted in January did not produce December's price."""
    approve_areas(admin_client, project_id, unit_id, area_types)

    response = finance_client.post(
        f"{pricing_url(project_id)}/units/{unit_id}/price-versions",
        json={"valid_from": "2025-12-01"},
    )

    assert response.status_code == 409
    assert "takes effect on 2026-01-01" in response.json()["detail"]


def test_a_price_after_the_configuration_validity_is_refused(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
    currency_id: str,
    area_types: dict[str, str],
) -> None:
    approve_areas(admin_client, project_id, unit_id, area_types)
    # A window that is open today — it has to be, or the policy could not have
    # been activated — and closes in a month.
    closes = business_today() + timedelta(days=30)
    _live_configuration(
        finance_client,
        cfo_client,
        project_id,
        currency_id,
        area_types,
        valid_from="2026-01-01",
        valid_to=closes.isoformat(),
    )

    response = finance_client.post(
        f"{pricing_url(project_id)}/units/{unit_id}/price-versions",
        json={"valid_from": (closes + timedelta(days=1)).isoformat()},
    )

    assert response.status_code == 409
    assert f"ended on {closes.isoformat()}" in response.json()["detail"]


def test_a_configuration_cannot_activate_before_its_valid_from(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    currency_id: str,
    area_types: dict[str, str],
) -> None:
    """A future policy waits for a person, not for a clock.

    It stays approved and activatable the day it becomes eligible. Nothing in
    this module runs on its own, so the alternative to refusing here would be a
    scheduler putting a price policy live overnight with nobody's name on it.
    """
    configuration = _draft_configuration(
        finance_client,
        project_id,
        currency_id,
        area_types,
        valid_from=(business_today() + timedelta(days=90)).isoformat(),
    )
    base = f"{pricing_url(project_id)}/configurations/{configuration}"
    assert finance_client.post(f"{base}/submit", json={}).status_code == 200
    assert cfo_client.post(f"{base}/approve", json={"reason": "Next season"}).status_code == 200

    response = cfo_client.post(f"{base}/activate")

    assert response.status_code == 409
    assert "takes effect on" in response.json()["detail"]


def _draft_configuration(
    finance_client: TestClient,
    project_id: str,
    currency_id: str,
    area_types: dict[str, str],
    **overrides: object,
) -> str:
    created = finance_client.post(
        f"{pricing_url(project_id)}/configurations",
        json=configuration_payload(currency_id, **overrides),
    )
    assert created.status_code == 201, created.text
    configuration = created.json()["id"]
    for area_type_id, method, extra in (
        (area_types["INTERNAL"], "internal_base", {}),
        (area_types["BALCONY"], "factor_of_internal_rate", {"internal_rate_factor": "0.500000"}),
    ):
        rule = finance_client.post(
            f"{pricing_url(project_id)}/configurations/{configuration}/area-rules",
            json={"area_type_id": area_type_id, "pricing_method": method, **extra},
        )
        assert rule.status_code == 201, rule.text
    return configuration


def _live_configuration(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    currency_id: str,
    area_types: dict[str, str],
    **overrides: object,
) -> str:
    configuration = _draft_configuration(
        finance_client, project_id, currency_id, area_types, **overrides
    )
    base = f"{pricing_url(project_id)}/configurations/{configuration}"
    assert finance_client.post(f"{base}/submit", json={}).status_code == 200
    assert cfo_client.post(f"{base}/approve", json={"reason": "Reviewed"}).status_code == 200
    assert cfo_client.post(f"{base}/activate").status_code == 200
    return configuration


# --------------------------------------------------------------------------- #
# The market flag follows the final price
# --------------------------------------------------------------------------- #


def _benchmark(
    finance_client: TestClient,
    project_id: str,
    currency_id: str,
    *,
    price: str = "1650.00",
    tolerance: str = "0.100000",
) -> str:
    response = finance_client.post(
        f"{pricing_url(project_id)}/market-benchmarks",
        json={
            "area_basis": "internal",
            "benchmark_price_per_area": price,
            "currency_id": currency_id,
            "comparison_date": "2026-01-15",
            "source_name": "Agency survey",
            "source_reference": "Q1-2026",
            "tolerance_fraction": tolerance,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_an_override_moves_the_market_flag_with_the_price(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    currency_id: str,
    area_types: dict[str, str],
    active_configuration: str,
) -> None:
    """Within tolerance at 165,000 is not within tolerance at 220,000.

    The waterfall recalculates on an override and always did; the market
    comparison did not, so a price a person had pushed 33% above the benchmark
    could still be sitting under a green "within tolerance" chip on the screen
    the approver decides from.
    """
    approve_areas(admin_client, project_id, unit_id, area_types)
    _benchmark(finance_client, project_id, currency_id)
    draft = _draft(finance_client, project_id, unit_id)

    assert draft["market_flag"] == "within_tolerance"
    assert draft["reference_price_ex_tax"] == "165000.00"

    overridden = finance_client.patch(
        f"{pricing_url(project_id)}/price-versions/{draft['id']}",
        json={
            "overrides": [
                {
                    "sequence": 1,
                    "override_amount": "205000.00",
                    "override_reason": "Corner premium agreed with the board",
                }
            ]
        },
    )

    assert overridden.status_code == 200, overridden.text
    body = overridden.json()
    assert body["reference_price_ex_tax"] == "220000.00"
    assert body["market_flag"] == "above_tolerance"
    # 220,000 over 100 sqm is 2,200 against a 1,650 benchmark: one third above.
    assert body["market_deviation_fraction"] == "0.333333"


def test_removing_an_override_restores_the_classification(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    currency_id: str,
    area_types: dict[str, str],
    active_configuration: str,
) -> None:
    approve_areas(admin_client, project_id, unit_id, area_types)
    _benchmark(finance_client, project_id, currency_id)
    draft = _draft(finance_client, project_id, unit_id)
    base = f"{pricing_url(project_id)}/price-versions/{draft['id']}"
    finance_client.patch(
        base,
        json={
            "overrides": [
                {
                    "sequence": 1,
                    "override_amount": "205000.00",
                    "override_reason": "Board agreed",
                }
            ]
        },
    )

    restored = finance_client.patch(base, json={"overrides": [{"sequence": 1}]})

    assert restored.status_code == 200, restored.text
    assert restored.json()["reference_price_ex_tax"] == "165000.00"
    assert restored.json()["market_flag"] == "within_tolerance"


def test_a_later_benchmark_revision_does_not_rewrite_a_frozen_observation(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    currency_id: str,
    area_types: dict[str, str],
    active_configuration: str,
) -> None:
    """The comparison an approver was shown is the comparison that stays recorded.

    Benchmarks are governed configuration that people revise. Following the live
    row would silently restate every historical price's market position each
    time somebody updated a survey, and "within tolerance" would stop being a
    statement about any decision that was actually made.
    """
    approve_areas(admin_client, project_id, unit_id, area_types)
    benchmark = _benchmark(finance_client, project_id, currency_id)
    draft = _draft(finance_client, project_id, unit_id)
    assert draft["market_flag"] == "within_tolerance"

    revised = finance_client.patch(
        f"{pricing_url(project_id)}/market-benchmarks/{benchmark}",
        json={"benchmark_price_per_area": "900.00", "notes": "Corrected survey"},
    )
    assert revised.status_code == 200, revised.text

    unchanged = finance_client.get(f"{pricing_url(project_id)}/price-versions/{draft['id']}").json()

    assert unchanged["market_benchmark_price_snapshot"] == "1650.00"
    assert unchanged["market_flag"] == "within_tolerance"
    observation = unchanged["basis_snapshot_json"]["market_benchmark"]
    assert observation["benchmark_price_per_area"] == "1650.00"
    assert observation["source_name"] == "Agency survey"
    assert observation["comparison_date"] == "2026-01-15"


def test_the_frozen_observation_survives_submission_and_approval(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
    currency_id: str,
    area_types: dict[str, str],
    active_configuration: str,
) -> None:
    """An overridden draft reaches the approver with a flag that matches its price."""
    approve_areas(admin_client, project_id, unit_id, area_types)
    _benchmark(finance_client, project_id, currency_id)
    draft = _draft(finance_client, project_id, unit_id)
    finance_client.patch(
        f"{pricing_url(project_id)}/price-versions/{draft['id']}",
        json={
            "overrides": [
                {"sequence": 1, "override_amount": "205000.00", "override_reason": "Board agreed"}
            ]
        },
    )

    _put_live(finance_client, cfo_client, project_id, draft["id"])

    live = finance_client.get(f"{pricing_url(project_id)}/price-versions/{draft['id']}").json()
    assert live["status"] == "active"
    assert live["market_flag"] == "above_tolerance"
    assert live["reference_price_ex_tax"] == "220000.00"


def test_activation_refuses_a_market_flag_that_does_not_match_the_price(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
    currency_id: str,
    area_types: dict[str, str],
    active_configuration: str,
    db: Session,
) -> None:
    """The backstop behind the recalculation, met by a write past the service.

    From submission onwards a version is immutable, so a classification that no
    longer follows from the price means something wrote to a row that should
    have been closed. Activation refuses rather than publishing it.
    """
    approve_areas(admin_client, project_id, unit_id, area_types)
    _benchmark(finance_client, project_id, currency_id)
    draft = _draft(finance_client, project_id, unit_id)
    base = f"{pricing_url(project_id)}/price-versions/{draft['id']}"
    assert finance_client.post(f"{base}/submit", json={}).status_code == 200
    assert cfo_client.post(f"{base}/approve", json={"reason": "Reviewed"}).status_code == 200

    db.execute(
        text("UPDATE unit_price_versions SET market_flag = 'above_tolerance' WHERE id = :id"),
        {"id": draft["id"]},
    )
    db.commit()

    response = cfo_client.post(f"{base}/activate")

    assert response.status_code == 409
    assert "market comparison does not match" in response.json()["detail"]


# --------------------------------------------------------------------------- #
# A stale price is readable, not quotable
# --------------------------------------------------------------------------- #


def _quote(client: TestClient, project_id: str, unit_id: str) -> Response:
    return client.post(
        f"{pricing_url(project_id)}/units/{unit_id}/quote-preview",
        json={"discount_fraction": "0.000000"},
    )


def test_a_stale_active_price_is_readable_but_not_quotable(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
    priced_unit: str,
) -> None:
    """The whole arc: quotable, changed, refused, repriced, quotable again.

    Inventory withdraws the pricing approval when a priced fact moves, and the
    register says "repricing required". Without this check Sales could still
    produce a live commercial offer from that same withdrawn price — the release
    gate closed and the quote button carried on regardless.
    """
    assert _quote(finance_client, project_id, unit_id).status_code == 200

    admin_client.patch(
        f"{inventory_url(project_id)}/units/{unit_id}", json={"view_class_code": "SEA"}
    )

    refused = _quote(finance_client, project_id, unit_id)
    assert refused.status_code == 409
    assert refused.json()["detail"] == (
        "This unit requires repricing before a quote can be prepared."
    )

    # The historical price is untouched: it is what the unit was offered at.
    history = _versions(finance_client, project_id, unit_id)
    assert [item["status"] for item in history] == ["active"]
    assert history[0]["reference_price_ex_tax"] == "165000.00"
    unit_view = finance_client.get(f"{pricing_url(project_id)}/units/{unit_id}").json()
    assert unit_view["repricing_required"] is True

    _reprice(admin_client, finance_client, cfo_client, project_id, unit_id)

    assert _quote(finance_client, project_id, unit_id).status_code == 200


def test_a_label_correction_alone_does_not_block_quoting(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    priced_unit: str,
) -> None:
    """The other half of the rule: harmless corrections stay harmless."""
    corrected = admin_client.patch(
        f"{inventory_url(project_id)}/units/{unit_id}", json={"unit_reference": "A1-101"}
    )
    assert corrected.status_code == 200, corrected.text

    response = _quote(finance_client, project_id, unit_id)

    assert response.status_code == 200, response.text
    assert response.json()["unit_reference"] == "A1-101"


def test_an_area_reapproval_blocks_quoting_until_repriced(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    priced_unit: str,
) -> None:
    approve_areas(admin_client, project_id, unit_id, area_types, revision="R1", internal="120.0000")

    response = _quote(finance_client, project_id, unit_id)

    assert response.status_code == 409


# --------------------------------------------------------------------------- #
# Explicit bulk selection is exact
# --------------------------------------------------------------------------- #


def _extra_unit(admin_client: TestClient, project_id: str, floor_id: str, number: str) -> str:
    response = admin_client.post(
        f"{inventory_url(project_id)}/units",
        json=unit_payload(floor_id, unit_number=number, unit_reference=f"B1-{number}"),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.fixture
def three_measured_units(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    floor_id: str,
    area_types: dict[str, str],
) -> list[str]:
    units = [unit_id]
    for number in ("102", "103"):
        units.append(_extra_unit(admin_client, project_id, floor_id, number))
    for identifier in units:
        approve_areas(admin_client, project_id, identifier, area_types)
    return units


def test_three_valid_identifiers_price_three_units(
    finance_client: TestClient,
    project_id: str,
    three_measured_units: list[str],
    active_configuration: str,
) -> None:
    response = finance_client.post(
        f"{pricing_url(project_id)}/price-versions/generate",
        json={"unit_ids": three_measured_units},
    )

    assert response.status_code == 201, response.text
    assert len(response.json()) == 3


def test_one_unavailable_identifier_prices_nothing(
    finance_client: TestClient,
    project_id: str,
    three_measured_units: list[str],
    active_configuration: str,
    db: Session,
) -> None:
    """All or none. Ninety-nine drafts from a hundred identifiers is a price list
    that looks complete and is not."""
    response = finance_client.post(
        f"{pricing_url(project_id)}/price-versions/generate",
        json={"unit_ids": [*three_measured_units, "11111111-1111-4111-8111-111111111111"]},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "One or more selected units are unavailable."
    assert db.scalars(select(UnitPriceVersion)).all() == []


def test_a_duplicated_identifier_is_refused(
    finance_client: TestClient,
    project_id: str,
    three_measured_units: list[str],
    active_configuration: str,
    db: Session,
) -> None:
    """Named twice is a request nobody meant to send, not a unit priced twice."""
    response = finance_client.post(
        f"{pricing_url(project_id)}/price-versions/generate",
        json={"unit_ids": [three_measured_units[0], three_measured_units[0]]},
    )

    assert response.status_code == 422
    assert "more than once" in response.json()["detail"]
    assert db.scalars(select(UnitPriceVersion)).all() == []


def test_a_unit_of_another_project_prices_nothing(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    three_measured_units: list[str],
    active_configuration: str,
    db: Session,
) -> None:
    """Refused the same way and with the same words as a unit that does not exist."""
    other = admin_client.post(
        f"{PROJECTS}",
        json=_second_project_payload(admin_client, project_id),
    )
    assert other.status_code == 201, other.text

    response = finance_client.post(
        f"{pricing_url(project_id)}/price-versions/generate",
        json={"unit_ids": [*three_measured_units, other.json()["id"]]},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "One or more selected units are unavailable."
    assert db.scalars(select(UnitPriceVersion)).all() == []


def _second_project_payload(admin_client: TestClient, project_id: str) -> dict[str, Any]:
    existing = admin_client.get(f"{PROJECTS}/{project_id}").json()
    return {
        "code": "SECOND-DEV",
        "name": "Second development",
        "developer_entity": "Reach Developments",
        "country_pack_id": existing["country_pack_id"],
        "city": "Amman",
        "project_type_code": "RESIDENTIAL",
        "base_currency_id": existing["base_currency_id"],
        "reporting_currency_id": existing["reporting_currency_id"],
        "fiscal_year_start_month": 1,
    }


def test_a_phase_filter_alone_still_narrows(
    finance_client: TestClient,
    project_id: str,
    phase_id: str,
    three_measured_units: list[str],
    active_configuration: str,
) -> None:
    """A filter narrows in SQL and is not held to the explicit-set contract."""
    response = finance_client.post(
        f"{pricing_url(project_id)}/price-versions/generate", json={"phase_id": phase_id}
    )

    assert response.status_code == 201, response.text
    assert len(response.json()) == 3


# --------------------------------------------------------------------------- #
# Reconciliation
# --------------------------------------------------------------------------- #


def test_every_component_total_still_reconciles_exactly(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    currency_id: str,
    area_types: dict[str, str],
    active_configuration: str,
) -> None:
    """The lines a reader sees add up to the total they see — after an override too."""
    approve_areas(admin_client, project_id, unit_id, area_types)
    _benchmark(finance_client, project_id, currency_id)
    draft = _draft(finance_client, project_id, unit_id)
    finance_client.patch(
        f"{pricing_url(project_id)}/price-versions/{draft['id']}",
        json={
            "overrides": [
                {"sequence": 2, "override_amount": "9000.00", "override_reason": "Balcony agreed"}
            ]
        },
    )

    detail = finance_client.get(f"{pricing_url(project_id)}/price-versions/{draft['id']}").json()

    lines = sum(Decimal(component["final_amount"]) for component in detail["components"])
    assert str(lines) == detail["reference_price_ex_tax"]
    assert detail["reference_price_ex_tax"] == "159000.00"


def test_a_price_effective_today_sits_inside_its_configuration_window(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    active_configuration: str,
) -> None:
    """The ordinary case still works: today is inside a window opened in January."""
    approve_areas(admin_client, project_id, unit_id, area_types)

    draft = _draft(finance_client, project_id, unit_id)

    assert date.fromisoformat(draft["valid_from"]) >= date(2026, 1, 1)
