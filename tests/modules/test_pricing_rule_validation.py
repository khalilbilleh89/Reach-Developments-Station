"""Configuration that cannot silently mean nothing.

A pricing rule that never matches is the worst kind of wrong: it saves, it
appears on the configuration screen, it is approved by a CFO, and it prices
nothing at all. Nobody finds out until somebody adds up a price list by hand.

So every rule is checked against the same catalogues the units themselves are
checked against, and every escalation has to carry the fact its trigger is
about. None of this evaluates anything — there is no operator, no expression and
no rules engine here, and these tests are partly about proving that stayed true.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.inventory.custom_fields import business_today
from tests.modules.conftest import (
    PROJECTS,
    approve_areas,
    configuration_payload,
    inventory_url,
    pricing_url,
)

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def _reference_data(inventory_reference_data: None) -> None:
    """Every rule in this file is checked against the project's configured catalogue.

    Declared once here rather than in each test, so a test that is about a
    premium rule reads as being about a premium rule.
    """


def _premium(client: TestClient, project_id: str, configuration: str, **body: object) -> Response:
    payload: dict[str, object] = {
        "code": "PREM",
        "label": "A premium",
        "method": "percentage",
        "percentage_fraction": "0.050000",
    }
    payload.update(body)
    return client.post(
        f"{pricing_url(project_id)}/configurations/{configuration}/premium-rules", json=payload
    )


def _escalation(
    client: TestClient, project_id: str, configuration: str, **body: object
) -> Response:
    payload: dict[str, object] = {
        "code": "ESC",
        "label": "An escalation",
        "adjustment_method": "percentage",
        "adjustment_percentage_fraction": "0.050000",
    }
    payload.update(body)
    return client.post(
        f"{pricing_url(project_id)}/configurations/{configuration}/escalation-rules", json=payload
    )


def _field(admin_client: TestClient, project_id: str, **overrides: object) -> str:
    payload: dict[str, object] = {
        "entity_type": "unit",
        "field_key": "corner_glazing",
        "display_label": "Corner glazing",
        "data_type": "boolean",
        "scope_type": "project",
        "project_id": project_id,
    }
    payload.update(overrides)
    response = admin_client.post(f"{PROJECTS}/{project_id}/field-definitions", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


# --------------------------------------------------------------------------- #
# Premium sources: reference-backed codes
# --------------------------------------------------------------------------- #


def test_a_configured_unit_type_premium_is_accepted(
    finance_client: TestClient, project_id: str, draft_configuration: str
) -> None:
    response = _premium(
        finance_client, project_id, draft_configuration, source_kind="unit_type", match_code="2BR"
    )

    assert response.status_code == 201, response.text


@pytest.mark.parametrize(
    ("source_kind", "match_code"),
    [
        ("unit_type", "4BR"),
        ("view_class", "SEAA_VEIW"),
        ("orientation", "NORTHH"),
        ("floor_band", "PENTHOUSE"),
        ("accessibility", "STEP_FREEE"),
        ("garden_class", "COMMUNAL"),
    ],
)
def test_a_premium_naming_an_unconfigured_code_is_refused(
    finance_client: TestClient,
    project_id: str,
    draft_configuration: str,
    source_kind: str,
    match_code: str,
) -> None:
    """'SEAA_VEIW' saves happily and then prices nothing — the failure that never
    announces itself."""
    response = _premium(
        finance_client,
        project_id,
        draft_configuration,
        source_kind=source_kind,
        match_code=match_code,
    )

    assert response.status_code == 422
    assert "No configured" in response.json()["detail"]


def test_a_premium_naming_a_retired_code_is_refused(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    country_pack_id: str,
    draft_configuration: str,
) -> None:
    """Historical rules keep retired codes; a new rule may not adopt one."""
    values = admin_client.get(
        "/api/v1/settings/reference-values",
        params={"country_pack_id": country_pack_id, "category": "view_class"},
    ).json()
    identifier = next(item["id"] for item in values if item["code"] == "SEA")
    admin_client.patch(f"/api/v1/settings/reference-values/{identifier}", json={"is_active": False})

    response = _premium(
        finance_client, project_id, draft_configuration, source_kind="view_class", match_code="SEA"
    )

    assert response.status_code == 422
    assert "no longer active" in response.json()["detail"]


def test_a_parking_premium_may_name_a_configured_subtype(
    finance_client: TestClient, project_id: str, draft_configuration: str
) -> None:
    response = _premium(
        finance_client,
        project_id,
        draft_configuration,
        source_kind="parking",
        match_code="COVERED",
        method="fixed_per_asset",
        percentage_fraction=None,
        amount="5000.00",
    )

    assert response.status_code == 201, response.text


def test_a_parking_premium_naming_an_unconfigured_subtype_is_refused(
    finance_client: TestClient, project_id: str, draft_configuration: str
) -> None:
    response = _premium(
        finance_client,
        project_id,
        draft_configuration,
        source_kind="parking",
        match_code="UNDERGROUND",
        method="fixed_per_asset",
        percentage_fraction=None,
        amount="5000.00",
    )

    assert response.status_code == 422
    assert "No configured sub_asset_subtype" in response.json()["detail"]


def test_a_parking_premium_without_a_subtype_counts_every_bay(
    finance_client: TestClient, project_id: str, draft_configuration: str
) -> None:
    """Optional, not forbidden: no subtype means any parking bay."""
    response = _premium(
        finance_client,
        project_id,
        draft_configuration,
        source_kind="parking",
        method="fixed_per_asset",
        percentage_fraction=None,
        amount="5000.00",
    )

    assert response.status_code == 201, response.text


# --------------------------------------------------------------------------- #
# Premium sources: custom fields
# --------------------------------------------------------------------------- #


def test_a_boolean_unit_field_can_drive_a_premium(
    admin_client: TestClient, finance_client: TestClient, project_id: str, draft_configuration: str
) -> None:
    definition = _field(admin_client, project_id)

    response = _premium(
        finance_client,
        project_id,
        draft_configuration,
        source_kind="custom_field",
        custom_field_definition_id=definition,
    )

    assert response.status_code == 201, response.text


def test_a_boolean_field_premium_takes_no_option_code(
    admin_client: TestClient, finance_client: TestClient, project_id: str, draft_configuration: str
) -> None:
    definition = _field(admin_client, project_id)

    response = _premium(
        finance_client,
        project_id,
        draft_configuration,
        source_kind="custom_field",
        custom_field_definition_id=definition,
        custom_option_code="YES",
    )

    assert response.status_code == 422
    assert "takes no option code" in response.json()["detail"]


def test_an_option_field_premium_prices_one_named_option(
    admin_client: TestClient, finance_client: TestClient, project_id: str, draft_configuration: str
) -> None:
    definition = _field(
        admin_client,
        project_id,
        field_key="kitchen_package",
        display_label="Kitchen package",
        data_type="option",
        options=[{"code": "STD", "label": "Standard"}, {"code": "LUX", "label": "Luxury"}],
    )

    response = _premium(
        finance_client,
        project_id,
        draft_configuration,
        source_kind="custom_field",
        custom_field_definition_id=definition,
        custom_option_code="LUX",
    )

    assert response.status_code == 201, response.text


def test_an_option_field_premium_needs_an_option_code(
    admin_client: TestClient, finance_client: TestClient, project_id: str, draft_configuration: str
) -> None:
    """Without one there is no unambiguous reading: "any value at all" would fire
    on a comment field."""
    definition = _field(
        admin_client,
        project_id,
        field_key="kitchen_package",
        display_label="Kitchen package",
        data_type="option",
        options=[{"code": "STD", "label": "Standard"}],
    )

    response = _premium(
        finance_client,
        project_id,
        draft_configuration,
        source_kind="custom_field",
        custom_field_definition_id=definition,
    )

    assert response.status_code == 422
    assert "must name the option" in response.json()["detail"]


def test_an_unknown_option_code_is_refused(
    admin_client: TestClient, finance_client: TestClient, project_id: str, draft_configuration: str
) -> None:
    definition = _field(
        admin_client,
        project_id,
        field_key="kitchen_package",
        display_label="Kitchen package",
        data_type="option",
        options=[{"code": "STD", "label": "Standard"}],
    )

    response = _premium(
        finance_client,
        project_id,
        draft_configuration,
        source_kind="custom_field",
        custom_field_definition_id=definition,
        custom_option_code="PREMIUM",
    )

    assert response.status_code == 422
    assert "is not an option" in response.json()["detail"]


def test_a_retired_option_code_is_refused(
    admin_client: TestClient, finance_client: TestClient, project_id: str, draft_configuration: str
) -> None:
    definition = _field(
        admin_client,
        project_id,
        field_key="kitchen_package",
        display_label="Kitchen package",
        data_type="option",
        options=[{"code": "STD", "label": "Standard"}, {"code": "LUX", "label": "Luxury"}],
    )
    admin_client.patch(
        f"{PROJECTS}/{project_id}/field-definitions/{definition}",
        json={"options": [{"code": "STD", "label": "Standard"}]},
    )

    response = _premium(
        finance_client,
        project_id,
        draft_configuration,
        source_kind="custom_field",
        custom_field_definition_id=definition,
        custom_option_code="LUX",
    )

    assert response.status_code == 422


@pytest.mark.parametrize("data_type", ["text", "integer", "decimal", "date"])
def test_a_field_with_no_unambiguous_reading_cannot_drive_a_premium(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    draft_configuration: str,
    data_type: str,
) -> None:
    """ "Ceiling height above 3m" needs a comparison, and a comparison is an
    expression language. There isn't one, so the rule is refused instead of
    stored and never matched."""
    definition = _field(
        admin_client,
        project_id,
        field_key="ceiling_height",
        display_label="Ceiling height",
        data_type=data_type,
    )

    response = _premium(
        finance_client,
        project_id,
        draft_configuration,
        source_kind="custom_field",
        custom_field_definition_id=definition,
    )

    assert response.status_code == 422
    assert "cannot drive a premium" in response.json()["detail"]


def test_a_project_scoped_field_of_another_entity_is_refused(
    admin_client: TestClient, finance_client: TestClient, project_id: str, draft_configuration: str
) -> None:
    definition = _field(
        admin_client,
        project_id,
        entity_type="project",
        field_key="funding_source",
        display_label="Funding source",
    )

    response = _premium(
        finance_client,
        project_id,
        draft_configuration,
        source_kind="custom_field",
        custom_field_definition_id=definition,
    )

    assert response.status_code == 422
    assert "unit custom field" in response.json()["detail"]


def test_another_projects_field_is_refused(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    country_pack_id: str,
    currency_id: str,
    draft_configuration: str,
) -> None:
    """A definition scoped to another development can never apply to a unit here."""
    other = admin_client.post(
        PROJECTS,
        json={
            "code": "SECOND-DEV",
            "name": "Second development",
            "developer_entity": "Reach Developments",
            "country_pack_id": country_pack_id,
            "city": "Amman",
            "project_type_code": "RESIDENTIAL",
            "base_currency_id": currency_id,
            "reporting_currency_id": currency_id,
            "fiscal_year_start_month": 1,
        },
    )
    assert other.status_code == 201, other.text
    other_id = other.json()["id"]
    admin_client.patch(f"{PROJECTS}/{other_id}", json={"status": "predevelopment"})
    definition = _field(
        admin_client, other_id, field_key="corner_glazing", display_label="Corner glazing"
    )

    response = _premium(
        finance_client,
        project_id,
        draft_configuration,
        source_kind="custom_field",
        custom_field_definition_id=definition,
    )

    assert response.status_code == 422
    assert "does not apply to units of this project" in response.json()["detail"]


def test_a_retired_definition_is_refused(
    admin_client: TestClient, finance_client: TestClient, project_id: str, draft_configuration: str
) -> None:
    definition = _field(admin_client, project_id)
    admin_client.patch(
        f"{PROJECTS}/{project_id}/field-definitions/{definition}", json={"is_active": False}
    )

    response = _premium(
        finance_client,
        project_id,
        draft_configuration,
        source_kind="custom_field",
        custom_field_definition_id=definition,
    )

    assert response.status_code == 422
    assert "does not apply to units of this project" in response.json()["detail"]


def test_no_expression_path_reaches_the_matcher(
    admin_client: TestClient, finance_client: TestClient, project_id: str, draft_configuration: str
) -> None:
    """The premium request has no field name and no operator to supply one."""
    response = _premium(
        finance_client,
        project_id,
        draft_configuration,
        source_kind="unit_type",
        match_code="2BR",
        expression="unit.bedrooms > 2",
    )

    assert response.status_code == 422


# --------------------------------------------------------------------------- #
# Escalation triggers carry the fact they claim to use
# --------------------------------------------------------------------------- #

_TOMORROW = (business_today() + timedelta(days=1)).isoformat()

_VALID_TRIGGERS = [
    ("date", {"threshold_date": _TOMORROW}),
    ("sales_percentage", {"threshold_fraction": "0.300000"}),
    ("construction_milestone", {"milestone_reference": "Slab level 5 certified"}),
    ("market_index", {"market_index_reference": "DLD residential index"}),
]


@pytest.mark.parametrize(("trigger", "inputs"), _VALID_TRIGGERS)
def test_each_trigger_family_is_accepted_with_its_own_fact(
    finance_client: TestClient,
    project_id: str,
    draft_configuration: str,
    trigger: str,
    inputs: dict[str, object],
) -> None:
    response = _escalation(
        finance_client, project_id, draft_configuration, trigger_type=trigger, **inputs
    )

    assert response.status_code == 201, response.text


@pytest.mark.parametrize(("trigger", "inputs"), _VALID_TRIGGERS)
def test_a_trigger_without_its_own_fact_is_refused(
    finance_client: TestClient,
    project_id: str,
    draft_configuration: str,
    trigger: str,
    inputs: dict[str, object],
) -> None:
    """ "Escalate when we are 30% sold" with no 30% in it cannot be activated
    against evidence, because there is nothing to compare the evidence to."""
    response = _escalation(finance_client, project_id, draft_configuration, trigger_type=trigger)

    assert response.status_code == 422
    assert response.json()["detail"].startswith(f"A {trigger} escalation needs")


@pytest.mark.parametrize(
    ("trigger", "own", "foreign"),
    [
        ("date", {"threshold_date": _TOMORROW}, {"threshold_fraction": "0.300000"}),
        (
            "sales_percentage",
            {"threshold_fraction": "0.300000"},
            {"milestone_reference": "Slab level 5"},
        ),
        (
            "construction_milestone",
            {"milestone_reference": "Slab level 5"},
            {"market_index_reference": "DLD"},
        ),
        ("market_index", {"market_index_reference": "DLD"}, {"threshold_date": _TOMORROW}),
    ],
)
def test_a_trigger_carrying_another_triggers_fact_is_refused(
    finance_client: TestClient,
    project_id: str,
    draft_configuration: str,
    trigger: str,
    own: dict[str, object],
    foreign: dict[str, object],
) -> None:
    """A rule holding two triggers' inputs is a rule two readers read two ways."""
    response = _escalation(
        finance_client, project_id, draft_configuration, trigger_type=trigger, **own, **foreign
    )

    assert response.status_code == 422
    assert "applies to a different trigger" in response.json()["detail"]


