"""When a schedule starts governing, as opposed to when it was typed.

A revision agreed in August that takes effect in October is an ordinary
commercial fact, and the two dates are not the same thing. The version model
has always carried ``effective_date`` and activation has always refused to make
a schedule govern before it arrives — but until a request could set the field,
that control could not be reached from the product at all, and every version
silently took effect the day it was drafted.

The refusal is a 409, not a silent shift to today. Moving a date the parties
agreed, because it is inconvenient, is the kind of helpfulness that makes a
system untrustworthy about contracts.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

from tests.modules.conftest import (
    fixed_row,
    plan_detail,
    plans_url,
    write_schedule,
)


def _reconcile(collections: TestClient, project_id: str, plan_id: str, version_id: str) -> None:
    written = write_schedule(
        collections,
        project_id,
        plan_id,
        version_id,
        [
            fixed_row(1, "0.400000", "2026-03-01"),
            fixed_row(2, "0.600000", "2026-09-01"),
        ],
    )
    assert written.status_code == 200, written.text
    assert written.json()["reconciliation"]["is_reconciled"] is True


def _approve(
    collections: TestClient, cfo: TestClient, project_id: str, plan_id: str, version_id: str
) -> str:
    base = f"{plans_url(project_id)}/{plan_id}/versions/{version_id}"
    assert collections.post(f"{base}/submit", json={}).status_code == 200
    approved = cfo.post(f"{base}/approve", json={"reason": "Terms agreed"})
    assert approved.status_code == 200, approved.text
    return base


def test_a_plan_takes_effect_today_when_no_date_is_given(
    collections_client: TestClient, project_id: str, active_sale: str
) -> None:
    created = collections_client.post(
        plans_url(project_id),
        json={"sale_contract_id": active_sale, "name": "Standard terms"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["current"]["version"]["effective_date"] == date.today().isoformat()


def test_a_plan_can_be_opened_with_a_future_effective_date(
    collections_client: TestClient, project_id: str, active_sale: str
) -> None:
    """The date is taken as given, not nudged to today."""
    start = date.today() + timedelta(days=30)
    created = collections_client.post(
        plans_url(project_id),
        json={
            "sale_contract_id": active_sale,
            "name": "Terms from next month",
            "effective_date": start.isoformat(),
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["current"]["version"]["effective_date"] == start.isoformat()


def test_a_future_effective_schedule_is_approved_but_cannot_be_activated_yet(
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    active_sale: str,
) -> None:
    tomorrow = date.today() + timedelta(days=1)
    created = collections_client.post(
        plans_url(project_id),
        json={
            "sale_contract_id": active_sale,
            "name": "Terms from tomorrow",
            "effective_date": tomorrow.isoformat(),
        },
    )
    assert created.status_code == 201, created.text
    plan_id = created.json()["plan"]["id"]
    version_id = created.json()["current"]["version"]["id"]
    _reconcile(collections_client, project_id, plan_id, version_id)
    base = _approve(collections_client, cfo_client, project_id, plan_id, version_id)

    refused = cfo_client.post(f"{base}/activate", json={})
    assert refused.status_code == 409
    assert tomorrow.isoformat() in refused.json()["detail"]

    # Approved and waiting, not active, and nothing has been superseded.
    detail = plan_detail(collections_client, project_id, plan_id)
    assert detail["current"]["version"]["status"] == "approved"
    assert detail["active_version_id"] is None


def test_a_schedule_effective_today_activates(
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    active_sale: str,
) -> None:
    created = collections_client.post(
        plans_url(project_id),
        json={
            "sale_contract_id": active_sale,
            "name": "Terms from today",
            "effective_date": date.today().isoformat(),
        },
    )
    plan_id = created.json()["plan"]["id"]
    version_id = created.json()["current"]["version"]["id"]
    _reconcile(collections_client, project_id, plan_id, version_id)
    base = _approve(collections_client, cfo_client, project_id, plan_id, version_id)
    activated = cfo_client.post(f"{base}/activate", json={})
    assert activated.status_code == 200, activated.text
    assert activated.json()["version"]["status"] == "active"


def test_a_backdated_schedule_activates_and_keeps_its_date(
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    active_sale: str,
) -> None:
    """A schedule agreed a fortnight ago and entered today took effect then."""
    start = date.today() - timedelta(days=14)
    created = collections_client.post(
        plans_url(project_id),
        json={
            "sale_contract_id": active_sale,
            "name": "Agreed a fortnight ago",
            "effective_date": start.isoformat(),
        },
    )
    plan_id = created.json()["plan"]["id"]
    version_id = created.json()["current"]["version"]["id"]
    _reconcile(collections_client, project_id, plan_id, version_id)
    base = _approve(collections_client, cfo_client, project_id, plan_id, version_id)
    activated = cfo_client.post(f"{base}/activate", json={})
    assert activated.status_code == 200, activated.text
    assert activated.json()["version"]["effective_date"] == start.isoformat()


def test_a_future_effective_revision_leaves_the_standing_schedule_governing(
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    active_plan: tuple[str, str],
) -> None:
    """The failed activation must not supersede anything.

    A buyer with a live contract has a schedule at every moment. An activation
    refused for being early has to leave the previous one exactly where it was,
    or the refusal costs the sale its terms.
    """
    plan_id, standing_version = active_plan
    start = date.today() + timedelta(days=45)
    revised = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/versions",
        json={
            "change_reason": "Rescheduled from next quarter",
            "effective_date": start.isoformat(),
        },
    )
    assert revised.status_code == 201, revised.text
    second = revised.json()["version"]["id"]
    assert revised.json()["version"]["effective_date"] == start.isoformat()

    base = _approve(collections_client, cfo_client, project_id, plan_id, second)
    refused = cfo_client.post(f"{base}/activate", json={})
    assert refused.status_code == 409

    detail = plan_detail(collections_client, project_id, plan_id)
    assert detail["active_version_id"] == standing_version
    statuses = {version["id"]: version["status"] for version in detail["versions"]}
    assert statuses[standing_version] == "active"
    assert statuses[second] == "approved"
