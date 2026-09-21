"""Opening a payment plan, and the sale states that permit it.

The boundary this file defends: a schedule is written against frozen contract
terms. A draft contract's price can still move, so it cannot be scheduled; a
cancelled one has nothing left to schedule.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.payment_plans.models import (
    PaymentPlan,
    PaymentPlanInstallment,
    PaymentPlanVersion,
)
from app.modules.sales.models import SaleContract
from tests.modules.conftest import plan_detail, plans_url, sales_url


def test_a_plan_opens_on_a_live_contract_with_its_first_draft_version(
    collections_client: TestClient, project_id: str, active_sale: str
) -> None:
    created = collections_client.post(
        plans_url(project_id),
        json={"sale_contract_id": active_sale, "name": "Standard terms"},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["plan"]["plan_number"] == "PLN-000001"
    assert body["current"]["version"]["version_number"] == 1
    assert body["current"]["version"]["status"] == "draft"
    # No schedule yet, so nothing reconciles and the screen must say why.
    assert body["current"]["reconciliation"]["is_reconciled"] is False
    assert body["current"]["reconciliation"]["installment_count"] == 0


def test_the_first_version_freezes_the_contracts_own_figures(
    collections_client: TestClient, project_id: str, active_sale: str, sales_ops_client: TestClient
) -> None:
    sale = sales_ops_client.get(f"{sales_url(project_id)}/contracts/{active_sale}").json()["sale"]
    created = collections_client.post(
        plans_url(project_id),
        json={"sale_contract_id": active_sale, "name": "Standard terms"},
    )
    version = created.json()["current"]["version"]
    # Copied from the contract, not recomputed from pricing or from tax rules.
    assert version["contract_value_covered"] == sale["net_contract_price_ex_tax"]
    assert version["tax_total_snapshot"] == sale["tax_total"]
    assert version["buyer_fee_total_snapshot"] == sale["buyer_fee_total"]
    assert version["total_buyer_payable_snapshot"] == sale["total_contract_price"]
    assert version["currency_id"] == sale["currency_id"]


def test_a_plan_may_be_prepared_while_the_contract_awaits_signature(
    collections_client: TestClient, project_id: str, submitted_sale: str
) -> None:
    """Preparation before commercial activation is the point of the two states."""
    created = collections_client.post(
        plans_url(project_id),
        json={"sale_contract_id": submitted_sale, "name": "Prepared early"},
    )
    assert created.status_code == 201, created.text


def test_a_draft_contract_cannot_be_scheduled(
    collections_client: TestClient, project_id: str, sale_id: str
) -> None:
    """Its price, tax and fees can still change under whatever was scheduled."""
    refused = collections_client.post(
        plans_url(project_id),
        json={"sale_contract_id": sale_id, "name": "Too early"},
    )
    assert refused.status_code == 409
    assert "awaiting signature or active" in refused.json()["detail"]


def test_a_sale_gets_at_most_one_plan(
    collections_client: TestClient, project_id: str, active_sale: str, plan_id: str
) -> None:
    second = collections_client.post(
        plans_url(project_id),
        json={"sale_contract_id": active_sale, "name": "Competing"},
    )
    assert second.status_code == 409
    assert "PLN-000001" in second.json()["detail"]
    assert "new version" in second.json()["detail"]


def test_plan_numbers_run_in_project_sequence(
    collections_client: TestClient,
    sales_ops_client: TestClient,
    project_id: str,
    active_sale: str,
    submitted_sale: str,
) -> None:
    first = collections_client.post(
        plans_url(project_id), json={"sale_contract_id": active_sale, "name": "One"}
    )
    assert first.json()["plan"]["plan_number"] == "PLN-000001"


def test_a_plan_detail_carries_the_sale_the_unit_and_the_buyers_name(
    collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    body = plan_detail(collections_client, project_id, plan_id)
    assert body["sale_number"]
    assert body["unit_reference"]
    assert body["client_display_name"]
    # A payment schedule never needs the buyer's identity document, so the
    # response does not carry one.
    assert "identity_document_number" not in body
    assert "email" not in body


def test_a_plan_carries_no_collected_or_outstanding_figure(
    collections_client: TestClient, project_id: str, active_plan: tuple[str, str]
) -> None:
    """PR-MVP-07 owns cash truth. Nothing here may imply it exists yet."""
    plan, _version = active_plan
    body = plan_detail(collections_client, project_id, plan)
    serialised = str(body)
    for forbidden in (
        "paid_amount",
        "balance_due",
        "outstanding",
        "receipt_id",
        "days_overdue",
        "payment_status",
    ):
        assert forbidden not in serialised


def test_an_unused_draft_plan_is_deleted_without_deleting_its_sale_and_can_be_recreated(
    db: Session,
    collections_client: TestClient,
    project_id: str,
    active_sale: str,
    reconciled_plan: tuple[str, str],
) -> None:
    plan_id, version_id = reconciled_plan
    removed = collections_client.delete(
        f"{plans_url(project_id)}/{plan_id}",
        params={"reason": "Duplicate plan entered by mistake"},
    )
    assert removed.status_code == 204, removed.text

    assert db.get(PaymentPlan, uuid.UUID(plan_id)) is None
    assert db.get(PaymentPlanVersion, uuid.UUID(version_id)) is None
    assert (
        db.scalar(
            select(func.count())
            .select_from(PaymentPlanInstallment)
            .where(PaymentPlanInstallment.payment_plan_version_id == uuid.UUID(version_id))
        )
        == 0
    )
    assert db.get(SaleContract, uuid.UUID(active_sale)) is not None
    event = db.scalars(
        select(AuditEvent).where(
            AuditEvent.action == "payment_plan.deleted",
            AuditEvent.entity_id == uuid.UUID(plan_id),
        )
    ).one()
    assert event.reason == "Duplicate plan entered by mistake"
    assert event.before_data["sale_contract_id"] == active_sale
    assert event.before_data["installment_count"] == 3

    recreated = collections_client.post(
        plans_url(project_id),
        json={"sale_contract_id": active_sale, "name": "Correct terms"},
    )
    assert recreated.status_code == 201, recreated.text
    assert recreated.json()["current"]["version"]["status"] == "draft"


def test_a_replacement_draft_is_discarded_without_touching_the_active_schedule(
    db: Session,
    collections_client: TestClient,
    project_id: str,
    active_plan: tuple[str, str],
) -> None:
    plan_id, active_version_id = active_plan
    created = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/versions",
        json={"change_reason": "Mistaken revision"},
    )
    assert created.status_code == 201, created.text
    draft_id = created.json()["version"]["id"]

    discarded = collections_client.delete(
        f"{plans_url(project_id)}/{plan_id}/versions/{draft_id}",
        params={"reason": "Draft opened accidentally"},
    )
    assert discarded.status_code == 204, discarded.text
    assert db.get(PaymentPlanVersion, uuid.UUID(draft_id)) is None
    active = db.get(PaymentPlanVersion, uuid.UUID(active_version_id))
    assert active is not None and active.status == "active"
    assert db.get(PaymentPlan, uuid.UUID(plan_id)) is not None
    event = db.scalars(
        select(AuditEvent).where(
            AuditEvent.action == "payment_plan_version.discarded",
            AuditEvent.entity_id == uuid.UUID(draft_id),
        )
    ).one()
    assert event.reason == "Draft opened accidentally"

    next_revision = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/versions",
        json={"change_reason": "Legitimate revision"},
    )
    assert next_revision.status_code == 201, next_revision.text
    assert next_revision.json()["version"]["version_number"] == 3


def test_an_active_plan_cannot_be_deleted(
    collections_client: TestClient, project_id: str, active_plan: tuple[str, str]
) -> None:
    plan_id, _version_id = active_plan
    refused = collections_client.delete(
        f"{plans_url(project_id)}/{plan_id}", params={"reason": "Remove it"}
    )
    assert refused.status_code == 409
    assert refused.json()["detail"] == "The active contractual payment schedule cannot be deleted."


def test_collections_started_blocks_deleting_even_a_draft(
    db: Session, collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    plan = db.get(PaymentPlan, uuid.UUID(plan_id))
    assert plan is not None
    plan.collections_started_at = datetime.now(UTC)
    db.commit()

    refused = collections_client.delete(
        f"{plans_url(project_id)}/{plan_id}", params={"reason": "Remove it"}
    )
    assert refused.status_code == 409
    assert "collections have started" in refused.json()["detail"]
    db.expire_all()
    assert db.get(PaymentPlan, uuid.UUID(plan_id)) is not None


def test_submitted_and_approved_versions_cannot_be_deleted(
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    reconciled_plan: tuple[str, str],
) -> None:
    plan_id, version_id = reconciled_plan
    base = f"{plans_url(project_id)}/{plan_id}/versions/{version_id}"
    assert collections_client.post(f"{base}/submit", json={}).status_code == 200
    submitted = collections_client.delete(base, params={"reason": "Remove it"})
    assert submitted.status_code == 409
    assert "already been submitted" in submitted.json()["detail"]
    assert cfo_client.post(f"{base}/approve", json={"reason": "Reviewed"}).status_code == 200
    approved = collections_client.delete(base, params={"reason": "Remove it"})
    assert approved.status_code == 409
    assert "already been approved" in approved.json()["detail"]


def test_rejected_version_is_retained(
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    reconciled_plan: tuple[str, str],
) -> None:
    plan_id, version_id = reconciled_plan
    base = f"{plans_url(project_id)}/{plan_id}/versions/{version_id}"
    assert collections_client.post(f"{base}/submit", json={}).status_code == 200
    assert cfo_client.post(f"{base}/reject", json={"reason": "Terms refused"}).status_code == 200
    refused = collections_client.delete(base, params={"reason": "Remove it"})
    assert refused.status_code == 409
    assert "contractual history" in refused.json()["detail"]


def test_superseded_version_is_retained(
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    active_plan: tuple[str, str],
) -> None:
    plan_id, first_version_id = active_plan
    created = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/versions",
        json={"change_reason": "Replacement"},
    )
    second_version_id = created.json()["version"]["id"]
    second = f"{plans_url(project_id)}/{plan_id}/versions/{second_version_id}"
    assert collections_client.post(f"{second}/submit", json={}).status_code == 200
    assert cfo_client.post(f"{second}/approve", json={"reason": "Agreed"}).status_code == 200
    assert cfo_client.post(f"{second}/activate", json={}).status_code == 200
    first = f"{plans_url(project_id)}/{plan_id}/versions/{first_version_id}"
    refused = collections_client.delete(first, params={"reason": "Remove it"})
    assert refused.status_code == 409
    assert "contractual history" in refused.json()["detail"]