def test_the_database_refuses_a_trigger_with_no_fact(
    finance_client: TestClient, project_id: str, draft_configuration: str, db: Session
) -> None:
    """Written straight past the service, the way a script or a console would."""
    created = _escalation(
        finance_client,
        project_id,
        draft_configuration,
        trigger_type="sales_percentage",
        threshold_fraction="0.300000",
    )
    assert created.status_code == 201, created.text

    with pytest.raises(IntegrityError) as raised:
        db.execute(
            text("UPDATE pricing_escalation_rules SET threshold_fraction = NULL WHERE id = :id"),
            {"id": created.json()["id"]},
        )
        db.flush()
    db.rollback()

    assert "ck_pricing_escalation_rules_trigger_inputs" in str(raised.value)


def test_the_database_refuses_two_triggers_worth_of_facts(
    finance_client: TestClient, project_id: str, draft_configuration: str, db: Session
) -> None:
    created = _escalation(
        finance_client,
        project_id,
        draft_configuration,
        trigger_type="market_index",
        market_index_reference="DLD residential index",
    )
    assert created.status_code == 201, created.text

    with pytest.raises(IntegrityError) as raised:
        db.execute(
            text("UPDATE pricing_escalation_rules SET threshold_date = :day WHERE id = :id"),
            {"id": created.json()["id"], "day": _TOMORROW},
        )
        db.flush()
    db.rollback()

    assert "ck_pricing_escalation_rules_trigger_inputs" in str(raised.value)


