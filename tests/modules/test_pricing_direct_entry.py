"""Direct prices retain approval, immutable basis and quote arithmetic."""

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.factories import client_for, make_user
from tests.modules.conftest import (
    PROJECTS,
    approve_areas,
    inventory_url,
    pricing_url,
    released_unit,
    sales_url,
)


def test_direct_price_without_configuration_requires_separate_approval(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    advisor_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    db: Session,
) -> None:
    approve_areas(admin_client, project_id, unit_id, area_types)
    base_inventory = inventory_url(project_id)
    assert (
        admin_client.patch(
            f"{base_inventory}/area-types/{area_types['BALCONY']}",
            json={"physical_component": "balcony"},
        ).status_code
        == 200
    )
    measured = [
        {"area_type_id": area_types["INTERNAL"], "raw_area": "100"},
        {"area_type_id": area_types["BALCONY"], "raw_area": "20"},
    ]
    for component in ("roof_garden", "front_garden", "terrace", "porches"):
        area = admin_client.post(
            f"{base_inventory}/area-types",
            json={
                "code": component,
                "label": component,
                "area_role": "outdoor",
                "physical_component": component,
                "weight_factor": "0",
            },
        )
        assert area.status_code == 201, area.text
        measured.append({"area_type_id": area.json()["id"], "raw_area": "0"})
    revision = admin_client.post(
        f"{base_inventory}/units/{unit_id}/area-schedules",
        json={"revision_code": "GROSS", "reconciled": True, "values": measured},
    )
    assert revision.status_code == 201, revision.text
    assert (
        admin_client.post(
            f"{base_inventory}/units/{unit_id}/area-schedules/{revision.json()['id']}/approve"
        ).status_code
        == 200
    )
    url = f"{pricing_url(project_id)}/units/{unit_id}"
    payload = {"selling_price": "195123.45", "change_reason": "Approved commercial proposal"}
    assert advisor_client.post(f"{url}/price-versions", json=payload).status_code == 403
    result = finance_client.post(f"{url}/price-versions", json=payload)
    assert result.status_code == 201, result.text
    row = result.json()
    assert row["pricing_configuration_id"] is None
    assert row["reference_price_ex_tax"] == "195123.45"
    assert row["basis_snapshot_json"]["entry_method"] == "direct"
    assert len(row["components"]) == 1
    assert row["components"][0]["final_amount"] == "195123.45"
    base = f"{pricing_url(project_id)}/price-versions/{row['id']}"
    assert cfo_client.post(f"{base}/activate").status_code == 409
    assert finance_client.post(f"{base}/submit", json={}).status_code == 200
    assert admin_client.post(f"{base}/approve", json={"reason": "Reviewed"}).status_code == 403
    assert finance_client.patch(base, json={"change_reason": "Mutate submitted"}).status_code == 409
    assert cfo_client.post(f"{base}/approve", json={"reason": "Reviewed"}).status_code == 200
    assert cfo_client.post(f"{base}/activate").status_code == 200
    quote = finance_client.post(f"{url}/quote-preview", json={})
    assert quote.status_code == 200, quote.text
    assert Decimal(quote.json()["net_contract_price_ex_tax"]) == Decimal("195123.45")
    assert db.scalar(text("SELECT count(*) FROM pricing_configurations")) == 0
    read = advisor_client.get(url)
    assert read.status_code == 200, read.text
    assert read.json()["active_price"]["reference_price_ex_tax"] == "195123.45"
    assert read.json()["price_per_gross_area"] == "1626.03"
    maker = make_user(db, email="direct-maker@example.com", roles=("finance", "approver_cfo"))
    assert admin_client.put(f"{PROJECTS}/{project_id}/access/{maker.id}").status_code == 200
    maker_client = client_for(maker.email)
    own = maker_client.post(f"{url}/price-versions", json=payload)
    assert own.status_code == 201, own.text
    own_base = f"{pricing_url(project_id)}/price-versions/{own.json()['id']}"
    assert finance_client.post(f"{own_base}/submit", json={}).status_code == 200
    assert (
        maker_client.post(f"{own_base}/approve", json={"reason": "Self review"}).status_code == 403
    )
    approve_areas(admin_client, project_id, unit_id, area_types, internal="101", revision="R2")
    assert finance_client.post(f"{url}/quote-preview", json={}).status_code == 409
    assert advisor_client.get(url).json()["repricing_required"] is True

    db.rollback()
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    with pytest.raises(RuntimeError, match="Direct price history exists"):
        command.downgrade(config, "0013_unit_master")


