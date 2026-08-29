"""What the database refuses, whatever the service does.

Application validation gives a caller a message worth reading. It is not the
final integrity layer, and a rule that exists only in Python is a rule one
careless refactor away from being gone. Everything here bypasses the service and
writes straight to PostgreSQL.

The second half is the adversarial pass: malformed input, a price in the wrong
currency, an attempt to edit a live price. All of them must fail safely — a 4xx
with something useful in it, never a 500 and never a silent success.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.modules.pricing.models import (
    PricingConfiguration,
    PricingEscalationActivation,
    UnitPriceComponent,
    UnitPriceVersion,
)
from tests.modules.conftest import SETTINGS, pricing_url


def _version(db: Session) -> UnitPriceVersion:
    return db.scalars(select(UnitPriceVersion)).one()


# --------------------------------------------------------------------------- #
# Constraints the database owns
# --------------------------------------------------------------------------- #


def test_a_price_cannot_point_at_a_project_that_does_not_exist(
    project_id: str, priced_unit: str, db: Session
) -> None:
    existing = _version(db)

    existing.project_id = uuid.uuid4()
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_a_price_cannot_point_at_a_unit_that_does_not_exist(
    project_id: str, priced_unit: str, db: Session
) -> None:
    existing = _version(db)

    existing.unit_id = uuid.uuid4()
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_a_component_cannot_belong_to_a_price_that_does_not_exist(
    project_id: str, priced_unit: str, db: Session
) -> None:
    component = db.scalars(select(UnitPriceComponent)).first()

    component.unit_price_version_id = uuid.uuid4()
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_a_status_outside_the_closed_set_is_refused(
    project_id: str, priced_unit: str, db: Session
) -> None:
    existing = _version(db)

    existing.status = "nearly_approved"
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_a_component_final_amount_must_match_its_override_or_its_calculation(
    project_id: str, priced_unit: str, db: Session
) -> None:
    """The line a reader adds up is the line the database stores. No third number."""
    component = db.scalars(select(UnitPriceComponent)).first()

    component.final_amount = Decimal("1.00")
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_an_override_without_a_reason_is_refused_by_the_database(
    project_id: str, priced_unit: str, db: Session
) -> None:
    component = db.scalars(select(UnitPriceComponent)).first()

    component.override_amount = Decimal("1.00")
    component.final_amount = Decimal("1.00")
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_a_reversed_activation_must_carry_its_reversal(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    draft_configuration: str,
    db: Session,
) -> None:
    rule = finance_client.post(
        f"{pricing_url(project_id)}/configurations/{draft_configuration}/escalation-rules",
        json={
            "code": "Q3",
            "label": "Q3",
            "trigger_type": "date",
            "threshold_date": "2026-01-01",
            "adjustment_method": "fixed",
            "adjustment_amount": "100.00",
        },
    ).json()["id"]
    base = f"{pricing_url(project_id)}/configurations/{draft_configuration}"
    finance_client.post(f"{base}/submit", json={})
    cfo_client.post(f"{base}/approve", json={"reason": "ok"})
    cfo_client.post(f"{base}/activate")
    cfo_client.post(
        f"{pricing_url(project_id)}/escalation-rules/{rule}/activate",
        json={"effective_date": "2026-01-01", "evidence_reference": "Calendar", "reason": "Step"},
    )

    activation = db.scalars(select(PricingEscalationActivation)).one()
    activation.is_active = False
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_a_premium_cap_adjustment_can_only_reduce(
    project_id: str, priced_unit: str, db: Session
) -> None:
    """A cap that added money would be a premium wearing the wrong name."""
    existing = _version(db)

    existing.premium_cap_adjustment = Decimal("100.00")
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_a_configuration_version_number_is_unique_per_project(
    project_id: str, active_configuration: str, db: Session
) -> None:
    existing = db.scalars(select(PricingConfiguration)).one()

    db.add(
        PricingConfiguration(
            project_id=existing.project_id,
            version_number=existing.version_number,
            name="Duplicate",
            status="draft",
            pricing_currency_id=existing.pricing_currency_id,
            base_internal_rate=Decimal("1.00"),
            valid_from=existing.valid_from,
            created_by_user_id=existing.created_by_user_id,
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_a_negative_price_is_refused_by_the_database(
    project_id: str, priced_unit: str, db: Session
) -> None:
    existing = _version(db)

    existing.reference_price_ex_tax = Decimal("-1.00")
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


# --------------------------------------------------------------------------- #
# The adversarial pass
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "body",
    [
        {"base_internal_rate": "not a number"},
        {"base_internal_rate": "1e400"},
        {"maximum_premium_fraction": "2.000000"},
        {"maximum_premium_fraction": "-0.100000"},
        {"offer_valid_days": 0},
        {"offer_valid_days": -5},
    ],
)
def test_a_malformed_configuration_value_is_a_422_not_a_500(
    finance_client: TestClient, project_id: str, draft_configuration: str, body: dict
) -> None:
    response = finance_client.patch(
        f"{pricing_url(project_id)}/configurations/{draft_configuration}", json=body
    )

    assert response.status_code == 422


def test_a_price_in_a_currency_the_project_no_longer_prices_in_cannot_be_submitted(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    active_configuration: str,
    db: Session,
) -> None:
    """Given a draft whose currency was changed underneath it, then submission refuses.

    There is no conversion here and there should not be one. A price whose
    currency no longer matches the project's is not a price that can be
    compared with anything.
    """
    from tests.modules.conftest import approve_areas

    approve_areas(admin_client, project_id, unit_id, area_types)
    version_id = finance_client.post(
        f"{pricing_url(project_id)}/units/{unit_id}/price-versions", json={}
    ).json()["id"]
    other = admin_client.post(
        f"{SETTINGS}/currencies", json={"code": "USD", "name": "US dollar"}
    ).json()["id"]
    row = db.scalars(
        select(UnitPriceVersion).where(UnitPriceVersion.id == uuid.UUID(version_id))
    ).one()
    row.currency_id = uuid.UUID(other)
    db.commit()

    response = finance_client.post(
        f"{pricing_url(project_id)}/price-versions/{version_id}/submit", json={}
    )

    assert response.status_code == 409
    assert "pricing currency" in response.json()["detail"]


def test_an_unknown_component_sequence_is_refused(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    active_configuration: str,
) -> None:
    from tests.modules.conftest import approve_areas

    approve_areas(admin_client, project_id, unit_id, area_types)
    version_id = finance_client.post(
        f"{pricing_url(project_id)}/units/{unit_id}/price-versions", json={}
    ).json()["id"]

    response = finance_client.patch(
        f"{pricing_url(project_id)}/price-versions/{version_id}",
        json={
            "overrides": [{"sequence": 99, "override_amount": "1.00", "override_reason": "Because"}]
        },
    )

    assert response.status_code == 422
    assert "component 99" in response.json()["detail"]


def test_a_price_version_of_another_project_is_not_reachable(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    priced_unit: str,
    country_pack_id: str,
    currency_id: str,
) -> None:
    """Loaded by project and identifier together, never by identifier alone."""
    from tests.modules.conftest import PROJECTS, project_payload

    other = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="OTHER", name="Other")
    ).json()["id"]

    response = admin_client.get(f"{pricing_url(other)}/price-versions/{priced_unit}")

    assert response.status_code == 404


def test_an_active_price_cannot_have_its_components_edited_through_any_route(
    finance_client: TestClient, project_id: str, priced_unit: str
) -> None:
    """There is no component route at all — the lines belong to the version."""
    response = finance_client.patch(
        f"{pricing_url(project_id)}/price-versions/{priced_unit}",
        json={
            "overrides": [{"sequence": 1, "override_amount": "1.00", "override_reason": "Because"}]
        },
    )

    assert response.status_code == 409


def test_a_quote_with_an_unknown_field_is_refused(
    finance_client: TestClient, project_id: str, unit_id: str, priced_unit: str
) -> None:
    response = finance_client.post(
        f"{pricing_url(project_id)}/units/{unit_id}/quote-preview",
        json={"discont_fraction": "0.05"},
    )

    assert response.status_code == 422


def test_no_pricing_route_leaks_an_internal_detail(
    finance_client: TestClient, project_id: str, priced_unit: str
) -> None:
    """A 4xx body is a fact the caller is entitled to, and nothing else."""
    probes = [
        finance_client.get(f"{pricing_url(project_id)}/price-versions/{uuid.uuid4()}"),
        finance_client.patch(
            f"{pricing_url(project_id)}/configurations/{uuid.uuid4()}", json={"name": "x"}
        ),
        finance_client.post(
            f"{pricing_url(project_id)}/price-versions/generate", json={"unit_ids": []}
        ),
    ]

    for response in probes:
        assert 400 <= response.status_code < 500, response.text
        body = response.text.lower()
        assert "traceback" not in body
        assert "postgres" not in body
        assert "psycopg" not in body
        assert "select " not in body


def test_a_component_amount_is_never_stored_as_a_float(
    project_id: str, priced_unit: str, db: Session
) -> None:
    """Decimal in, Decimal out. A price through a binary float is unreconcilable."""
    for component in db.scalars(select(UnitPriceComponent)):
        assert isinstance(component.calculated_amount, Decimal)
        assert isinstance(component.final_amount, Decimal)
    assert isinstance(_version(db).reference_price_ex_tax, Decimal)


def test_a_decimal_beyond_the_column_scale_is_refused_rather_than_truncated(
    finance_client: TestClient, project_id: str, draft_configuration: str
) -> None:
    """Silently dropping a fil is how two systems stop agreeing about a price."""
    response = finance_client.patch(
        f"{pricing_url(project_id)}/configurations/{draft_configuration}",
        json={"base_internal_rate": "1500.12345"},
    )

    assert response.status_code == 422


def test_writing_straight_past_the_service_still_cannot_create_a_second_active_price(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    priced_unit: str,
    db: Session,
) -> None:
    """The last line of defence, exercised with the service removed entirely."""
    second = finance_client.post(
        f"{pricing_url(project_id)}/units/{unit_id}/price-versions", json={}
    ).json()["id"]

    with pytest.raises((IntegrityError, DBAPIError)):
        db.execute(
            select(UnitPriceVersion).where(UnitPriceVersion.id == uuid.UUID(second))
        ).scalar_one().status = "active"
        db.flush()
    db.rollback()
