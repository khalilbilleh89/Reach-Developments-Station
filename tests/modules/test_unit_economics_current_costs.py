"""Live signed cost, gross-built allocation and explicitly configured profit tax."""

from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.modules.conftest import economics_url, inventory_url, pricing_url
from tests.modules.test_construction_contract_first import signed


@pytest.fixture
def current_inputs(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    currency_id: str,
    priced_pair: tuple[str, str],
    area_types: dict[str, str],
) -> dict[str, Any]:
    created = admin_client.post(
        f"{inventory_url(project_id)}/area-types",
        json={
            "code": "BUILT",
            "label": "Gross built including covered areas",
            "area_role": "gross",
            "unit_of_measure": "sqm",
            "weight_factor": "0.000000",
            "required_for_release": False,
        },
    )
    assert created.status_code == 201, created.text
    area_id = created.json()["id"]
    for unit_id, size, internal, balcony in zip(
        priced_pair, ("120", "80"), ("100", "60"), ("20", "8"), strict=True
    ):
        measured = admin_client.post(
            f"{inventory_url(project_id)}/units/{unit_id}/area-schedules",
            json={
                "revision_code": "BUILT",
                "reconciled": True,
                "values": [
                    {"area_type_id": area_types["INTERNAL"], "raw_area": internal},
                    {"area_type_id": area_types["BALCONY"], "raw_area": balcony},
                    {"area_type_id": area_id, "raw_area": size},
                ],
            },
        )
        assert measured.status_code == 201, measured.text
        approval = admin_client.post(
            f"{inventory_url(project_id)}/units/{unit_id}/area-schedules/{measured.json()['id']}/approve"
        )
        assert approval.status_code == 200, approval.text
        unit = admin_client.get(f"{inventory_url(project_id)}/units/{unit_id}").json()
        if unit["commercial_status"] != "sold":
            price = finance_client.post(
                f"{pricing_url(project_id)}/units/{unit_id}/price-versions", json={}
            )
            assert price.status_code == 201, price.text
            price_url = f"{pricing_url(project_id)}/price-versions/{price.json()['id']}"
            assert finance_client.post(f"{price_url}/submit", json={}).status_code == 200
            assert (
                cfo_client.post(
                    f"{price_url}/approve", json={"reason": "Built measurement confirmed"}
                ).status_code
                == 200
            )
            assert cfo_client.post(f"{price_url}/activate").status_code == 200
    signed(finance_client, project_id, currency_id, original_contract_value_ex_tax="100000.00")
    return {
        "gross_area_type_id": area_id,
        "supplemental_soft_cost": "10000.00",
        "additional_cost": "2000.00",
        "finance_cost": "1000.00",
        "commission_rate_fraction": "0.020000",
        "profit_tax_rate_fraction": "0.200000",
        "expected_revision": 0,
        "reason": "Opening current cost analysis",
    }


