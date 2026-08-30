"""The control this whole module exists to keep: a schedule must add up exactly.

Not to a tolerance, not with a warning, and not "close enough". A plan that
schedules 199,999 against a contract of 200,000 cannot be put forward, cannot
be approved and cannot be activated, and the refusal says which figure is wrong
and by how much.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from tests.modules.conftest import (
    contract_basis,
    current_version_id,
    fixed_row,
    plan_detail,
    plans_url,
    write_schedule,
)


def test_a_simple_three_line_schedule_reconciles(
    collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    version_id = current_version_id(collections_client, project_id, plan_id)
    basis = contract_basis(collections_client, project_id, plan_id)
    response = write_schedule(
        collections_client,
        project_id,
        plan_id,
        version_id,
        [
            fixed_row(1, "0.200000", "2026-03-01"),
            fixed_row(2, "0.300000", "2026-06-01"),
            fixed_row(3, "0.500000", "2026-09-01"),
        ],
    )
    assert response.status_code == 200, response.text
    reconciliation = response.json()["reconciliation"]
    assert reconciliation["is_reconciled"] is True
    assert reconciliation["scheduled_principal_total"] == basis["principal"]
    assert reconciliation["scheduled_fraction_total"] == "1.000000"
    assert reconciliation["principal_delta"] == "0.00"
    assert reconciliation["fraction_delta"] == "0.000000"
    assert reconciliation["blocking_reasons"] == []


def test_percentages_short_of_the_whole_block_submission(
    collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    version_id = current_version_id(collections_client, project_id, plan_id)
    saved = write_schedule(
        collections_client,
        project_id,
        plan_id,
        version_id,
        [
            fixed_row(1, "0.200000", "2026-03-01"),
            fixed_row(2, "0.300000", "2026-06-01"),
            fixed_row(3, "0.450000", "2026-09-01"),
        ],
    )
    assert saved.status_code == 200
    reconciliation = saved.json()["reconciliation"]
    assert reconciliation["is_reconciled"] is False
    assert reconciliation["scheduled_fraction_total"] == "0.950000"
    # The money is short too: a 95% schedule allocates 95% of the contract and
    # is never quietly rounded up to reconcile.
    assert reconciliation["principal_delta"].startswith("-")
    # The operator is told which figure is wrong, not that the plan is invalid.
    assert any("percentages total" in reason for reason in reconciliation["blocking_reasons"])
    assert any("short by" in reason for reason in reconciliation["blocking_reasons"])

    refused = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/versions/{version_id}/submit", json={}
    )
    assert refused.status_code == 409
    assert "short by" in refused.json()["detail"]


def test_percentages_over_the_whole_block_submission(
    collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    version_id = current_version_id(collections_client, project_id, plan_id)
    write_schedule(
        collections_client,
        project_id,
        plan_id,
        version_id,
        [fixed_row(1, "0.500000", "2026-03-01"), fixed_row(2, "0.600000", "2026-06-01")],
    )
    refused = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/versions/{version_id}/submit", json={}
    )
    assert refused.status_code == 409
    detail = refused.json()["detail"]
    assert "exceeds the contract" in detail
    assert "1.100000" in detail


def test_a_single_missing_fractional_unit_still_blocks(
    collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    """0.999999 is not one. There is no tolerance on a contract."""
    version_id = current_version_id(collections_client, project_id, plan_id)
    saved = write_schedule(
        collections_client,
        project_id,
        plan_id,
        version_id,
        [
            fixed_row(1, "0.500000", "2026-03-01"),
            fixed_row(2, "0.499999", "2026-06-01"),
        ],
    )
    reconciliation = saved.json()["reconciliation"]
    assert reconciliation["scheduled_fraction_total"] == "0.999999"
    assert reconciliation["is_reconciled"] is False
    refused = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/versions/{version_id}/submit", json={}
    )
    assert refused.status_code == 409


def test_a_single_excess_fractional_unit_still_blocks(
    collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    version_id = current_version_id(collections_client, project_id, plan_id)
    saved = write_schedule(
        collections_client,
        project_id,
        plan_id,
        version_id,
        [
            fixed_row(1, "0.500000", "2026-03-01"),
            fixed_row(2, "0.500001", "2026-06-01"),
        ],
    )
    assert saved.json()["reconciliation"]["scheduled_fraction_total"] == "1.000001"
    refused = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/versions/{version_id}/submit", json={}
    )
    assert refused.status_code == 409


def test_a_twenty_row_schedule_reconciles_and_activates(
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    plan_id: str,
) -> None:
    """The explicit MVP acceptance case: no six-instalment limitation anywhere."""
    version_id = current_version_id(collections_client, project_id, plan_id)
    basis = contract_basis(collections_client, project_id, plan_id)
    rows = [
        fixed_row(index + 1, "0.050000", f"2026-{(index % 12) + 1:02d}-01") for index in range(20)
    ]
    saved = write_schedule(collections_client, project_id, plan_id, version_id, rows)
    assert saved.status_code == 200, saved.text
    reconciliation = saved.json()["reconciliation"]
    assert reconciliation["installment_count"] == 20
    assert reconciliation["is_reconciled"] is True
    assert reconciliation["scheduled_principal_total"] == basis["principal"]
    assert reconciliation["scheduled_buyer_total"] == basis["payable"]

    base = f"{plans_url(project_id)}/{plan_id}/versions/{version_id}"
    assert collections_client.post(f"{base}/submit", json={}).status_code == 200
    assert cfo_client.post(f"{base}/approve", json={"reason": "Twenty terms"}).status_code == 200
    activated = cfo_client.post(f"{base}/activate", json={})
    assert activated.status_code == 200, activated.text
    assert activated.json()["version"]["status"] == "active"


def test_a_forty_eight_month_schedule_is_ordinary(
    collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    """A four-year term is a commercial fact, not a schema limit."""
    version_id = current_version_id(collections_client, project_id, plan_id)
    # 47 rows at 0.020833 and one carrying the remainder, so the stored
    # percentages total exactly one.
    each = Decimal("0.020833")
    rows = [
        fixed_row(index + 1, str(each), f"2026-{(index % 12) + 1:02d}-15") for index in range(47)
    ]
    rows.append(fixed_row(48, str(Decimal("1.000000") - each * 47), "2029-12-15"))
    saved = write_schedule(collections_client, project_id, plan_id, version_id, rows)
    assert saved.status_code == 200, saved.text
    reconciliation = saved.json()["reconciliation"]
    assert reconciliation["installment_count"] == 48
    assert reconciliation["is_reconciled"] is True


def test_amount_mode_reconciles_and_derives_the_percentages(
    collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    version_id = current_version_id(collections_client, project_id, plan_id)
    basis = contract_basis(collections_client, project_id, plan_id)
    principal = Decimal(basis["principal"])
    half = (principal / 2).quantize(Decimal("0.01"))
    rows = [
        {
            "sequence": 1,
            "label": "First half",
            "trigger_type": "fixed_date",
            "contractual_due_date": "2026-03-01",
            "principal_amount": str(half),
        },
        {
            "sequence": 2,
            "label": "Second half",
            "trigger_type": "fixed_date",
            "contractual_due_date": "2026-09-01",
            "principal_amount": str(principal - half),
        },
    ]
    saved = write_schedule(
        collections_client, project_id, plan_id, version_id, rows, allocation_mode="amount"
    )
    assert saved.status_code == 200, saved.text
    reconciliation = saved.json()["reconciliation"]
    assert reconciliation["is_reconciled"] is True
    assert reconciliation["scheduled_principal_total"] == basis["principal"]
    # The percentages are derived, and they still total exactly one.
    assert reconciliation["scheduled_fraction_total"] == "1.000000"


def test_amount_mode_short_by_one_unit_blocks(
    collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    version_id = current_version_id(collections_client, project_id, plan_id)
    basis = contract_basis(collections_client, project_id, plan_id)
    short = Decimal(basis["principal"]) - Decimal("0.01")
    rows = [
        {
            "sequence": 1,
            "label": "Almost everything",
            "trigger_type": "fixed_date",
            "contractual_due_date": "2026-03-01",
            "principal_amount": str(short),
        }
    ]
    saved = write_schedule(
        collections_client, project_id, plan_id, version_id, rows, allocation_mode="amount"
    )
    reconciliation = saved.json()["reconciliation"]
    assert reconciliation["principal_delta"] == "-0.01"
    assert reconciliation["is_reconciled"] is False
    refused = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/versions/{version_id}/submit", json={}
    )
    assert refused.status_code == 409
    assert "0.01" in refused.json()["detail"]


def test_the_rounding_residual_is_allocated_not_dropped(
    collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    """Three equal thirds cannot each be exact; the schedule must still add up."""
    version_id = current_version_id(collections_client, project_id, plan_id)
    basis = contract_basis(collections_client, project_id, plan_id)
    saved = write_schedule(
        collections_client,
        project_id,
        plan_id,
        version_id,
        [
            fixed_row(1, "0.333333", "2026-03-01"),
            fixed_row(2, "0.333333", "2026-06-01"),
            fixed_row(3, "0.333334", "2026-09-01"),
        ],
    )
    body = saved.json()
    lines = [Decimal(row["principal_amount"]) for row in body["installments"]]
    assert sum(lines) == Decimal(basis["principal"])
    assert body["reconciliation"]["is_reconciled"] is True


def test_pro_rata_charges_reconcile_against_the_frozen_totals(
    collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    version_id = current_version_id(collections_client, project_id, plan_id)
    basis = contract_basis(collections_client, project_id, plan_id)
    saved = write_schedule(
        collections_client,
        project_id,
        plan_id,
        version_id,
        [
            fixed_row(1, "0.333333", "2026-03-01"),
            fixed_row(2, "0.333333", "2026-06-01"),
            fixed_row(3, "0.333334", "2026-09-01"),
        ],
    )
    reconciliation = saved.json()["reconciliation"]
    assert reconciliation["scheduled_tax_total"] == basis["tax"]
    assert reconciliation["scheduled_fee_total"] == basis["fee"]
    assert reconciliation["tax_delta"] == "0.00"
    assert reconciliation["fee_delta"] == "0.00"
    assert reconciliation["is_reconciled"] is True


def test_the_buyer_total_is_derived_per_line_and_in_total(
    collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    version_id = current_version_id(collections_client, project_id, plan_id)
    basis = contract_basis(collections_client, project_id, plan_id)
    saved = write_schedule(
        collections_client,
        project_id,
        plan_id,
        version_id,
        [fixed_row(1, "0.400000", "2026-03-01"), fixed_row(2, "0.600000", "2026-06-01")],
    )
    body = saved.json()
    for row in body["installments"]:
        expected = (
            Decimal(row["principal_amount"])
            + Decimal(row["tax_amount"])
            + Decimal(row["fee_amount"])
        )
        assert Decimal(row["total_scheduled_amount"]) == expected
    assert body["reconciliation"]["scheduled_buyer_total"] == basis["payable"]
    assert body["reconciliation"]["buyer_total_delta"] == "0.00"


def test_an_empty_schedule_cannot_be_saved(
    collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    version_id = current_version_id(collections_client, project_id, plan_id)
    refused = write_schedule(collections_client, project_id, plan_id, version_id, [])
    # Refused by the schema before it reaches the service.
    assert refused.status_code == 422


def test_two_instalments_cannot_share_a_sequence(
    collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    version_id = current_version_id(collections_client, project_id, plan_id)
    refused = write_schedule(
        collections_client,
        project_id,
        plan_id,
        version_id,
        [fixed_row(1, "0.500000", "2026-03-01"), fixed_row(1, "0.500000", "2026-06-01")],
    )
    assert refused.status_code == 422
    assert "sequence" in refused.json()["detail"].lower()


def test_the_register_reports_the_same_reconciliation_as_the_plan(
    collections_client: TestClient, project_id: str, reconciled_plan: tuple[str, str]
) -> None:
    plan, _version = reconciled_plan
    register = collections_client.get(plans_url(project_id))
    assert register.status_code == 200
    row = next(entry for entry in register.json()["rows"] if entry["plan_id"] == plan)
    detail = plan_detail(collections_client, project_id, plan)["current"]["reconciliation"]
    assert row["is_reconciled"] == detail["is_reconciled"]
    assert row["scheduled_principal_total"] == detail["scheduled_principal_total"]
    assert row["installment_count"] == detail["installment_count"]
    # The register states no cash position, because none exists yet.
    assert "paid" not in str(row)
    assert "outstanding" not in str(row)