def test_a_unit_type_scope_is_checked_against_the_catalogue(
    finance_client: TestClient, project_id: str, draft_configuration: str
) -> None:
    """Phase scope has a real same-project foreign key; a unit type code needs this."""
    response = _escalation(
        finance_client,
        project_id,
        draft_configuration,
        trigger_type="date",
        threshold_date=_TOMORROW,
        scope_type="unit_type",
        unit_type_code="5BR",
    )

    assert response.status_code == 422
    assert "No configured unit_type" in response.json()["detail"]


def test_a_configured_unit_type_scope_is_accepted(
    finance_client: TestClient, project_id: str, draft_configuration: str
) -> None:
    response = _escalation(
        finance_client,
        project_id,
        draft_configuration,
        trigger_type="date",
        threshold_date=_TOMORROW,
        scope_type="unit_type",
        unit_type_code="3BR",
    )

    assert response.status_code == 201, response.text


# --------------------------------------------------------------------------- #
# Activation evidence has to satisfy the rule it is offered against
# --------------------------------------------------------------------------- #


def _live_rule_with(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    currency_id: str,
    area_types: dict[str, str],
    **escalation: object,
) -> str:
    """A live configuration carrying one escalation rule, ready to activate."""
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
        assert (
            finance_client.post(
                f"{base}/area-rules",
                json={"area_type_id": area_type_id, "pricing_method": method, **extra},
            ).status_code
            == 201
        )
    rule = _escalation(finance_client, project_id, configuration, **escalation)
    assert rule.status_code == 201, rule.text
    assert finance_client.post(f"{base}/submit", json={}).status_code == 200
    assert cfo_client.post(f"{base}/approve", json={"reason": "Reviewed"}).status_code == 200
    assert cfo_client.post(f"{base}/activate").status_code == 200
    return rule.json()["id"]


