"""Sanctioning a schedule, activating it, and revising it without a gap.

Two rules under test throughout: the person who prepares a schedule does not
sanction it, and a contracted buyer is never left without a governing schedule
merely because its replacement is being drafted.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.modules.conftest import (
    current_version_id,
    fixed_row,
    plan_detail,
    plans_url,
    sales_url,
    write_schedule,
)


def _base(project_id: str, plan_id: str, version_id: str) -> str:
    return f"{plans_url(project_id)}/{plan_id}/versions/{version_id}"


def test_a_reconciled_schedule_can_be_put_forward_and_sanctioned(
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    reconciled_plan: tuple[str, str],
) -> None:
    plan_id, version_id = reconciled_plan
    base = _base(project_id, plan_id, version_id)
    submitted = collections_client.post(f"{base}/submit", json={})
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["version"]["status"] == "submitted"
    approved = cfo_client.post(f"{base}/approve", json={"reason": "Terms reviewed"})
    assert approved.status_code == 200, approved.text
    assert approved.json()["version"]["status"] == "approved"


def test_the_submitter_cannot_sanction_their_own_schedule(
    collections_client: TestClient, project_id: str, reconciled_plan: tuple[str, str]
) -> None:
    plan_id, version_id = reconciled_plan
    base = _base(project_id, plan_id, version_id)
    collections_client.post(f"{base}/submit", json={})
    refused = collections_client.post(f"{base}/approve", json={"reason": "Mine"})
    assert refused.status_code == 403


def test_an_administrator_cannot_sanction_a_schedule(
    collections_client: TestClient,
    admin_client: TestClient,
    project_id: str,
    reconciled_plan: tuple[str, str],
) -> None:
    """Configuring a platform is not authority over its receivables."""
    plan_id, version_id = reconciled_plan
    base = _base(project_id, plan_id, version_id)
    collections_client.post(f"{base}/submit", json={})
    refused = admin_client.post(f"{base}/approve", json={"reason": "Admin says so"})
    assert refused.status_code == 403


def test_a_refused_schedule_stays_refused_and_readable(
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    reconciled_plan: tuple[str, str],
) -> None:
    plan_id, version_id = reconciled_plan
    base = _base(project_id, plan_id, version_id)
    collections_client.post(f"{base}/submit", json={})
    rejected = cfo_client.post(f"{base}/reject", json={"reason": "Front-loaded too heavily"})
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["version"]["status"] == "rejected"
    assert rejected.json()["version"]["rejection_reason"] == "Front-loaded too heavily"

    # It cannot be edited back into a draft; the revision is a new version.
    refused = write_schedule(
        collections_client,
        project_id,
        plan_id,
        version_id,
        [fixed_row(1, "1.000000", "2026-03-01")],
    )
    assert refused.status_code == 409
    assert "new version" in refused.json()["detail"]


def test_a_submitted_schedule_is_immutable(
    collections_client: TestClient, project_id: str, reconciled_plan: tuple[str, str]
) -> None:
    plan_id, version_id = reconciled_plan
    collections_client.post(f"{_base(project_id, plan_id, version_id)}/submit", json={})
    refused = write_schedule(
        collections_client,
        project_id,
        plan_id,
        version_id,
        [fixed_row(1, "1.000000", "2026-03-01")],
    )
    assert refused.status_code == 409


def test_an_active_schedule_is_immutable(
    collections_client: TestClient, project_id: str, active_plan: tuple[str, str]
) -> None:
    plan_id, version_id = active_plan
    refused = write_schedule(
        collections_client,
        project_id,
        plan_id,
        version_id,
        [fixed_row(1, "1.000000", "2026-03-01")],
    )
    assert refused.status_code == 409


def test_a_schedule_cannot_activate_while_the_contract_awaits_signature(
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    submitted_sale: str,
) -> None:
    """A live receivable schedule needs a live contract."""
    created = collections_client.post(
        plans_url(project_id),
        json={"sale_contract_id": submitted_sale, "name": "Prepared early"},
    )
    plan_id = created.json()["plan"]["id"]
    version_id = created.json()["current"]["version"]["id"]
    write_schedule(
        collections_client,
        project_id,
        plan_id,
        version_id,
        [fixed_row(1, "1.000000", "2026-03-01")],
    )
    base = _base(project_id, plan_id, version_id)
    assert collections_client.post(f"{base}/submit", json={}).status_code == 200
    assert cfo_client.post(f"{base}/approve", json={"reason": "Fine"}).status_code == 200
    refused = cfo_client.post(f"{base}/activate", json={})
    assert refused.status_code == 409
    assert "live contract" in refused.json()["detail"]


def test_a_future_dated_schedule_cannot_be_activated_early(
    collections_client: TestClient,
    cfo_client: TestClient,
    db: Session,
    project_id: str,
    approved_plan: tuple[str, str],
) -> None:
    """Approved and future-dated stays approved. There is no scheduler."""
    plan_id, version_id = approved_plan
    later = date.today() + timedelta(days=30)
    db.execute(
        text("UPDATE payment_plan_versions SET effective_date = :d WHERE id = :i"),
        {"d": later, "i": version_id},
    )
    db.commit()
    refused = cfo_client.post(f"{_base(project_id, plan_id, version_id)}/activate", json={})
    assert refused.status_code == 409
    assert later.isoformat() in refused.json()["detail"]

    # Nothing was half-done: the version is still approved and nothing is active.
    body = plan_detail(collections_client, project_id, plan_id)
    assert body["current"]["version"]["status"] == "approved"
    assert body["active_version_id"] is None


def test_activation_materialises_dated_triggers_only(
    collections_client: TestClient, project_id: str, active_plan: tuple[str, str]
) -> None:
    plan_id, _version_id = active_plan
    body = plan_detail(collections_client, project_id, plan_id)
    assert body["current"]["version"]["status"] == "active"
    for row in body["current"]["installments"]:
        assert row["actual_due_date"] == row["contractual_due_date"]
        assert row["trigger_status"] == "scheduled"


def test_a_revision_leaves_the_standing_schedule_governing(
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    active_plan: tuple[str, str],
) -> None:
    """There is never a gap where a contracted buyer has no schedule."""
    plan_id, first_version = active_plan
    created = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/versions",
        json={"change_reason": "Buyer requested a longer tail"},
    )
    assert created.status_code == 201, created.text
    second_version = created.json()["version"]["id"]
    assert created.json()["version"]["version_number"] == 2
    assert created.json()["version"]["origin_type"] == "copied_plan"
    # The shape came across, so the revision starts from what was agreed.
    assert created.json()["reconciliation"]["installment_count"] == 3
    assert created.json()["reconciliation"]["is_reconciled"] is True

    body = plan_detail(collections_client, project_id, plan_id)
    assert body["active_version_id"] == first_version

    base = _base(project_id, plan_id, second_version)
    assert collections_client.post(f"{base}/submit", json={}).status_code == 200
    # Still governed by version 1 while its replacement is being sanctioned.
    assert plan_detail(collections_client, project_id, plan_id)["active_version_id"] == (
        first_version
    )
    assert cfo_client.post(f"{base}/approve", json={"reason": "Agreed"}).status_code == 200
    assert plan_detail(collections_client, project_id, plan_id)["active_version_id"] == (
        first_version
    )

    assert cfo_client.post(f"{base}/activate", json={}).status_code == 200
    body = plan_detail(collections_client, project_id, plan_id)
    assert body["active_version_id"] == second_version
    statuses = {row["id"]: row["status"] for row in body["versions"]}
    assert statuses[first_version] == "superseded"
    assert statuses[second_version] == "active"


def test_a_superseded_schedule_remains_readable(
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    active_plan: tuple[str, str],
) -> None:
    plan_id, first_version = active_plan
    second = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/versions", json={"change_reason": "Revised"}
    ).json()["version"]["id"]
    base = _base(project_id, plan_id, second)
    collections_client.post(f"{base}/submit", json={})
    cfo_client.post(f"{base}/approve", json={"reason": "Agreed"})
    cfo_client.post(f"{base}/activate", json={})

    historical = collections_client.get(_base(project_id, plan_id, first_version))
    assert historical.status_code == 200
    assert historical.json()["version"]["status"] == "superseded"
    # Its instalments were not overwritten by the replacement.
    assert historical.json()["reconciliation"]["installment_count"] == 3


def test_only_one_revision_may_be_in_preparation(
    collections_client: TestClient, project_id: str, active_plan: tuple[str, str]
) -> None:
    plan_id, _version = active_plan
    first = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/versions", json={"change_reason": "One"}
    )
    assert first.status_code == 201
    second = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/versions", json={"change_reason": "Two"}
    )
    assert second.status_code == 409
    assert "already has a version in preparation" in second.json()["detail"]


def test_a_revision_needs_a_reason(
    collections_client: TestClient, project_id: str, active_plan: tuple[str, str]
) -> None:
    plan_id, _version = active_plan
    refused = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/versions", json={"change_reason": ""}
    )
    assert refused.status_code == 422


def test_approval_refuses_a_schedule_the_contract_has_moved_away_from(
    collections_client: TestClient,
    cfo_client: TestClient,
    db: Session,
    project_id: str,
    reconciled_plan: tuple[str, str],
) -> None:
    """An approval of stale figures is worse than no approval."""
    plan_id, version_id = reconciled_plan
    base = _base(project_id, plan_id, version_id)
    collections_client.post(f"{base}/submit", json={})
    sale_id = plan_detail(collections_client, project_id, plan_id)["sale_id"]
    db.execute(
        text(
            "UPDATE sale_contracts SET net_contract_price_ex_tax ="
            " net_contract_price_ex_tax + 1000 WHERE id = :i"
        ),
        {"i": sale_id},
    )
    db.commit()
    refused = cfo_client.post(f"{base}/approve", json={"reason": "Looks fine"})
    assert refused.status_code == 409
    assert "contract has changed" in refused.json()["detail"]
    assert "contract value" in refused.json()["detail"]


def test_activation_refuses_a_schedule_the_contract_has_moved_away_from(
    collections_client: TestClient,
    cfo_client: TestClient,
    db: Session,
    project_id: str,
    approved_plan: tuple[str, str],
) -> None:
    plan_id, version_id = approved_plan
    sale_id = plan_detail(collections_client, project_id, plan_id)["sale_id"]
    db.execute(
        text("UPDATE sale_contracts SET tax_total = tax_total + 5 WHERE id = :i"),
        {"i": sale_id},
    )
    db.commit()
    refused = cfo_client.post(f"{_base(project_id, plan_id, version_id)}/activate", json={})
    assert refused.status_code == 409
    assert "tax" in refused.json()["detail"]


def test_a_cancelled_contract_cannot_gain_a_new_version(
    collections_client: TestClient,
    sales_ops_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    active_plan: tuple[str, str],
) -> None:
    plan_id, _version = active_plan
    sale_id = plan_detail(collections_client, project_id, plan_id)["sale_id"]
    started = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts/{sale_id}/cancellation",
        json={"initiated_by_party": "buyer", "reason": "Buyer withdrew"},
    )
    assert started.status_code == 201, started.text
    refused = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/versions", json={"change_reason": "Rework"}
    )
    assert refused.status_code == 409


def test_operational_forecast_and_owner_change_without_a_new_version(
    collections_client: TestClient, cfo_client: TestClient, project_id: str, plan_id: str
) -> None:
    """Maintenance is not contract restructuring."""
    version_id = current_version_id(collections_client, project_id, plan_id)
    write_schedule(
        collections_client,
        project_id,
        plan_id,
        version_id,
        [
            fixed_row(1, "0.500000", "2026-03-01"),
            {
                "sequence": 2,
                "label": "On handover",
                "trigger_type": "handover",
                "principal_fraction": "0.500000",
            },
        ],
    )
    base = _base(project_id, plan_id, version_id)
    collections_client.post(f"{base}/submit", json={})
    cfo_client.post(f"{base}/approve", json={"reason": "Fine"})
    cfo_client.post(f"{base}/activate", json={})

    rows = {
        row["sequence"]: row
        for row in plan_detail(collections_client, project_id, plan_id)["current"]["installments"]
    }
    contingent = rows[2]["id"]
    moved = collections_client.patch(
        f"{plans_url(project_id)}/{plan_id}/installments/{contingent}/forecast",
        json={"forecast_due_date": "2027-01-31", "reason": "Construction slipped a quarter"},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["forecast_due_date"] == "2027-01-31"
    # A forecast never makes anything due.
    assert moved.json()["actual_due_date"] is None
    assert moved.json()["trigger_status"] == "awaiting_trigger"

    # Still one version: this was not a contractual change.
    assert len(plan_detail(collections_client, project_id, plan_id)["versions"]) == 1


def test_a_dated_instalment_has_no_forecast_to_maintain(
    collections_client: TestClient, project_id: str, active_plan: tuple[str, str]
) -> None:
    plan_id, _version = active_plan
    row = plan_detail(collections_client, project_id, plan_id)["current"]["installments"][0]
    refused = collections_client.patch(
        f"{plans_url(project_id)}/{plan_id}/installments/{row['id']}/forecast",
        json={"forecast_due_date": "2027-01-31", "reason": "Trying"},
    )
    assert refused.status_code == 409
    assert "contractual date" in refused.json()["detail"]


def test_an_instalment_owner_must_be_somebody_who_chases_payments(
    collections_client: TestClient,
    project_id: str,
    active_plan: tuple[str, str],
    engineer: object,
) -> None:
    plan_id, _version = active_plan
    row = plan_detail(collections_client, project_id, plan_id)["current"]["installments"][0]
    refused = collections_client.patch(
        f"{plans_url(project_id)}/{plan_id}/installments/{row['id']}/owner",
        json={"owner_user_id": str(engineer.id)},
    )
    assert refused.status_code == 422
    assert "Collections or Sales Operations" in refused.json()["detail"]