def test_direct_price_validates_amount_reason_and_exclusive_inputs(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
) -> None:
    url = f"{pricing_url(project_id)}/units/{unit_id}/price-versions"
    payload = {"selling_price": "100000", "change_reason": "Launch"}
    assert finance_client.post(url, json=payload).status_code == 409
    approve_areas(admin_client, project_id, unit_id, area_types)
    for change in (
        {"selling_price": "0"},
        {"selling_price": "-1"},
        {"selling_price": "NaN"},
        {"change_reason": " "},
        {"internal_rate_override": "12"},
    ):
        response = finance_client.post(url, json={**payload, **change})
        assert response.status_code == 422, response.text
    record = admin_client.get(f"{inventory_url(project_id)}/units/{unit_id}").json()
    assert record["pricing_approved"] is False


def test_direct_price_flows_into_a_reservation_and_contract_with_explicit_dates(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    sales_ops_client: TestClient,
    buyer_id: str,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
) -> None:
    approve_areas(admin_client, project_id, unit_id, area_types)
    price = finance_client.post(
        f"{pricing_url(project_id)}/units/{unit_id}/price-versions",
        json={"selling_price": "200000.00", "change_reason": "Launch"},
    )
    assert price.status_code == 201, price.text
    version = price.json()["id"]
    base = f"{pricing_url(project_id)}/price-versions/{version}"
    assert finance_client.post(f"{base}/submit", json={}).status_code == 200
    assert cfo_client.post(f"{base}/approve", json={"reason": "Reviewed"}).status_code == 200
    assert cfo_client.post(f"{base}/activate").status_code == 200
    released_unit.__wrapped__(admin_client, project_id, unit_id, version)
    today = date.today()
    payload = {
        "unit_id": unit_id,
        "client_id": buyer_id,
        "sales_channel_code": "DIRECT",
        "sales_branch_code": "AMMAN",
        "deposit_required_amount": "5000",
    }
    assert (
        sales_ops_client.post(f"{sales_url(project_id)}/reservations", json=payload).status_code
        == 422
    )
    result = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations",
        json={
            **payload,
            "expires_on": (today + timedelta(days=7)).isoformat(),
            "price_locked_until": (today + timedelta(days=14)).isoformat(),
        },
    )
    assert result.status_code == 201, result.text
    reservation = result.json()["reservation"]
    assert reservation["net_contract_price_ex_tax"] == "200000.00"
    reservation_base = f"{sales_url(project_id)}/reservations/{reservation['id']}"
    assert (
        sales_ops_client.post(
            f"{reservation_base}/confirm-deposit", json={"evidence_reference": "TEST-BANK"}
        ).status_code
        == 200
    )
    assert sales_ops_client.post(f"{reservation_base}/activate", json={}).status_code == 200
    lock = (today + timedelta(days=21)).isoformat()
    requote = sales_ops_client.post(
        f"{reservation_base}/requote", json={"reason": "Renew offer", "price_locked_until": lock}
    )
    assert requote.status_code == 200, requote.text
    assert requote.json()["reservation"]["price_locked_until"] == lock
    contract = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts",
        json={"reservation_id": reservation["id"], "spa_number": "DIRECT-01"},
    )
    assert contract.status_code == 201, contract.text
    assert contract.json()["sale"]["unit_price_version_id"] == version