def _activate(cfo_client: TestClient, project_id: str, rule: str, **body: object) -> Response:
    payload: dict[str, object] = {
        "effective_date": business_today().isoformat(),
        "evidence_reference": "Sales report 2026-08",
        "reason": "Absorption threshold reached",
    }
    payload.update(body)
    return cfo_client.post(
        f"{pricing_url(project_id)}/escalation-rules/{rule}/activate", json=payload
    )


@pytest.fixture
def sales_rule(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    currency_id: str,
    area_types: dict[str, str],
) -> str:
    return _live_rule_with(
        finance_client,
        cfo_client,
        project_id,
        currency_id,
        area_types,
        trigger_type="sales_percentage",
        threshold_fraction="0.300000",
    )


def test_evidence_below_the_threshold_is_refused(
    cfo_client: TestClient, project_id: str, sales_rule: str
) -> None:
    """A CFO cannot activate a "30% sold" escalation on evidence saying 29%."""
    response = _activate(cfo_client, project_id, sales_rule, evidence_value="0.2900")

    assert response.status_code == 409
    assert "becomes due at 0.300000" in response.json()["detail"]


@pytest.mark.parametrize("evidence", ["0.3000", "0.5000", "1.0000"])
def test_evidence_at_or_above_the_threshold_is_accepted(
    cfo_client: TestClient, project_id: str, sales_rule: str, evidence: str
) -> None:
    response = _activate(cfo_client, project_id, sales_rule, evidence_value=evidence)

    assert response.status_code == 201, response.text


