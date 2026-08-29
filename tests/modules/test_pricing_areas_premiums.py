"""Area pricing and premiums: what a unit costs, and why each line is there.

Two rules run through everything here. Areas are priced from the unit's
**current approved** measurement and from nothing else — not a draft, not a
superseded revision, not a weighted figure standing in for a legal one. And a
premium matches on a fixed list of real facts about the unit; there is no field
name, no operator and nothing anywhere that gets evaluated.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.access.models import User
from app.modules.inventory.models import Unit, UnitAreaSchedule
from tests.modules.conftest import PROJECTS, approve_areas, inventory_url, pricing_url


def _premium(client: TestClient, project_id: str, configuration_id: str, **body: object) -> dict:
    response = client.post(
        f"{pricing_url(project_id)}/configurations/{configuration_id}/premium-rules", json=body
    )
    assert response.status_code == 201, response.text
    return response.json()


def _draft(client: TestClient, project_id: str, unit_id: str) -> dict:
    response = client.post(f"{pricing_url(project_id)}/units/{unit_id}/price-versions", json={})
    assert response.status_code == 201, response.text
    return response.json()


def _amount(version: dict, code: str) -> Decimal | None:
    for component in version["components"]:
        if component["code"] == code:
            return Decimal(component["final_amount"])
    return None


# --------------------------------------------------------------------------- #
# Areas
# --------------------------------------------------------------------------- #


def test_a_unit_with_no_approved_measurement_cannot_be_priced(
    finance_client: TestClient, project_id: str, unit_id: str, active_configuration: str
) -> None:
    """There is no price without an area, and no area without an approval."""
    response = finance_client.post(
        f"{pricing_url(project_id)}/units/{unit_id}/price-versions", json={}
    )

    assert response.status_code == 409
    assert "approved area schedule" in response.json()["detail"]


def test_a_draft_measurement_is_not_priced_from(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    active_configuration: str,
) -> None:
    """Given only an unapproved revision, then pricing refuses rather than guesses."""
    created = admin_client.post(
        f"{inventory_url(project_id)}/units/{unit_id}/area-schedules",
        json={
            "revision_code": "R0",
            "reconciled": True,
            "values": [{"area_type_id": area_types["INTERNAL"], "raw_area": "100.0000"}],
        },
    )
    assert created.status_code == 201

    response = finance_client.post(
        f"{pricing_url(project_id)}/units/{unit_id}/price-versions", json={}
    )

    assert response.status_code == 409


def test_the_price_shows_each_area_its_rate_and_what_it_contributed(
    finance_client: TestClient, project_id: str, unit_id: str, priced_unit: str
) -> None:
    """A total with no lines beneath it is the spreadsheet cell this replaces."""
    version = finance_client.get(f"{pricing_url(project_id)}/price-versions/{priced_unit}").json()

    internal, balcony = version["components"][0], version["components"][1]
    assert (internal["quantity"], internal["rate"], internal["final_amount"]) == (
        "100.0000",
        "1500.00",
        "150000.00",
    )
    assert (balcony["quantity"], balcony["rate"], balcony["factor"]) == (
        "20.0000",
        "750.00",
        "0.500000",
    )
    assert version["reference_price_ex_tax"] == "165000.00"


def test_the_price_freezes_the_area_schedule_it_used(
    finance_client: TestClient, project_id: str, unit_id: str, priced_unit: str, db: Session
) -> None:
    version = finance_client.get(f"{pricing_url(project_id)}/price-versions/{priced_unit}").json()
    schedule = db.scalars(select(UnitAreaSchedule)).one()

    assert version["unit_area_schedule_id"] == str(schedule.id)
    assert version["basis_snapshot_json"]["unit_basis"]["area_schedule"]["revision_code"] == "R0"
    assert version["basis_snapshot_json"]["unit_basis"]["areas"]["INTERNAL"] == "100.0000"


def test_an_area_type_with_no_rule_contributes_nothing_and_no_line(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    active_configuration: str,
) -> None:
    """An unpriced area is configuration, not a silent zero in a total."""
    terrace = admin_client.post(
        f"{inventory_url(project_id)}/area-types",
        json={
            "code": "TERRACE",
            "label": "Terrace",
            "area_role": "outdoor",
            "weight_factor": "0.500000",
        },
    ).json()["id"]
    created = admin_client.post(
        f"{inventory_url(project_id)}/units/{unit_id}/area-schedules",
        json={
            "revision_code": "R0",
            "reconciled": True,
            "values": [
                {"area_type_id": area_types["INTERNAL"], "raw_area": "100.0000"},
                {"area_type_id": terrace, "raw_area": "30.0000"},
            ],
        },
    ).json()["id"]
    admin_client.post(
        f"{inventory_url(project_id)}/units/{unit_id}/area-schedules/{created}/approve"
    )

    version = _draft(finance_client, project_id, unit_id)

    assert [component["code"] for component in version["components"]] == ["INTERNAL"]
    assert version["reference_price_ex_tax"] == "150000.00"


def test_one_configuration_prices_one_internal_base(
    finance_client: TestClient,
    project_id: str,
    draft_configuration: str,
    area_types: dict[str, str],
) -> None:
    """Two areas quoted at the headline rate is two answers to one question."""
    response = finance_client.post(
        f"{pricing_url(project_id)}/configurations/{draft_configuration}/area-rules",
        json={"area_type_id": area_types["BALCONY"], "pricing_method": "internal_base"},
    )

    assert response.status_code == 409


def test_a_fixed_rate_rule_needs_a_rate(
    finance_client: TestClient,
    project_id: str,
    draft_configuration: str,
    area_types: dict[str, str],
) -> None:
    response = finance_client.post(
        f"{pricing_url(project_id)}/configurations/{draft_configuration}/area-rules",
        json={"area_type_id": area_types["BALCONY"], "pricing_method": "fixed_rate_per_area"},
    )

    assert response.status_code == 422
    assert "rate_per_area" in response.json()["detail"]


def test_area_rules_of_an_active_configuration_cannot_be_edited(
    finance_client: TestClient, project_id: str, active_configuration: str
) -> None:
    rules = finance_client.get(
        f"{pricing_url(project_id)}/configurations/{active_configuration}/area-rules"
    ).json()

    response = finance_client.patch(
        f"{pricing_url(project_id)}/area-rules/{rules[0]['id']}", json={"sort_order": 5}
    )

    assert response.status_code == 409


# --------------------------------------------------------------------------- #
# Premiums
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("source_kind", "match_code", "unit_field", "unit_value", "starting_value"),
    [
        ("view_class", "SEA", "view_class_code", "SEA", None),
        ("floor_band", "MID", "floor_band_code", "MID", None),
        ("orientation", "NORTH", "orientation_code", "NORTH", None),
        # The unit fixture is already a 2BR, so this case has to start somewhere
        # else to prove the premium is matching rather than always applying.
        ("unit_type", "2BR", "unit_type_code", "2BR", "3BR"),
        ("accessibility", "STEP_FREE", "accessibility_code", "STEP_FREE", None),
        ("garden_class", "PRIVATE", "garden_class_code", "PRIVATE", None),
    ],
)
def test_a_coded_premium_applies_only_when_the_code_matches(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    draft_configuration: str,
    cfo_client: TestClient,
    source_kind: str,
    match_code: str,
    unit_field: str,
    unit_value: str,
    starting_value: str | None,
) -> None:
    """Given a unit that carries the code, then the premium is on the price.

    Parametrised over every coded source the module supports, because a matching
    table is exactly the kind of code where one branch quietly reads the wrong
    column and nobody notices until a quote is wrong.
    """
    _premium(
        finance_client,
        project_id,
        draft_configuration,
        code="P1",
        label=f"{source_kind} premium",
        source_kind=source_kind,
        match_code=match_code,
        method="fixed",
        amount="5000.00",
    )
    base = f"{pricing_url(project_id)}/configurations/{draft_configuration}"
    finance_client.post(f"{base}/submit", json={})
    cfo_client.post(f"{base}/approve", json={"reason": "ok"})
    cfo_client.post(f"{base}/activate")
    approve_areas(admin_client, project_id, unit_id, area_types)
    if starting_value is not None:
        admin_client.patch(
            f"{inventory_url(project_id)}/units/{unit_id}", json={unit_field: starting_value}
        )

    without = _draft(finance_client, project_id, unit_id)
    admin_client.patch(
        f"{inventory_url(project_id)}/units/{unit_id}", json={unit_field: unit_value}
    )
    with_it = _draft(finance_client, project_id, unit_id)

    assert _amount(without, "P1") is None
    assert _amount(with_it, "P1") == Decimal("5000.00")


def test_a_boolean_premium_reads_the_flag_and_takes_no_code(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    draft_configuration: str,
) -> None:
    refused = finance_client.post(
        f"{pricing_url(project_id)}/configurations/{draft_configuration}/premium-rules",
        json={
            "code": "CORNER",
            "label": "Corner",
            "source_kind": "corner",
            "match_code": "YES",
            "method": "fixed",
            "amount": "10000.00",
        },
    )
    _premium(
        finance_client,
        project_id,
        draft_configuration,
        code="CORNER",
        label="Corner unit",
        source_kind="corner",
        method="fixed",
        amount="10000.00",
    )
    base = f"{pricing_url(project_id)}/configurations/{draft_configuration}"
    finance_client.post(f"{base}/submit", json={})
    cfo_client.post(f"{base}/approve", json={"reason": "ok"})
    cfo_client.post(f"{base}/activate")
    approve_areas(admin_client, project_id, unit_id, area_types)
    admin_client.patch(f"{inventory_url(project_id)}/units/{unit_id}", json={"is_corner": True})

    version = _draft(finance_client, project_id, unit_id)

    assert refused.status_code == 422
    assert _amount(version, "CORNER") == Decimal("10000.00")


def test_a_per_asset_premium_counts_the_linked_sub_assets(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
    floor_id: str,
    area_types: dict[str, str],
    draft_configuration: str,
) -> None:
    """Two bays at 7,500 is 15,000, counted from the rows rather than a column."""
    _premium(
        finance_client,
        project_id,
        draft_configuration,
        code="PARKING",
        label="Covered parking",
        source_kind="parking",
        method="fixed_per_asset",
        amount="7500.00",
    )
    base = f"{pricing_url(project_id)}/configurations/{draft_configuration}"
    finance_client.post(f"{base}/submit", json={})
    cfo_client.post(f"{base}/approve", json={"reason": "ok"})
    cfo_client.post(f"{base}/activate")
    approve_areas(admin_client, project_id, unit_id, area_types)
    for index in (1, 2):
        created = admin_client.post(
            f"{inventory_url(project_id)}/sub-assets",
            json={
                "asset_reference": f"P-{index}",
                "asset_type": "parking",
                "floor_id": floor_id,
                "linked_unit_id": unit_id,
            },
        )
        assert created.status_code == 201, created.text

    version = _draft(finance_client, project_id, unit_id)

    line = next(item for item in version["components"] if item["code"] == "PARKING")
    assert (line["quantity"], line["rate"], line["final_amount"]) == (
        "2.0000",
        "7500.00",
        "15000.00",
    )
    assert line["component_type"] == "sub_asset_premium"


def test_a_per_area_premium_multiplies_the_area_it_names(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    draft_configuration: str,
) -> None:
    _premium(
        finance_client,
        project_id,
        draft_configuration,
        code="BALPREM",
        label="Balcony premium",
        source_kind="area_type",
        match_code="BALCONY",
        method="per_area",
        amount="150.00",
    )
    base = f"{pricing_url(project_id)}/configurations/{draft_configuration}"
    finance_client.post(f"{base}/submit", json={})
    cfo_client.post(f"{base}/approve", json={"reason": "ok"})
    cfo_client.post(f"{base}/activate")
    approve_areas(admin_client, project_id, unit_id, area_types)

    version = _draft(finance_client, project_id, unit_id)

    assert _amount(version, "BALPREM") == Decimal("3000.00")


def test_an_inactive_rule_does_not_apply(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    draft_configuration: str,
) -> None:
    rule = _premium(
        finance_client,
        project_id,
        draft_configuration,
        code="VIEW",
        label="Sea view",
        source_kind="view_class",
        match_code="SEA",
        method="fixed",
        amount="5000.00",
    )
    finance_client.patch(
        f"{pricing_url(project_id)}/premium-rules/{rule['id']}", json={"is_active": False}
    )
    base = f"{pricing_url(project_id)}/configurations/{draft_configuration}"
    finance_client.post(f"{base}/submit", json={})
    cfo_client.post(f"{base}/approve", json={"reason": "ok"})
    cfo_client.post(f"{base}/activate")
    approve_areas(admin_client, project_id, unit_id, area_types)
    admin_client.patch(
        f"{inventory_url(project_id)}/units/{unit_id}", json={"view_class_code": "SEA"}
    )

    version = _draft(finance_client, project_id, unit_id)

    assert _amount(version, "VIEW") is None


def test_a_premium_naming_a_phase_the_project_does_not_have_is_refused(
    finance_client: TestClient, project_id: str, draft_configuration: str
) -> None:
    """A rule that could never match is a rule somebody meant to write differently."""
    response = finance_client.post(
        f"{pricing_url(project_id)}/configurations/{draft_configuration}/premium-rules",
        json={
            "code": "PH9",
            "label": "Phase 9",
            "source_kind": "phase",
            "match_code": "PHASE-9",
            "method": "fixed",
            "amount": "1000.00",
        },
    )

    assert response.status_code == 422
    assert "not a phase" in response.json()["detail"]


def test_a_per_area_premium_must_read_an_area_type(
    finance_client: TestClient, project_id: str, draft_configuration: str
) -> None:
    response = finance_client.post(
        f"{pricing_url(project_id)}/configurations/{draft_configuration}/premium-rules",
        json={
            "code": "ODD",
            "label": "Odd",
            "source_kind": "corner",
            "method": "per_area",
            "amount": "10.00",
        },
    )

    assert response.status_code == 422
    assert "area type" in response.json()["detail"]


def test_a_percentage_premium_may_not_also_carry_an_amount(
    finance_client: TestClient, project_id: str, draft_configuration: str
) -> None:
    """One number per method. A rule holding both is a rule read two ways."""
    response = finance_client.post(
        f"{pricing_url(project_id)}/configurations/{draft_configuration}/premium-rules",
        json={
            "code": "BOTH",
            "label": "Both",
            "source_kind": "corner",
            "method": "percentage",
            "percentage_fraction": "0.050000",
            "amount": "1000.00",
        },
    )

    assert response.status_code == 422


def test_the_premium_cap_is_visible_in_the_breakdown(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    draft_configuration: str,
    db: Session,
) -> None:
    """Given premiums above the ceiling, then the refused amount is its own line."""
    for index, amount in enumerate(("25000.00", "20000.00"), start=1):
        _premium(
            finance_client,
            project_id,
            draft_configuration,
            code=f"P{index}",
            label=f"Premium {index}",
            source_kind="corner" if index == 1 else "pool_access",
            method="fixed",
            amount=amount,
            sequence=index,
        )
    base = f"{pricing_url(project_id)}/configurations/{draft_configuration}"
    finance_client.post(f"{base}/submit", json={})
    cfo_client.post(f"{base}/approve", json={"reason": "ok"})
    cfo_client.post(f"{base}/activate")
    approve_areas(admin_client, project_id, unit_id, area_types)
    admin_client.patch(
        f"{inventory_url(project_id)}/units/{unit_id}",
        json={"is_corner": True, "pool_access": True},
    )

    version = _draft(finance_client, project_id, unit_id)

    # 165,000 of area at a 20% ceiling caps premiums at 33,000 of the 45,000
    # configured, so 12,000 is refused and printed as refused.
    assert _amount(version, "PREMIUM_CAP") == Decimal("-12000.00")
    assert version["premium_total"] == "33000.00"
    assert version["reference_price_ex_tax"] == "198000.00"
    assert sum(
        Decimal(component["final_amount"]) for component in version["components"]
    ) == Decimal(version["reference_price_ex_tax"])


def test_a_unit_in_a_hidden_phase_cannot_be_priced(
    admin_client: TestClient,
    finance: User,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    active_configuration: str,
    db: Session,
) -> None:
    """Phase access narrows pricing exactly as it narrows inventory: 404.

    Narrowed to no phases at all, so the unit's phase is not among them. The
    refusal is 404 rather than 403 for the same reason inventory chose it: a 403
    confirms the identifier names a real unit of a real project.
    """
    from tests.factories import client_for

    scoped = admin_client.patch(
        f"{PROJECTS}/{project_id}/access/{finance.id}/phase-scope",
        json={"phase_scope": "selected"},
    )
    assert scoped.status_code == 200, scoped.text
    client = client_for(finance.email)

    response = client.get(f"{pricing_url(project_id)}/units/{unit_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Unit not found."
    assert db.scalars(select(Unit)).one() is not None
