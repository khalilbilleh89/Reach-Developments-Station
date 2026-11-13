"""Real database/API checks for land costs, permissions, annual rows and migration."""

import uuid
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.database import get_engine
from app.modules.audit.models import AuditEvent
from app.modules.projects.land_analytics import project_acquisition_total
from tests.factories import client_for, make_user
from tests.modules.conftest import PROJECTS, grant_access, parcel_payload


def create(admin_client: TestClient, project_id: str, **changes: object) -> dict:
    payload = parcel_payload(
        purchase_price="1000000",
        acquisition_fees="1000",
        acquisition_tax_rate_fraction="0.05",
        agent_fee_amount="20000",
        legal_fee_amount="5000",
        registration_fee_amount="3000",
        expected_gdv_amount="5000000",
        **changes,
    )
    response = admin_client.post(f"{PROJECTS}/{project_id}/parcels", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_acquisition_api_and_cost_pool_include_itemized_fees(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    result = create(admin_client, project_id)
    assert result["total_acquisition_cost"] == "1079000.00"
    assert result["agent_fee_rate_fraction"] == "0.020000"
    assert project_acquisition_total(db, project_id=uuid.UUID(project_id)) == 1079000
    url = f"{PROJECTS}/{project_id}/parcels/{result['id']}"
    changed = admin_client.patch(url, json={"purchase_price": "2000000"}).json()
    assert changed["acquisition_tax_amount"] == "100000.00"
    assert changed["agent_fee_rate_fraction"] == "0.010000"
    assert changed["total_acquisition_cost"] == "2129000.00"


def test_annual_rows_upsert_and_recompute_later_years_without_changing_cost(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    result = create(admin_client, project_id)
    url = f"{PROJECTS}/{project_id}/parcels/{result['id']}"
    for year, rate in ((2027, "-0.05"), (2026, "0.10"), (2026, "0.20")):
        response = admin_client.put(
            f"{url}/market-assumptions/{year}", json={"change_rate_fraction": rate}
        )
        assert response.status_code == 200, response.text
    rows = response.json()["market_years"]
    assert [row["year"] for row in rows] == [2026, 2027]
    assert rows[1]["estimated_value"] == "1140000.00"
    assert admin_client.get(url).json()["total_acquisition_cost"] == "1079000.00"
    assert (
        len(
            list(
                db.scalars(
                    select(AuditEvent).where(AuditEvent.action == "land_market_assumption.recorded")
                )
            )
        )
        == 3
    )


def test_land_analytics_hide_financials_and_refuse_cross_project_ids(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    result = create(admin_client, project_id)
    user = make_user(db, email="land-reader@example.com", roles=("sales_advisor",))
    grant_access(admin_client, project_id, user)
    client = client_for(user.email)
    url = f"{PROJECTS}/{project_id}/parcels/{result['id']}"
    redacted = client.get(url).json()
    for field in (
        "agent_fee_amount",
        "acquisition_tax_rate_fraction",
        "expected_gdv_amount",
        "total_acquisition_fees",
    ):
        assert redacted[field] is None
    assert client.get(f"{url}/analytics").status_code == 403
    assert (
        client.put(
            f"{url}/market-assumptions/2026", json={"change_rate_fraction": "0.1"}
        ).status_code
        == 403
    )
    assert (
        admin_client.get(f"{PROJECTS}/{uuid.uuid4()}/parcels/{result['id']}/analytics").status_code
        == 404
    )


def test_invalid_financial_inputs_and_derived_overwrites_are_refused(
    admin_client: TestClient, project_id: str
) -> None:
    result = create(admin_client, project_id)
    url = f"{PROJECTS}/{project_id}/parcels/{result['id']}"
    for payload in (
        {"agent_fee_amount": "-1"},
        {"acquisition_tax_rate_fraction": "1.01"},
        {"total_acquisition_fees": "1"},
    ):
        assert admin_client.patch(url, json=payload).status_code == 422
    assert (
        admin_client.put(
            f"{url}/market-assumptions/2026", json={"change_rate_fraction": "-1.01"}
        ).status_code
        == 422
    )
    assert (
        admin_client.put(
            f"{url}/market-assumptions/1800", json={"change_rate_fraction": "0"}
        ).status_code
        == 422
    )
    cleared = admin_client.patch(url, json={"legal_fee_amount": None}).json()
    assert cleared["legal_fee_amount"] is None
    assert cleared["total_acquisition_cost"] is None


def test_new_monetary_fields_lock_the_project_currency(
    admin_client: TestClient, project_id: str
) -> None:
    # Keep consideration absent: a new GDV or fee alone establishes currency.
    response = admin_client.post(
        f"{PROJECTS}/{project_id}/parcels", json=parcel_payload(expected_gdv_amount="2000000")
    )
    assert response.status_code == 201, response.text
    changed = admin_client.patch(
        f"{PROJECTS}/{project_id}", json={"base_currency_id": str(uuid.uuid4())}
    )
    assert changed.status_code == 409, changed.text


def test_migration_round_trip_preserves_original_land_amounts(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    result = create(admin_client, project_id)
    db.rollback()
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    try:
        command.downgrade(config, "0021_sales_negotiated_price")
        with get_engine().connect() as connection:
            saved = connection.execute(
                text("SELECT purchase_price, acquisition_fees FROM land_parcels WHERE id=:id"),
                {"id": result["id"]},
            ).one()
            assert tuple(saved) == (1000000, 1000)
        command.upgrade(config, "head")
        command.check(config)
        with get_engine().connect() as connection:
            assert connection.scalar(text("SELECT agent_fee_amount FROM land_parcels")) == 0
            assert connection.scalar(text("SELECT count(*) FROM land_market_assumptions")) == 0
    finally:
        command.upgrade(config, "head")


def test_analytics_section_saves_inputs_together(
    admin_client: TestClient,
    project_id: str,
    db: Session,
) -> None:
    parcel = create(admin_client, project_id, acquisition_date="2026-01-01")
    url = f"{PROJECTS}/{project_id}/parcels/{parcel['id']}"
    saved = admin_client.patch(
        f"{url}/analytics",
        json={"expected_gdv_amount": "6000000", "year": 2027, "change_rate_fraction": "-0.05"},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["market_years"][0]["estimated_value"] == "950000.00"
    assert admin_client.get(url).json()["expected_gdv_amount"] == "6000000.00"
    rejected = admin_client.patch(
        f"{url}/analytics",
        json={"expected_gdv_amount": "100", "year": 2025, "change_rate_fraction": "0.1"},
    )
    assert rejected.status_code == 422
    assert admin_client.get(url).json()["expected_gdv_amount"] == "6000000.00"
    assert len(admin_client.get(f"{url}/analytics").json()["market_years"]) == 1
    user = make_user(db, email="analytics-view-only@example.com", roles=("sales_advisor",))
    grant_access(admin_client, project_id, user)
    assert (
        client_for(user.email)
        .patch(f"{url}/analytics", json={"expected_gdv_amount": "200"})
        .status_code
        == 403
    )
    assert (
        admin_client.patch(
            f"{PROJECTS}/{uuid.uuid4()}/parcels/{parcel['id']}/analytics",
            json={"expected_gdv_amount": "200"},
        ).status_code
        == 404
    )


def test_utility_migration_preserves_known_and_unknown_availability(
    admin_client: TestClient,
    project_id: str,
    db: Session,
) -> None:
    parcel = create(admin_client, project_id, power_available=True, water_available=False)
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    db.rollback()
    command.downgrade(config, "0072_company_document_metadata")
    command.upgrade(config, "head")
    command.check(config)
    url = f"{PROJECTS}/{project_id}/parcels/{parcel['id']}"
    migrated = admin_client.get(url).json()
    assert migrated["power_network_availability"] == "available"
    assert migrated["water_network_availability"] == "unavailable"
    assert migrated["sewer_network_availability"] is None
    assert migrated["power_connection_status"] is None
    assert migrated["power_available"] is True