def test_a_sales_activation_without_evidence_is_refused(
    cfo_client: TestClient, project_id: str, sales_rule: str
) -> None:
    response = _activate(cfo_client, project_id, sales_rule)

    assert response.status_code == 422
    assert "share of inventory sold" in response.json()["detail"]


def test_evidence_above_one_is_refused(
    cfo_client: TestClient, project_id: str, sales_rule: str
) -> None:
    """A share of inventory sold is a fraction. 150% sold is a typed-in decimal point."""
    response = _activate(cfo_client, project_id, sales_rule, evidence_value="1.5000")

    assert response.status_code == 422
    assert "fraction between 0 and 1" in response.json()["detail"]


def test_a_date_activation_still_needs_no_evidence_value(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    currency_id: str,
    area_types: dict[str, str],
) -> None:
    """The one trigger the system could evaluate itself still needs a person, not a number."""
    rule = _live_rule_with(
        finance_client,
        cfo_client,
        project_id,
        currency_id,
        area_types,
        trigger_type="date",
        threshold_date=business_today().isoformat(),
    )

    response = _activate(cfo_client, project_id, rule)

    assert response.status_code == 201, response.text


def test_a_date_activation_before_its_threshold_is_refused(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    currency_id: str,
    area_types: dict[str, str],
) -> None:
    rule = _live_rule_with(
        finance_client,
        cfo_client,
        project_id,
        currency_id,
        area_types,
        trigger_type="date",
        threshold_date=(business_today() + timedelta(days=30)).isoformat(),
    )

    response = _activate(cfo_client, project_id, rule)

    assert response.status_code == 409
    assert "not eligible before" in response.json()["detail"]