def save(client: TestClient, project_id: str, body: dict[str, Any]) -> dict[str, Any]:
    response = client.put(f"{economics_url(project_id)}/current-cost-analysis/settings", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_area_allocation_cost_layers_loss_tax_and_group_reconciliation(
    finance_client: TestClient, project_id: str, current_inputs: dict[str, Any], land_cost: str
) -> None:
    report = save(finance_client, project_id, current_inputs)
    first, second = report["units"]
    assert first["hard_cost"] == "60000.00"
    assert second["hard_cost"] == "40000.00"
    assert first["hard_cost_per_sqm"] == second["hard_cost_per_sqm"] == "500.00"
    assert first["land_cost"] == "504000.00"
    assert first["soft_cost"] == "6000.00"
    assert first["additional_cost"] == "1200.00"
    assert first["finance_cost"] == "600.00"
    assert first["commission_cost"] == "3300.00"
    assert first["total_cost"] == "575100.00"
    assert first["profit_before_tax"] == "-410100.00"
    assert first["tax_amount"] == "0.00"
    assert first["net_profit"] == first["profit_before_tax"]
    for field in (
        "hard_cost",
        "land_cost",
        "soft_cost",
        "additional_cost",
        "finance_cost",
        "commission_cost",
        "total_cost",
        "revenue",
        "profit_before_tax",
        "tax_amount",
        "net_profit",
    ):
        assert Decimal(report["project"][field]) == sum(Decimal(u[field]) for u in report["units"])
        assert (
            report["buildings"][0][field] == report["floors"][0][field] == report["project"][field]
        )
    assert report["project"]["gross_area_sqm"] == "200.0000"
    assert report["project"]["sold_count"] == 0
    assert report["project"]["cost_complete_count"] == 2


def test_positive_profit_tax_unknown_rate_and_stale_write(
    finance_client: TestClient,
    project_id: str,
    current_inputs: dict[str, Any],
    land_cost: str,
    db: Session,
) -> None:
    db.execute(
        text("UPDATE land_parcels SET purchase_price=0, acquisition_fees=0 WHERE id=:id"),
        {"id": land_cost},
    )
    db.commit()
    report = save(finance_client, project_id, current_inputs)
    first = report["units"][0]
    assert first["total_cost"] == "71100.00"
    assert first["profit_before_tax"] == "93900.00"
    assert first["tax_amount"] == "18780.00"
    assert first["net_profit"] == "75120.00"
    url = f"{economics_url(project_id)}/current-cost-analysis/settings"
    assert finance_client.put(url, json=current_inputs).status_code == 409
    current_inputs.update(expected_revision=1, profit_tax_rate_fraction=None)
    unknown = save(finance_client, project_id, current_inputs)
    assert unknown["units"][0]["profit_before_tax"] == "93900.00"
    assert unknown["units"][0]["net_profit"] is None


def test_missing_area_never_shrinks_denominator(
    finance_client: TestClient,
    project_id: str,
    current_inputs: dict[str, Any],
    land_cost: str,
    db: Session,
    priced_pair: tuple[str, str],
) -> None:
    db.execute(
        text(
            "DELETE FROM unit_area_values WHERE area_type_id=:area "
            "AND unit_area_schedule_id IN "
            "(SELECT id FROM unit_area_schedules WHERE unit_id=:unit)"
        ),
        {"area": current_inputs["gross_area_type_id"], "unit": priced_pair[1]},
    )
    db.commit()
    report = save(finance_client, project_id, current_inputs)
    assert all(u["hard_cost"] is None and u["total_cost"] is None for u in report["units"])
    assert report["project"]["net_profit"] is None
    assert any("shared allocation is unavailable" in i for i in report["issues"])


def test_audited_delete_repeated_delete_and_denied_role(
    finance_client: TestClient,
    sales_ops_client: TestClient,
    project_id: str,
    current_inputs: dict[str, Any],
    db: Session,
) -> None:
    save(finance_client, project_id, current_inputs)
    url = f"{economics_url(project_id)}/current-cost-analysis/settings"
    assert sales_ops_client.put(url, json=current_inputs).status_code == 403
    assert (
        sales_ops_client.delete(url, params={"revision": 1, "reason": "Remove"}).status_code == 403
    )
    assert finance_client.delete(url, params={"revision": 2, "reason": "Remove"}).status_code == 409
    assert (
        finance_client.delete(
            url, params={"revision": 1, "reason": "Superseded inputs"}
        ).status_code
        == 204
    )
    assert finance_client.delete(url, params={"revision": 1, "reason": "Repeat"}).status_code == 404
    assert (
        db.scalar(
            text(
                "SELECT count(*) FROM audit_events "
                "WHERE action='unit_economics.current_settings_deleted'"
            )
        )
        == 1
    )


def test_signed_sale_commission_grant_counted_once(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    active_sale: str,
    current_inputs: dict[str, Any],
    land_cost: str,
    unit_id: str,
) -> None:
    base = f"/api/v1/projects/{project_id}/commissions"
    created = finance_client.post(
        base,
        json={
            "sale_contract_id": active_sale,
            "commissionable_base_amount": "100000.00",
            "granted_rate_fraction": "0.100000",
        },
    )
    assert created.status_code == 201, created.text
    grant = created.json()
    allocation = finance_client.post(
        f"{base}/{grant['id']}/allocations",
        json={"beneficiary_name": "Agent", "rate_fraction": "0.100000"},
    )
    assert allocation.status_code == 200, allocation.text
    manual = finance_client.post(
        f"{economics_url(project_id)}/units/{unit_id}/costs",
        json={
            "cost_type": "sales_commission",
            "basis": "actual",
            "sale_contract_id": active_sale,
            "amount": "10000.00",
            "effective_date": "2026-09-20",
        },
    )
    assert manual.status_code == 201, manual.text
    report = save(finance_client, project_id, current_inputs)
    sold = next(u for u in report["units"] if u["unit_id"] == unit_id)
    assert sold["revenue_basis"] == "sold"
    assert sold["commission_cost"] == "10000.00"
    assert sold["direct_cost"] == "0.00"
    assert sold["commission_basis"] == "draft grant provision"
    assert any("counted once" in issue for issue in sold["issues"])
    assert report["project"]["sold_count"] == 1
    released = cfo_client.post(f"{base}/{grant['id']}/release")
    assert released.status_code == 200, released.text
    after = finance_client.get(f"{economics_url(project_id)}/current-cost-analysis").json()
    assert after["project"]["commission_cost"] == report["project"]["commission_cost"]


def test_approved_reduction_updates_unit_cost_payment_does_not(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    currency_id: str,
    current_inputs: dict[str, Any],
    land_cost: str,
) -> None:
    base = f"/api/v1/projects/{project_id}/construction"
    contract = finance_client.get(f"{base}/contracts").json()[0]
    detail = finance_client.get(f"{base}/contracts/{contract['id']}").json()
    report = save(finance_client, project_id, current_inputs)
    from tests.modules.test_construction_contract_first import payment

    paid = payment(finance_client, base, contract["id"], currency_id, amount="1000.00")
    assert paid.status_code == 201, paid.text
    change = finance_client.post(
        f"{base}/contracts/{contract['id']}/variations",
        json={
            "variation_number": "CLIENT",
            "description": "Client supplied windows",
            "requested_date": "2026-09-20",
            "cost_code_id": detail["lines"][0]["cost_code_id"],
            "adjustment_amount": "10000.00",
            "adjustment_kind": "reduction",
        },
    )
    assert change.status_code == 201, change.text
    url = f"{economics_url(project_id)}/current-cost-analysis"
    pending = finance_client.get(url).json()
    assert pending["project"]["hard_cost"] == report["project"]["hard_cost"]
    variation = f"{base}/variations/{change.json()['id']}"
    assert finance_client.post(f"{variation}/submit", json={}).status_code == 200
    assert cfo_client.post(f"{variation}/approve", json={}).status_code == 200
    revised = finance_client.get(url).json()
    assert revised["project"]["hard_cost"] == "90000.00"
    assert revised["units"][0]["hard_cost"] == "54000.00"
    assert revised["units"][1]["hard_cost"] == "36000.00"


def test_current_settings_migration_roundtrip(db: Session) -> None:
    from alembic import command

    from tests.conftest import alembic_config

    db.commit()
    config = alembic_config()
    command.downgrade(config, "0033_contract_payments")
    command.upgrade(config, "head")
    assert db.scalar(text("SELECT count(*) FROM ue_current_cost_settings")) == 0


def test_wrong_project_and_selected_phase_cannot_read_or_change_inputs(
    finance_client: TestClient,
    admin_client: TestClient,
    project_id: str,
    current_inputs: dict[str, Any],
    db: Session,
) -> None:
    import uuid

    from tests.factories import client_for, make_user
    from tests.modules.conftest import PROJECTS, grant_access

    save(finance_client, project_id, current_inputs)
    stranger = str(uuid.uuid4())
    assert finance_client.get(f"{economics_url(stranger)}/current-cost-analysis").status_code == 404
    assert (
        finance_client.delete(
            f"{economics_url(stranger)}/current-cost-analysis/settings",
            params={"revision": 1, "reason": "Remove"},
        ).status_code
        == 404
    )
    scoped = make_user(db, email="current-cost-scoped@example.com", roles=("finance",))
    grant_access(admin_client, project_id, scoped)
    narrowed = admin_client.patch(
        f"{PROJECTS}/{project_id}/access/{scoped.id}/phase-scope", json={"phase_scope": "selected"}
    )
    assert narrowed.status_code == 200, narrowed.text
    client = client_for(scoped.email)
    base = f"{economics_url(project_id)}/current-cost-analysis"
    assert client.get(base).status_code == 403
    assert (
        client.put(f"{base}/settings", json={**current_inputs, "expected_revision": 1}).status_code
        == 403
    )
    assert (
        client.delete(f"{base}/settings", params={"revision": 1, "reason": "Remove"}).status_code
        == 403
    )


def test_missing_land_and_explicit_zero_tax_are_distinct(
    finance_client: TestClient,
    project_id: str,
    current_inputs: dict[str, Any],
) -> None:
    current_inputs["profit_tax_rate_fraction"] = "0"
    report = save(finance_client, project_id, current_inputs)
    assert report["settings"]["profit_tax_rate_fraction"] == "0.000000"
    assert report["units"][0]["hard_cost"] == "60000.00"
    assert report["units"][0]["land_cost"] is None
    assert report["units"][0]["net_profit"] is None
    assert any("Land acquisition" in issue for issue in report["issues"])


def test_currency_mismatch_refuses_totals_and_settings_downgrade_is_guarded(
    finance_client: TestClient,
    admin_client: TestClient,
    project_id: str,
    current_inputs: dict[str, Any],
    land_cost: str,
    db: Session,
) -> None:
    from alembic import command

    from tests.conftest import alembic_config

    report = save(finance_client, project_id, current_inputs)
    assert report["project"]["total_cost"] is not None
    foreign = admin_client.post(
        "/api/v1/settings/currencies", json={"code": "USD", "name": "US Dollar"}
    )
    assert foreign.status_code == 201, foreign.text
    db.execute(
        text("UPDATE construction_contracts SET currency_id=:currency WHERE project_id=:project"),
        {"currency": foreign.json()["id"], "project": project_id},
    )
    db.commit()
    incompatible = finance_client.get(f"{economics_url(project_id)}/current-cost-analysis")
    assert incompatible.status_code == 200, incompatible.text
    assert incompatible.json()["project"]["total_cost"] is None
    with pytest.raises(RuntimeError, match="removed with audit"):
        command.downgrade(alembic_config(), "0033_contract_payments")


def test_stale_unsold_price_is_unavailable(
    finance_client: TestClient,
    project_id: str,
    current_inputs: dict[str, Any],
    land_cost: str,
    priced_pair: tuple[str, str],
    db: Session,
) -> None:
    report = save(finance_client, project_id, current_inputs)
    assert report["units"][0]["revenue"] == "165000.00"
    db.execute(text("UPDATE units SET pricing_approved=false WHERE id=:id"), {"id": priced_pair[0]})
    db.commit()
    after = finance_client.get(f"{economics_url(project_id)}/current-cost-analysis").json()
    assert after["units"][0]["revenue"] is None
    assert after["units"][0]["net_profit"] is None
    assert any("reapproval" in issue for issue in after["units"][0]["issues"])
