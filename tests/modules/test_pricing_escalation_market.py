"""Escalation and market comparison: governed movements and a stated benchmark.

Escalation in PR-MVP-04 is configured here and activated by a named approver
against recorded evidence — including for a date trigger the system could
evaluate itself, because activation is the moment a policy starts moving money
and one that starts because a clock ticked has nobody's name on it. Sales
absorption, certified construction and a market index are real triggers whose
source transactions do not exist yet; the rules exist, and the evidence is
recorded rather than invented.

Market comparison is one benchmark, chosen by a stated precedence, in the
project's own currency. No feed, no average, no conversion.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.pricing.models import PricingEscalationActivation, UnitPriceVersion
from tests.modules.conftest import approve_areas, pricing_url


def _rule(client: TestClient, project_id: str, configuration_id: str, **body: object) -> dict:
    response = client.post(
        f"{pricing_url(project_id)}/configurations/{configuration_id}/escalation-rules", json=body
    )
    assert response.status_code == 201, response.text
    return response.json()


def _benchmark(client: TestClient, project_id: str, currency_id: str, **body: object) -> dict:
    payload = {
        "area_basis": "internal",
        "benchmark_price_per_area": "1600.00",
        "currency_id": currency_id,
        "comparison_date": "2026-03-01",
        "source_name": "Agency survey",
        "tolerance_fraction": "0.100000",
    }
    payload.update(body)
    return client.post(f"{pricing_url(project_id)}/market-benchmarks", json=payload)


def _draft(client: TestClient, project_id: str, unit_id: str) -> dict:
    response = client.post(f"{pricing_url(project_id)}/units/{unit_id}/price-versions", json={})
    assert response.status_code == 201, response.text
    return response.json()


def _activate_configuration(
    finance_client: TestClient, cfo_client: TestClient, project_id: str, configuration_id: str
) -> None:
    """Put a draft policy live, the governed way.

    Escalation rules belong to a configuration and may only be written while it
    is a draft; activation may only happen on the live one. So the order is
    always: write the rules, then put the policy live — which is also the order
    a pricing team works in.
    """
    base = f"{pricing_url(project_id)}/configurations/{configuration_id}"
    assert finance_client.post(f"{base}/submit", json={}).status_code == 200
    assert cfo_client.post(f"{base}/approve", json={"reason": "Reviewed"}).status_code == 200
    assert cfo_client.post(f"{base}/activate").status_code == 200


def _price_unit(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
) -> str:
    approve_areas(admin_client, project_id, unit_id, area_types)
    version = _draft(finance_client, project_id, unit_id)["id"]
    base = f"{pricing_url(project_id)}/price-versions/{version}"
    assert finance_client.post(f"{base}/submit", json={}).status_code == 200
    assert cfo_client.post(f"{base}/approve", json={"reason": "ok"}).status_code == 200
    assert cfo_client.post(f"{base}/activate").status_code == 200
    return version


# --------------------------------------------------------------------------- #
# Escalation
# --------------------------------------------------------------------------- #


def test_a_date_escalation_cannot_be_activated_before_its_date(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    draft_configuration: str,
) -> None:
    rule = _rule(
        finance_client,
        project_id,
        draft_configuration,
        code="Q3",
        label="Q3 uplift",
        trigger_type="date",
        threshold_date="2026-07-01",
        adjustment_method="percentage",
        adjustment_percentage_fraction="0.030000",
    )
    _activate_configuration(finance_client, cfo_client, project_id, draft_configuration)

    response = cfo_client.post(
        f"{pricing_url(project_id)}/escalation-rules/{rule['id']}/activate",
        json={
            "effective_date": "2026-05-01",
            "evidence_reference": "Board minute 12",
            "reason": "Early",
        },
    )

    assert response.status_code == 409
    assert "not eligible before 2026-07-01" in response.json()["detail"]


def test_only_the_approver_may_activate_an_escalation(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    draft_configuration: str,
) -> None:
    rule = _rule(
        finance_client,
        project_id,
        draft_configuration,
        code="ABS30",
        label="30% absorption",
        trigger_type="sales_percentage",
        threshold_fraction="0.300000",
        adjustment_method="percentage",
        adjustment_percentage_fraction="0.050000",
    )
    _activate_configuration(finance_client, cfo_client, project_id, draft_configuration)

    response = finance_client.post(
        f"{pricing_url(project_id)}/escalation-rules/{rule['id']}/activate",
        json={
            "effective_date": "2026-05-01",
            "evidence_reference": "Sales report",
            "reason": "Reached",
        },
    )

    assert response.status_code == 403


def test_an_escalation_of_a_draft_configuration_cannot_be_activated(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    draft_configuration: str,
) -> None:
    """A policy nobody has put live cannot start moving prices."""
    rule = _rule(
        finance_client,
        project_id,
        draft_configuration,
        code="Q3",
        label="Q3 uplift",
        trigger_type="date",
        threshold_date="2026-01-01",
        adjustment_method="percentage",
        adjustment_percentage_fraction="0.030000",
    )

    response = cfo_client.post(
        f"{pricing_url(project_id)}/escalation-rules/{rule['id']}/activate",
        json={"effective_date": "2026-01-01", "evidence_reference": "Calendar", "reason": "Step"},
    )

    assert response.status_code == 409
    assert "active pricing configuration" in response.json()["detail"]


def test_an_absorption_escalation_is_activated_against_recorded_evidence(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    draft_configuration: str,
    db: Session,
) -> None:
    """PR-MVP-05 can measure absorption. Until then the evidence is written down."""
    rule = _rule(
        finance_client,
        project_id,
        draft_configuration,
        code="ABS30",
        label="30% absorption",
        trigger_type="sales_percentage",
        threshold_fraction="0.300000",
        adjustment_method="percentage",
        adjustment_percentage_fraction="0.050000",
    )
    _activate_configuration(finance_client, cfo_client, project_id, draft_configuration)

    response = cfo_client.post(
        f"{pricing_url(project_id)}/escalation-rules/{rule['id']}/activate",
        json={
            "effective_date": "2026-05-01",
            "evidence_value": "0.3200",
            "evidence_date": "2026-04-30",
            "evidence_reference": "Sales pipeline report 2026-04",
            "reason": "32% of releasable inventory reserved",
        },
    )

    assert response.status_code == 201, response.text
    activation = db.scalars(select(PricingEscalationActivation)).one()
    assert activation.evidence_reference == "Sales pipeline report 2026-04"
    assert activation.evidence_value == Decimal("0.3200")
    assert activation.approved_by_user_id is not None


def test_activating_an_escalation_does_not_reprice_a_single_unit(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    draft_configuration: str,
    db: Session,
) -> None:
    """The rule the whole module turns on: a price change is a new version.

    247 list prices silently rewritten by a policy change is precisely the
    behaviour effective-dated versioning exists to make impossible.
    """
    rule = _rule(
        finance_client,
        project_id,
        draft_configuration,
        code="Q3",
        label="Q3 uplift",
        trigger_type="date",
        threshold_date="2026-01-01",
        adjustment_method="percentage",
        adjustment_percentage_fraction="0.030000",
    )
    _activate_configuration(finance_client, cfo_client, project_id, draft_configuration)
    _price_unit(admin_client, finance_client, cfo_client, project_id, unit_id, area_types)

    cfo_client.post(
        f"{pricing_url(project_id)}/escalation-rules/{rule['id']}/activate",
        json={
            "effective_date": "2026-01-01",
            "evidence_reference": "Calendar",
            "reason": "Q3 pricing step",
        },
    )

    db.expire_all()
    active = db.scalars(select(UnitPriceVersion).where(UnitPriceVersion.status == "active")).one()
    assert active.reference_price_ex_tax == Decimal("165000.00")
    assert active.escalation_total == Decimal("0.00")


def test_a_new_draft_generated_afterwards_carries_the_escalation(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    draft_configuration: str,
) -> None:
    rule = _rule(
        finance_client,
        project_id,
        draft_configuration,
        code="Q3",
        label="Q3 uplift",
        trigger_type="date",
        threshold_date="2026-01-01",
        adjustment_method="percentage",
        adjustment_percentage_fraction="0.030000",
    )
    _activate_configuration(finance_client, cfo_client, project_id, draft_configuration)
    _price_unit(admin_client, finance_client, cfo_client, project_id, unit_id, area_types)
    cfo_client.post(
        f"{pricing_url(project_id)}/escalation-rules/{rule['id']}/activate",
        json={
            "effective_date": "2026-01-01",
            "evidence_reference": "Calendar",
            "reason": "Q3 pricing step",
        },
    )

    version = _draft(finance_client, project_id, unit_id)

    line = next(item for item in version["components"] if item["code"] == "Q3")
    assert line["component_type"] == "escalation"
    assert line["final_amount"] == "4950.00"
    assert version["reference_price_ex_tax"] == "169950.00"


def test_a_reversed_activation_stops_applying_but_stays_on_the_record(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    draft_configuration: str,
    db: Session,
) -> None:
    """A correction is a reversal and a replacement, never an edit."""
    rule = _rule(
        finance_client,
        project_id,
        draft_configuration,
        code="Q3",
        label="Q3 uplift",
        trigger_type="date",
        threshold_date="2026-01-01",
        adjustment_method="percentage",
        adjustment_percentage_fraction="0.030000",
    )
    _activate_configuration(finance_client, cfo_client, project_id, draft_configuration)
    approve_areas(admin_client, project_id, unit_id, area_types)
    activation = cfo_client.post(
        f"{pricing_url(project_id)}/escalation-rules/{rule['id']}/activate",
        json={
            "effective_date": "2026-01-01",
            "evidence_reference": "Calendar",
            "reason": "Q3 pricing step",
        },
    ).json()["id"]

    reversed_ = cfo_client.post(
        f"{pricing_url(project_id)}/escalation-activations/{activation}/reverse",
        json={"reason": "Activated against the wrong phase"},
    )
    version = _draft(finance_client, project_id, unit_id)

    assert reversed_.status_code == 200, reversed_.text
    assert all(item["code"] != "Q3" for item in version["components"])
    row = db.scalars(select(PricingEscalationActivation)).one()
    assert row.is_active is False
    assert row.reversal_reason == "Activated against the wrong phase"
    assert row.reason == "Q3 pricing step"


def test_an_escalation_scoped_to_another_phase_does_not_reach_this_unit(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    draft_configuration: str,
) -> None:
    from tests.modules.conftest import inventory_url

    other_phase = admin_client.post(
        f"{inventory_url(project_id)}/phases",
        json={"code": "PHASE-2", "name": "Phase 2", "sequence": 2},
    ).json()["id"]
    rule = _rule(
        finance_client,
        project_id,
        draft_configuration,
        code="P2ONLY",
        label="Phase 2 uplift",
        trigger_type="date",
        scope_type="phase",
        phase_id=other_phase,
        threshold_date="2026-01-01",
        adjustment_method="percentage",
        adjustment_percentage_fraction="0.100000",
    )
    _activate_configuration(finance_client, cfo_client, project_id, draft_configuration)
    approve_areas(admin_client, project_id, unit_id, area_types)
    cfo_client.post(
        f"{pricing_url(project_id)}/escalation-rules/{rule['id']}/activate",
        json={
            "effective_date": "2026-01-01",
            "evidence_reference": "Calendar",
            "reason": "Phase 2 step",
        },
    )

    version = _draft(finance_client, project_id, unit_id)

    assert all(item["code"] != "P2ONLY" for item in version["components"])


def test_escalation_activation_is_audited(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    draft_configuration: str,
    db: Session,
) -> None:
    rule = _rule(
        finance_client,
        project_id,
        draft_configuration,
        code="Q3",
        label="Q3",
        trigger_type="date",
        threshold_date="2026-01-01",
        adjustment_method="fixed",
        adjustment_amount="1000.00",
    )
    _activate_configuration(finance_client, cfo_client, project_id, draft_configuration)
    activation = cfo_client.post(
        f"{pricing_url(project_id)}/escalation-rules/{rule['id']}/activate",
        json={"effective_date": "2026-01-01", "evidence_reference": "Calendar", "reason": "Step"},
    ).json()["id"]
    cfo_client.post(
        f"{pricing_url(project_id)}/escalation-activations/{activation}/reverse",
        json={"reason": "Wrong"},
    )

    actions = {
        event.action
        for event in db.scalars(
            select(AuditEvent).where(AuditEvent.action.like("pricing_escalation%"))
        )
    }
    assert {
        "pricing_escalation_rule.created",
        "pricing_escalation.activated",
        "pricing_escalation.reversed",
    } <= actions


# --------------------------------------------------------------------------- #
# Market benchmarks
# --------------------------------------------------------------------------- #


def test_a_price_within_tolerance_is_flagged_as_such(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    currency_id: str,
    area_types: dict[str, str],
    active_configuration: str,
) -> None:
    """1,650 per internal metre against a 1,600 benchmark is 3.125% above.

    Inside a 10% tolerance, so the flag says so and publishes the deviation
    rather than a verdict with no number behind it.
    """
    _benchmark(finance_client, project_id, currency_id)
    approve_areas(admin_client, project_id, unit_id, area_types)

    version = _draft(finance_client, project_id, unit_id)

    assert version["price_per_internal_area"] == "1650.00"
    assert version["market_deviation_fraction"] == "0.031250"
    assert version["market_flag"] == "within_tolerance"
    assert version["market_benchmark_price_snapshot"] == "1600.00"


def test_a_price_above_tolerance_is_called_out(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    currency_id: str,
    area_types: dict[str, str],
    active_configuration: str,
) -> None:
    _benchmark(finance_client, project_id, currency_id, benchmark_price_per_area="1000.00")
    approve_areas(admin_client, project_id, unit_id, area_types)

    version = _draft(finance_client, project_id, unit_id)

    assert version["market_flag"] == "above_tolerance"
    assert version["market_deviation_fraction"] == "0.650000"


def test_a_price_below_tolerance_is_called_out(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    currency_id: str,
    area_types: dict[str, str],
    active_configuration: str,
) -> None:
    _benchmark(finance_client, project_id, currency_id, benchmark_price_per_area="3000.00")
    approve_areas(admin_client, project_id, unit_id, area_types)

    version = _draft(finance_client, project_id, unit_id)

    assert version["market_flag"] == "below_tolerance"


def test_a_weighted_basis_benchmark_uses_the_weighted_area(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    currency_id: str,
    area_types: dict[str, str],
    active_configuration: str,
) -> None:
    """A price per internal metre and per weighted metre are different numbers.

    110 weighted metres against 100 internal ones, so 165,000 is 1,650 the one
    way and 1,500 the other. A flag that did not say which it used would be
    unusable.
    """
    _benchmark(
        finance_client,
        project_id,
        currency_id,
        area_basis="weighted",
        benchmark_price_per_area="1500.00",
    )
    approve_areas(admin_client, project_id, unit_id, area_types)

    version = _draft(finance_client, project_id, unit_id)

    assert version["weighted_area_snapshot"] == "110.0000"
    assert version["price_per_weighted_area"] == "1500.00"
    assert version["market_deviation_fraction"] == "0.000000"
    assert version["market_flag"] == "within_tolerance"


def test_no_benchmark_is_a_stated_answer_not_a_missing_one(
    project_id: str, priced_unit: str, finance_client: TestClient
) -> None:
    version = finance_client.get(f"{pricing_url(project_id)}/price-versions/{priced_unit}").json()

    assert version["market_flag"] == "no_benchmark"
    assert version["market_deviation_fraction"] is None


def test_two_equally_specific_benchmarks_cannot_both_be_active(
    finance_client: TestClient, project_id: str, currency_id: str, active_configuration: str
) -> None:
    """A comparison that depends on which row came back first is not a comparison."""
    first = _benchmark(finance_client, project_id, currency_id)
    second = _benchmark(finance_client, project_id, currency_id, benchmark_price_per_area="1700.00")

    assert first.status_code == 201, first.text
    assert second.status_code == 409
    assert "already covers that scope" in second.json()["detail"]


def test_the_most_specific_benchmark_wins(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    phase_id: str,
    currency_id: str,
    area_types: dict[str, str],
    active_configuration: str,
) -> None:
    """Unit type in this phase, then unit type, then phase, then project."""
    _benchmark(finance_client, project_id, currency_id, benchmark_price_per_area="1000.00")
    _benchmark(
        finance_client,
        project_id,
        currency_id,
        phase_id=phase_id,
        unit_type_code="2BR",
        benchmark_price_per_area="1650.00",
    )
    approve_areas(admin_client, project_id, unit_id, area_types)

    version = _draft(finance_client, project_id, unit_id)

    assert version["market_benchmark_price_snapshot"] == "1650.00"
    assert version["market_flag"] == "within_tolerance"


def test_a_benchmark_in_another_currency_is_refused(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    active_configuration: str,
) -> None:
    """There is no FX table here, and inventing a rate to compare two numbers
    would produce a deviation that looks like a fact and is not."""
    from tests.modules.conftest import SETTINGS

    other = admin_client.post(
        f"{SETTINGS}/currencies", json={"code": "USD", "name": "US dollar"}
    ).json()["id"]

    response = _benchmark(finance_client, project_id, other)

    assert response.status_code == 422
    assert "same currency" in response.json()["detail"]