def test_a_manually_evidenced_activation_records_when_the_fact_was_true(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    currency_id: str,
    area_types: dict[str, str],
) -> None:
    """ "Certified" alone does not say when. The audit trail should."""
    rule = _live_rule_with(
        finance_client,
        cfo_client,
        project_id,
        currency_id,
        area_types,
        trigger_type="construction_milestone",
        milestone_reference="Slab level 5 certified",
    )

    without = _activate(cfo_client, project_id, rule)
    with_date = _activate(cfo_client, project_id, rule, evidence_date=business_today().isoformat())

    assert without.status_code == 422
    assert "date the evidence was true" in without.json()["detail"]
    assert with_date.status_code == 201, with_date.text


def test_activating_an_escalation_does_not_reprice_a_live_unit(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    currency_id: str,
) -> None:
    """An activation makes the escalation available to the *next* version.

    Prices already live keep saying what they said until somebody generates,
    approves and activates a replacement. That is the whole reason activation is
    a recorded human decision rather than a trigger.
    """
    approve_areas(admin_client, project_id, unit_id, area_types)
    rule = _live_rule_with(
        finance_client,
        cfo_client,
        project_id,
        currency_id,
        area_types,
        trigger_type="sales_percentage",
        threshold_fraction="0.300000",
    )
    draft = finance_client.post(
        f"{pricing_url(project_id)}/units/{unit_id}/price-versions", json={}
    ).json()
    base = f"{pricing_url(project_id)}/price-versions/{draft['id']}"
    finance_client.post(f"{base}/submit", json={})
    cfo_client.post(f"{base}/approve", json={"reason": "Reviewed"})
    cfo_client.post(f"{base}/activate")

    assert _activate(cfo_client, project_id, rule, evidence_value="0.4000").status_code == 201

    live = finance_client.get(f"{pricing_url(project_id)}/units/{unit_id}").json()
    assert live["active_price"]["reference_price_ex_tax"] == "165000.00"
    assert live["active_price"]["escalation_total"] == "0.00"


# --------------------------------------------------------------------------- #
# internal_base means the actual internal area
# --------------------------------------------------------------------------- #


