"""One synthetic unit traverses the combined MVP 2 application, not isolated PRs.

The shared API fixtures build hierarchy, buyer/purchaser, reservation, SPA,
signatures and reconciled/approved/active payment plan. This file overrides the
price fixture so that entire flow is based on a six-component direct price,
without a pricing policy. Browser/accessibility acceptance remains separate.
"""

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.modules.conftest import (
    allocate,
    collection_account,
    confirm_receipt,
    construction_url,
    inventory_url,
    pricing_url,
    record_legal,
    record_receipt,
    sales_url,
)
from tests.modules.test_construction_stage_configuration import snapshot


@pytest.fixture
def reservation_id(
    sales_ops_client: TestClient,
    project_id: str,
    released_unit: str,
    buyer_id: str,
) -> str:
    response = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations",
        json={
            "unit_id": released_unit,
            "client_id": buyer_id,
            "sales_channel_code": "DIRECT",
            "sales_branch_code": "AMMAN",
            "deposit_required_amount": "5000.00",
            "expires_on": str(date.today() + timedelta(days=7)),
            "price_locked_until": str(date.today() + timedelta(days=14)),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["reservation"]["id"]


@pytest.fixture
def priced_unit(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
) -> str:
    root = inventory_url(project_id)
    types = {"internal": area_types["INTERNAL"], "balcony": area_types["BALCONY"]}
    assert (
        admin_client.patch(
            f"{root}/area-types/{types['balcony']}", json={"physical_component": "balcony"}
        ).status_code
        == 200
    )
    for component in ("roof_garden", "front_garden", "terrace", "porches"):
        response = admin_client.post(
            f"{root}/area-types",
            json={
                "code": component,
                "label": component,
                "physical_component": component,
                "area_role": "outdoor",
                "weight_factor": "0",
            },
        )
        assert response.status_code == 201, response.text
        types[component] = response.json()["id"]
    measured = admin_client.post(
        f"{root}/units/{unit_id}/area-schedules",
        json={
            "revision_code": "CLOSE-1",
            "reconciled": True,
            "values": [
                {"area_type_id": types[key], "raw_area": value}
                for key, value in zip(types, ("100", "20", "30", "40", "5", "5"), strict=True)
            ],
        },
    )
    assert measured.status_code == 201, measured.text
    assert (
        admin_client.post(
            f"{root}/units/{unit_id}/area-schedules/{measured.json()['id']}/approve"
        ).status_code
        == 200
    )
    for kind in ("parking", "storage"):
        assert (
            admin_client.post(
                f"{root}/sub-assets",
                json={
                    "asset_reference": kind,
                    "asset_type": kind,
                    "linked_unit_id": unit_id,
                    "transfer_mode": "attached",
                    "area": "999",
                },
            ).status_code
            == 201
        )
    assert (
        admin_client.post(
            f"{root}/units/{unit_id}/features", json={"label": "Sea view"}
        ).status_code
        == 201
    )
    assert (
        admin_client.post(
            f"{root}/units/{unit_id}/documents",
            json={
                "title": "Synthetic plan",
                "url": "https://example.com/plan.pdf",
                "revision": "A",
            },
        ).status_code
        == 201
    )
    assert Decimal(admin_client.get(f"{root}/units/{unit_id}").json()["gross_area"]) == 200
    priced = finance_client.post(
        f"{pricing_url(project_id)}/units/{unit_id}/price-versions",
        json={
            "selling_price": "200000.00",
            "change_reason": "Closure direct price",
        },
    )
    assert priced.status_code == 201, priced.text
    version = priced.json()["id"]
    assert priced.json()["pricing_configuration_id"] is None
    path = f"{pricing_url(project_id)}/price-versions/{version}"
    assert finance_client.post(f"{path}/submit", json={}).status_code == 200
    assert (
        cfo_client.post(f"{path}/approve", json={"reason": "Independent review"}).status_code == 200
    )
    assert cfo_client.post(f"{path}/activate").status_code == 200
    return version


def test_combined_direct_sale_cash_and_physical_progress(
    db: Session,
    admin_client: TestClient,
    finance_client: TestClient,
    collections_client: TestClient,
    legal_client: TestClient,
    manager_member_client: TestClient,
    project_id: str,
    unit_id: str,
    second_unit: str,
    active_sale: str,
    active_plan: tuple[str, str],
) -> None:
    assert db.scalar(text("SELECT count(*) FROM pricing_configurations")) == 0
    price_root = f"{pricing_url(project_id)}/units/{unit_id}"
    price = finance_client.get(price_root).json()
    assert Decimal(price["price_per_gross_area"]) == 1000
    active = price["active_price"]["id"]
    draft = finance_client.post(
        f"{price_root}/price-versions",
        json={
            "selling_price": "210000.00",
            "change_reason": "Unapproved proposal",
        },
    )
    assert draft.status_code == 201, draft.text
    assert finance_client.get(price_root).json()["active_price"]["id"] == active
    record_legal(legal_client, project_id, active_sale, "land_registry_lodged", "2026-02-10")
    unit = admin_client.get(f"{inventory_url(project_id)}/units/{unit_id}").json()
    assert unit["legal_status"] == "lodged_submitted"
    recorded = record_receipt(collections_client, project_id, active_sale, "10000.00", "2026-03-02")
    assert recorded.status_code == 201, recorded.text
    before = collection_account(collections_client, project_id, active_sale)
    assert Decimal(before["confirmed_receipts_total"]) == 0
    assert Decimal(before["collected_percentage"]) == 0
    assert confirm_receipt(finance_client, project_id, recorded.json()["id"]).status_code == 200
    cash = collection_account(collections_client, project_id, active_sale)
    assert Decimal(cash["confirmed_receipts_total"]) == 10000
    assert Decimal(cash["collected_percentage"]) == (
        Decimal("10000") / Decimal(cash["spa_total_payable"]) * 100
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    assert Decimal(cash["refund_confirmed_total"]) == 0
    assert Decimal(cash["unapplied_cash"]) == 10000
    assert (
        allocate(
            collections_client,
            project_id,
            recorded.json()["id"],
            cash["installments"][0]["installment_id"],
            "5000.00",
        ).status_code
        == 201
    )
    cash = collection_account(collections_client, project_id, active_sale)
    assert Decimal(cash["unapplied_cash"]) == 5000
    historical = collection_account(collections_client, project_id, active_sale, as_of="2026-03-01")
    assert Decimal(historical["confirmed_receipts_total"]) == 0
    standing = admin_client.get(f"{inventory_url(project_id)}/units/{unit_id}").json()
    root = construction_url(project_id)
    client = manager_member_client
    stage = client.post(f"{root}/stages", json={"name": "Structure"}).json()
    finish = client.post(f"{root}/stages", json={"name": "Finishes"}).json()
    moved = client.patch(
        f"{root}/stages/{stage['id']}",
        json=snapshot(
            stage, name="Structural Works", sequence=2, expected_order=[stage["id"], finish["id"]]
        ),
    )
    assert moved.status_code == 200, moved.text
    path = f"{root}/units/{unit_id}/stages"
    for revision, day in enumerate(("2026-08-01", "2026-08-02")):
        assert (
            client.post(
                f"{path}/{stage['id']}/completion",
                json={
                    "completed_date": day,
                    "reason": "Synthetic inspection",
                    "expected_revision": revision,
                },
            ).status_code
            == 204
        )
    assert client.get(f"{root}/units/{second_unit}/stages").json()["completed_count"] == 0
    progress = client.get(path).json()
    assert progress["completed_count"] == 1
    assert len(progress["stages"][1]["history"]) == 2
    assert collection_account(collections_client, project_id, active_sale) == cash
    after = admin_client.get(f"{inventory_url(project_id)}/units/{unit_id}").json()
    for dimension in ("legal_status", "commercial_status", "delivery_status", "collection_status"):
        assert after[dimension] == standing[dimension]