def _area_type(admin_client: TestClient, project_id: str, **overrides: object) -> str:
    payload: dict[str, object] = {
        "code": "TERRACE",
        "label": "Terrace",
        "area_role": "outdoor",
        # Zero-weighted on purpose: inventory already refuses a *weighted* area
        # measured in another unit, because the weighted total would add square
        # feet to square metres. This one is priced but not weighted, which is
        # exactly the case the pricing rule has to decide for itself.
        "weight_factor": "0.000000",
        "unit_of_measure": "sqft",
    }
    payload.update(overrides)
    response = admin_client.post(f"{inventory_url(project_id)}/area-types", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_the_internal_area_may_be_the_internal_base(
    finance_client: TestClient, project_id: str, draft_configuration: str
) -> None:
    """The fixture builds exactly this, so a submission proves the whole rule."""
    response = finance_client.post(
        f"{pricing_url(project_id)}/configurations/{draft_configuration}/submit", json={}
    )

    assert response.status_code == 200, response.text


def test_an_outdoor_area_may_not_be_the_internal_base(
    finance_client: TestClient,
    project_id: str,
    draft_configuration: str,
    area_types: dict[str, str],
) -> None:
    response = finance_client.post(
        f"{pricing_url(project_id)}/configurations/{draft_configuration}/area-rules",
        json={"area_type_id": area_types["BALCONY"], "pricing_method": "internal_base"},
    )

    assert response.status_code == 422
    assert "Only the project's internal area" in response.json()["detail"]


def test_a_factor_rule_may_not_cross_units_of_measure(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    draft_configuration: str,
) -> None:
    """A JOD-per-square-metre rate times a square-foot area needs a conversion.

    There is deliberately no conversion anywhere in this system, so the two
    measurements have to already agree or the rule is refused.
    """
    terrace = _area_type(admin_client, project_id)

    response = finance_client.post(
        f"{pricing_url(project_id)}/configurations/{draft_configuration}/area-rules",
        json={
            "area_type_id": terrace,
            "pricing_method": "factor_of_internal_rate",
            "internal_rate_factor": "0.400000",
        },
    )

    assert response.status_code == 422
    assert "no conversion here" in response.json()["detail"]


def test_a_fixed_rate_rule_may_use_its_own_unit_of_measure(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    draft_configuration: str,
) -> None:
    """Its rate is stated against that area's own unit, so nothing is carried across."""
    terrace = _area_type(admin_client, project_id)

    response = finance_client.post(
        f"{pricing_url(project_id)}/configurations/{draft_configuration}/area-rules",
        json={
            "area_type_id": terrace,
            "pricing_method": "fixed_rate_per_area",
            "rate_per_area": "60.00",
        },
    )

    assert response.status_code == 201, response.text


def test_a_factor_rule_in_the_same_unit_of_measure_is_accepted(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    draft_configuration: str,
) -> None:
    terrace = _area_type(admin_client, project_id, unit_of_measure="sqm")

    response = finance_client.post(
        f"{pricing_url(project_id)}/configurations/{draft_configuration}/area-rules",
        json={
            "area_type_id": terrace,
            "pricing_method": "factor_of_internal_rate",
            "internal_rate_factor": "0.400000",
        },
    )

    assert response.status_code == 201, response.text


def test_submission_refuses_a_configuration_whose_internal_base_was_deactivated(
    finance_client: TestClient,
    project_id: str,
    draft_configuration: str,
    area_types: dict[str, str],
) -> None:
    """Checked again at submission: a rule can be deactivated after it was written."""
    rules = finance_client.get(
        f"{pricing_url(project_id)}/configurations/{draft_configuration}/area-rules"
    ).json()
    internal = next(rule for rule in rules if rule["area_type_id"] == area_types["INTERNAL"])
    deactivated = finance_client.patch(
        f"{pricing_url(project_id)}/area-rules/{internal['id']}", json={"is_active": False}
    )
    assert deactivated.status_code == 200, deactivated.text

    response = finance_client.post(
        f"{pricing_url(project_id)}/configurations/{draft_configuration}/submit", json={}
    )

    assert response.status_code == 422
    assert "prices no internal area" in response.json()["detail"]


def test_the_database_refuses_a_second_active_internal_base(
    finance_client: TestClient,
    project_id: str,
    draft_configuration: str,
    area_types: dict[str, str],
    db: Session,
) -> None:
    """The service refuses it first; this is the backstop a direct write meets."""
    rules = finance_client.get(
        f"{pricing_url(project_id)}/configurations/{draft_configuration}/area-rules"
    ).json()
    balcony = next(rule for rule in rules if rule["area_type_id"] == area_types["BALCONY"])

    with pytest.raises(IntegrityError) as raised:
        db.execute(
            text(
                "UPDATE pricing_area_rules "
                "SET pricing_method = 'internal_base', internal_rate_factor = NULL "
                "WHERE id = :id"
            ),
            {"id": balcony["id"]},
        )
        db.flush()
    db.rollback()

    assert "uq_pricing_area_rules_internal_base" in str(raised.value)
