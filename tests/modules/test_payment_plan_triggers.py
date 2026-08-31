"""What makes an instalment fall due — and what conclusively does not.

The control this file exists to defend: a forecast is not an event. A
construction milestone expected in March does not become due in March, or in
April, or ever, until PR-MVP-09 certifies it. No route in this system can be
made to fill in that date, and the database refuses it as well.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

from tests.modules.conftest import (
    current_version_id,
    fixed_row,
    plan_detail,
    plans_url,
    record_legal,
    sales_url,
    write_schedule,
)


def _rows_by_sequence(body: dict) -> dict[int, dict]:
    return {row["sequence"]: row for row in body["current"]["installments"]}


def _activate(
    collections: TestClient, cfo: TestClient, project_id: str, plan_id: str, version_id: str
) -> None:
    base = f"{plans_url(project_id)}/{plan_id}/versions/{version_id}"
    assert collections.post(f"{base}/submit", json={}).status_code == 200
    assert cfo.post(f"{base}/approve", json={"reason": "Reviewed"}).status_code == 200
    assert cfo.post(f"{base}/activate", json={}).status_code == 200


# --------------------------------------------------------------------------- #
# Dated triggers
# --------------------------------------------------------------------------- #


def test_a_fixed_date_instalment_is_due_on_its_contractual_date(
    collections_client: TestClient, cfo_client: TestClient, project_id: str, plan_id: str
) -> None:
    version_id = current_version_id(collections_client, project_id, plan_id)
    write_schedule(
        collections_client,
        project_id,
        plan_id,
        version_id,
        [fixed_row(1, "1.000000", "2026-03-01")],
    )
    _activate(collections_client, cfo_client, project_id, plan_id, version_id)
    row = _rows_by_sequence(plan_detail(collections_client, project_id, plan_id))[1]
    assert row["contractual_due_date"] == "2026-03-01"
    assert row["actual_due_date"] == "2026-03-01"
    assert row["trigger_status"] == "scheduled"


def test_a_fixed_date_instalment_without_a_date_is_refused(
    collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    version_id = current_version_id(collections_client, project_id, plan_id)
    refused = write_schedule(
        collections_client,
        project_id,
        plan_id,
        version_id,
        [
            {
                "sequence": 1,
                "label": "Undated",
                "trigger_type": "fixed_date",
                "principal_fraction": "1.000000",
            }
        ],
    )
    assert refused.status_code == 422
    assert "no due date" in refused.json()["detail"]


def test_days_after_spa_resolves_against_the_contract_date(
    collections_client: TestClient,
    cfo_client: TestClient,
    sales_ops_client: TestClient,
    project_id: str,
    plan_id: str,
) -> None:
    sale_id = plan_detail(collections_client, project_id, plan_id)["sale_id"]
    contract_date = date.fromisoformat(
        sales_ops_client.get(f"{sales_url(project_id)}/contracts/{sale_id}").json()["sale"][
            "contract_date"
        ]
    )
    version_id = current_version_id(collections_client, project_id, plan_id)
    write_schedule(
        collections_client,
        project_id,
        plan_id,
        version_id,
        [
            {
                "sequence": 1,
                "label": "On signing",
                "trigger_type": "days_after_spa",
                "offset_days": 0,
                "principal_fraction": "0.400000",
            },
            {
                "sequence": 2,
                "label": "Thirty days later",
                "trigger_type": "days_after_spa",
                "offset_days": 30,
                "principal_fraction": "0.600000",
            },
        ],
    )
    rows = _rows_by_sequence(plan_detail(collections_client, project_id, plan_id))
    assert rows[1]["contractual_due_date"] == contract_date.isoformat()
    assert rows[2]["contractual_due_date"] == (contract_date + timedelta(days=30)).isoformat()

    _activate(collections_client, cfo_client, project_id, plan_id, version_id)
    rows = _rows_by_sequence(plan_detail(collections_client, project_id, plan_id))
    assert rows[2]["actual_due_date"] == (contract_date + timedelta(days=30)).isoformat()


def test_days_after_spa_without_an_offset_is_refused(
    collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    version_id = current_version_id(collections_client, project_id, plan_id)
    refused = write_schedule(
        collections_client,
        project_id,
        plan_id,
        version_id,
        [
            {
                "sequence": 1,
                "label": "Relative to nothing",
                "trigger_type": "days_after_spa",
                "principal_fraction": "1.000000",
            }
        ],
    )
    assert refused.status_code == 422
    assert "number of days" in refused.json()["detail"]


# --------------------------------------------------------------------------- #
# Recurring series
# --------------------------------------------------------------------------- #


def test_a_monthly_series_proposes_dates_and_clamps_month_ends(
    collections_client: TestClient, project_id: str
) -> None:
    preview = collections_client.post(
        f"{plans_url(project_id)}/series-preview",
        json={
            "frequency": "recurring_monthly",
            "first_due_date": "2026-01-31",
            "count": 4,
            "label_prefix": "Monthly",
        },
    )
    assert preview.status_code == 200, preview.text
    dates = [row["due_date"] for row in preview.json()["rows"]]
    # February is clamped, and March is NOT dragged back with it.
    assert dates == ["2026-01-31", "2026-02-28", "2026-03-31", "2026-04-30"]
    assert preview.json()["rows"][0]["label"] == "Monthly 1"


def test_a_monthly_series_clamps_into_a_leap_february(
    collections_client: TestClient, project_id: str
) -> None:
    preview = collections_client.post(
        f"{plans_url(project_id)}/series-preview",
        json={"frequency": "recurring_monthly", "first_due_date": "2028-01-31", "count": 2},
    )
    assert [row["due_date"] for row in preview.json()["rows"]] == ["2028-01-31", "2028-02-29"]


def test_a_monthly_series_crosses_a_year_boundary(
    collections_client: TestClient, project_id: str
) -> None:
    preview = collections_client.post(
        f"{plans_url(project_id)}/series-preview",
        json={"frequency": "recurring_monthly", "first_due_date": "2026-11-30", "count": 3},
    )
    assert [row["due_date"] for row in preview.json()["rows"]] == [
        "2026-11-30",
        "2026-12-30",
        "2027-01-30",
    ]


def test_a_quarterly_series_steps_three_months(
    collections_client: TestClient, project_id: str
) -> None:
    preview = collections_client.post(
        f"{plans_url(project_id)}/series-preview",
        json={"frequency": "recurring_quarterly", "first_due_date": "2026-01-31", "count": 4},
    )
    assert [row["due_date"] for row in preview.json()["rows"]] == [
        "2026-01-31",
        "2026-04-30",
        "2026-07-31",
        "2026-10-31",
    ]


def test_a_twenty_four_row_series_is_ordinary(
    collections_client: TestClient, project_id: str
) -> None:
    preview = collections_client.post(
        f"{plans_url(project_id)}/series-preview",
        json={"frequency": "recurring_monthly", "first_due_date": "2026-01-15", "count": 24},
    )
    assert len(preview.json()["rows"]) == 24
    assert preview.json()["rows"][-1]["due_date"] == "2027-12-15"


def test_the_series_helper_writes_nothing(
    collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    before = plan_detail(collections_client, project_id, plan_id)
    collections_client.post(
        f"{plans_url(project_id)}/series-preview",
        json={"frequency": "recurring_monthly", "first_due_date": "2026-01-15", "count": 12},
    )
    after = plan_detail(collections_client, project_id, plan_id)
    assert (
        after["current"]["reconciliation"]["installment_count"]
        == (before["current"]["reconciliation"]["installment_count"])
    )


# --------------------------------------------------------------------------- #
# Construction milestones — the boundary
# --------------------------------------------------------------------------- #


def test_a_construction_milestone_never_becomes_due_from_a_forecast(
    collections_client: TestClient, cfo_client: TestClient, project_id: str, plan_id: str
) -> None:
    """The critical control. A forecast date is not a certificate.

    PR-MVP-09 owns construction certification. Until it exists there is no
    record that could say a milestone was reached, so the instalment waits —
    even with a forecast date long in the past.
    """
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
                "label": "On slab completion",
                "trigger_type": "construction_milestone",
                "trigger_reference": "SLAB-L3",
                # Deliberately in the past.
                "forecast_due_date": "2020-01-01",
                "principal_fraction": "0.500000",
            },
        ],
    )
    _activate(collections_client, cfo_client, project_id, plan_id, version_id)

    rows = _rows_by_sequence(plan_detail(collections_client, project_id, plan_id))
    milestone = rows[2]
    assert milestone["trigger_status"] == "awaiting_trigger"
    assert milestone["actual_due_date"] is None
    assert milestone["forecast_due_date"] == "2020-01-01"
    assert milestone["contractual_due_date"] is None

    # A refresh cannot certify it either.
    refreshed = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/refresh-triggers", json={}
    )
    assert refreshed.status_code == 200
    assert [row["sequence"] for row in refreshed.json()["triggered"]] == []
    assert 2 in [row["sequence"] for row in refreshed.json()["still_awaiting"]]

    rows = _rows_by_sequence(plan_detail(collections_client, project_id, plan_id))
    assert rows[2]["actual_due_date"] is None


def test_a_construction_milestone_cannot_be_manually_attested(
    collections_client: TestClient, cfo_client: TestClient, project_id: str, plan_id: str
) -> None:
    """Manual attestation is for a contractual event, never for certification."""
    version_id = current_version_id(collections_client, project_id, plan_id)
    write_schedule(
        collections_client,
        project_id,
        plan_id,
        version_id,
        [
            {
                "sequence": 1,
                "label": "On slab completion",
                "trigger_type": "construction_milestone",
                "trigger_reference": "SLAB-L3",
                "principal_fraction": "1.000000",
            }
        ],
    )
    _activate(collections_client, cfo_client, project_id, plan_id, version_id)
    installment_id = _rows_by_sequence(plan_detail(collections_client, project_id, plan_id))[1][
        "id"
    ]
    refused = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/installments/{installment_id}/manual-trigger",
        json={
            "event_date": "2026-05-01",
            "evidence_reference": "PHOTO-1",
            "reason": "Looks finished",
        },
    )
    assert refused.status_code == 409
    assert "manually approved event" in refused.json()["detail"]


def test_a_construction_milestone_needs_a_reference(
    collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    version_id = current_version_id(collections_client, project_id, plan_id)
    refused = write_schedule(
        collections_client,
        project_id,
        plan_id,
        version_id,
        [
            {
                "sequence": 1,
                "label": "On some milestone",
                "trigger_type": "construction_milestone",
                "principal_fraction": "1.000000",
            }
        ],
    )
    assert refused.status_code == 422
    assert "which one" in refused.json()["detail"]


# --------------------------------------------------------------------------- #
# Handover and title transfer
# --------------------------------------------------------------------------- #


def _handover_plan(
    collections: TestClient, cfo: TestClient, project_id: str, plan_id: str, trigger: str
) -> str:
    version_id = current_version_id(collections, project_id, plan_id)
    write_schedule(
        collections,
        project_id,
        plan_id,
        version_id,
        [
            fixed_row(1, "0.700000", "2026-03-01"),
            {
                "sequence": 2,
                "label": "On completion",
                "trigger_type": trigger,
                "forecast_due_date": "2026-10-01",
                "principal_fraction": "0.300000",
            },
        ],
    )
    _activate(collections, cfo, project_id, plan_id, version_id)
    return version_id


def test_a_handover_instalment_waits_for_a_real_handover(
    collections_client: TestClient,
    cfo_client: TestClient,
    sales_ops_client: TestClient,
    project_id: str,
    plan_id: str,
) -> None:
    _handover_plan(collections_client, cfo_client, project_id, plan_id, "handover")
    sale_id = plan_detail(collections_client, project_id, plan_id)["sale_id"]

    # Opening a handover and scheduling it is not completing it.
    opened = sales_ops_client.post(f"{sales_url(project_id)}/contracts/{sale_id}/handover", json={})
    assert opened.status_code == 201, opened.text
    handover_id = opened.json()["handover"]["id"]
    sales_ops_client.patch(
        f"{sales_url(project_id)}/handovers/{handover_id}",
        json={"scheduled_handover_date": "2026-09-15"},
    )
    refreshed = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/refresh-triggers", json={}
    )
    assert [row["sequence"] for row in refreshed.json()["triggered"]] == []
    rows = _rows_by_sequence(plan_detail(collections_client, project_id, plan_id))
    assert rows[2]["trigger_status"] == "awaiting_trigger"
    assert rows[2]["actual_due_date"] is None


def test_a_title_transfer_instalment_waits_for_the_transfer_itself(
    collections_client: TestClient,
    cfo_client: TestClient,
    legal_client: TestClient,
    admin_client: TestClient,
    project_id: str,
    plan_id: str,
) -> None:
    # PR-MVP-05's own gate on title transfer is a separate concern from this
    # trigger, so it is relaxed here to leave one rule under test.
    policy = admin_client.put(
        f"{sales_url(project_id)}/policy",
        json={
            "handover_requires_collection_clearance": True,
            "handover_requires_legal_clearance": True,
            "handover_requires_delivery_clearance": True,
            "handover_requires_title_transfer": True,
            "title_transfer_requires_collection_clearance": False,
            "reservation_requires_deposit_confirmation": True,
        },
    )
    assert policy.status_code == 200, policy.text
    _handover_plan(collections_client, cfo_client, project_id, plan_id, "title_transfer")
    sale_id = plan_detail(collections_client, project_id, plan_id)["sale_id"]

    for event_type, event_date in (
        ("stamped", "2026-03-01"),
        ("land_registry_lodged", "2026-03-05"),
        ("land_registry_accepted", "2026-03-08"),
        ("registered", "2026-03-10"),
        ("title_transfer_pending", "2026-04-01"),
    ):
        record_legal(legal_client, project_id, sale_id, event_type, event_date)

    # Registered and transfer-pending are not the transfer.
    refreshed = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/refresh-triggers", json={}
    )
    assert [row["sequence"] for row in refreshed.json()["triggered"]] == []

    record_legal(legal_client, project_id, sale_id, "title_transferred", "2026-05-20")
    refreshed = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/refresh-triggers", json={}
    )
    assert [row["sequence"] for row in refreshed.json()["triggered"]] == [2]
    rows = _rows_by_sequence(plan_detail(collections_client, project_id, plan_id))
    assert rows[2]["trigger_status"] == "triggered"
    assert rows[2]["actual_due_date"] == "2026-05-20"


# --------------------------------------------------------------------------- #
# Manual attestation
# --------------------------------------------------------------------------- #


def _manual_plan(collections: TestClient, cfo: TestClient, project_id: str, plan_id: str) -> str:
    version_id = current_version_id(collections, project_id, plan_id)
    write_schedule(
        collections,
        project_id,
        plan_id,
        version_id,
        [
            fixed_row(1, "0.600000", "2026-03-01"),
            {
                "sequence": 2,
                "label": "On mortgage drawdown",
                "trigger_type": "manual_approved_event",
                "trigger_reference": "Buyer's lender releases funds",
                "principal_fraction": "0.400000",
            },
        ],
    )
    _activate(collections, cfo, project_id, plan_id, version_id)
    return _rows_by_sequence(plan_detail(collections, project_id, plan_id))[2]["id"]


def test_a_manual_attestation_needs_a_second_person_to_approve_it(
    collections_client: TestClient, cfo_client: TestClient, project_id: str, plan_id: str
) -> None:
    installment_id = _manual_plan(collections_client, cfo_client, project_id, plan_id)
    submitted = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/installments/{installment_id}/manual-trigger",
        json={
            "event_date": "2026-07-15",
            "evidence_reference": "LENDER-LETTER-88",
            "reason": "Funds released",
        },
    )
    assert submitted.status_code == 201, submitted.text
    event_id = submitted.json()["id"]

    # Not yet due: an attestation nobody has sanctioned makes nothing due.
    rows = _rows_by_sequence(plan_detail(collections_client, project_id, plan_id))
    assert rows[2]["trigger_status"] == "awaiting_trigger"
    assert rows[2]["actual_due_date"] is None

    approved = cfo_client.post(
        f"{plans_url(project_id)}/{plan_id}/trigger-events/{event_id}/approve", json={}
    )
    assert approved.status_code == 200, approved.text
    rows = _rows_by_sequence(plan_detail(collections_client, project_id, plan_id))
    assert rows[2]["trigger_status"] == "triggered"
    assert rows[2]["actual_due_date"] == "2026-07-15"


def test_collections_cannot_approve_its_own_attestation(
    collections_client: TestClient, cfo_client: TestClient, project_id: str, plan_id: str
) -> None:
    installment_id = _manual_plan(collections_client, cfo_client, project_id, plan_id)
    event_id = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/installments/{installment_id}/manual-trigger",
        json={"event_date": "2026-07-15", "evidence_reference": "X", "reason": "Done"},
    ).json()["id"]
    refused = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/trigger-events/{event_id}/approve", json={}
    )
    assert refused.status_code == 403


def test_an_administrator_cannot_approve_an_attestation(
    collections_client: TestClient,
    cfo_client: TestClient,
    admin_client: TestClient,
    project_id: str,
    plan_id: str,
) -> None:
    """Administering a platform is not authority to declare an event occurred."""
    installment_id = _manual_plan(collections_client, cfo_client, project_id, plan_id)
    event_id = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/installments/{installment_id}/manual-trigger",
        json={"event_date": "2026-07-15", "evidence_reference": "X", "reason": "Done"},
    ).json()["id"]
    refused = admin_client.post(
        f"{plans_url(project_id)}/{plan_id}/trigger-events/{event_id}/approve", json={}
    )
    assert refused.status_code == 403


def test_a_withdrawn_attestation_keeps_its_record_and_clears_the_due_date(
    collections_client: TestClient, cfo_client: TestClient, project_id: str, plan_id: str
) -> None:
    installment_id = _manual_plan(collections_client, cfo_client, project_id, plan_id)
    event_id = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/installments/{installment_id}/manual-trigger",
        json={"event_date": "2026-07-15", "evidence_reference": "X", "reason": "Done"},
    ).json()["id"]
    cfo_client.post(f"{plans_url(project_id)}/{plan_id}/trigger-events/{event_id}/approve", json={})

    reversed_event = cfo_client.post(
        f"{plans_url(project_id)}/{plan_id}/trigger-events/{event_id}/reverse",
        json={"reason": "Attested against the wrong instalment"},
    )
    assert reversed_event.status_code == 200, reversed_event.text
    assert reversed_event.json()["status"] == "reversed"

    rows = _rows_by_sequence(plan_detail(collections_client, project_id, plan_id))
    assert rows[2]["trigger_status"] == "awaiting_trigger"
    assert rows[2]["actual_due_date"] is None

    # The original attestation is still on the record. Nothing is deleted.
    history = collections_client.get(
        f"{plans_url(project_id)}/{plan_id}/installments/{installment_id}/trigger-events"
    )
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["evidence_reference"] == "X"
    assert history.json()[0]["reversal_reason"]


def test_a_manual_attestation_needs_evidence_and_a_reason(
    collections_client: TestClient, cfo_client: TestClient, project_id: str, plan_id: str
) -> None:
    installment_id = _manual_plan(collections_client, cfo_client, project_id, plan_id)
    refused = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/installments/{installment_id}/manual-trigger",
        json={"event_date": "2026-07-15", "evidence_reference": "", "reason": ""},
    )
    assert refused.status_code == 422


def test_only_one_attestation_may_stand_at_a_time(
    collections_client: TestClient, cfo_client: TestClient, project_id: str, plan_id: str
) -> None:
    installment_id = _manual_plan(collections_client, cfo_client, project_id, plan_id)
    url = f"{plans_url(project_id)}/{plan_id}/installments/{installment_id}/manual-trigger"
    first = collections_client.post(
        url, json={"event_date": "2026-07-15", "evidence_reference": "A", "reason": "Done"}
    )
    assert first.status_code == 201
    second = collections_client.post(
        url, json={"event_date": "2026-07-16", "evidence_reference": "B", "reason": "Again"}
    )
    assert second.status_code == 409
    assert "already outstanding" in second.json()["detail"]


# --------------------------------------------------------------------------- #
# When an attestation may be made, and how long it stays good for
# --------------------------------------------------------------------------- #


def test_an_attestation_cannot_be_dated_in_the_future(
    collections_client: TestClient, cfo_client: TestClient, project_id: str, plan_id: str
) -> None:
    """An attestation says an event happened. Tomorrow it has not.

    Accepting a future date would make an instalment contractually due for
    something nobody has witnessed, and would leave the system needing a
    scheduler to later decide the day had come. Instalments already carry a
    forecast date for an event still expected; that is the field for this.
    """
    installment_id = _manual_plan(collections_client, cfo_client, project_id, plan_id)
    tomorrow = date.today() + timedelta(days=1)
    refused = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/installments/{installment_id}/manual-trigger",
        json={
            "event_date": tomorrow.isoformat(),
            "evidence_reference": "LENDER-FUTURE",
            "reason": "Expected drawdown",
        },
    )
    assert refused.status_code == 422
    assert tomorrow.isoformat() in refused.json()["detail"]

    # Nothing was written: no attestation, and the instalment still waits.
    history = collections_client.get(
        f"{plans_url(project_id)}/{plan_id}/installments/{installment_id}/trigger-events"
    )
    assert history.json() == []
    row = _rows_by_sequence(plan_detail(collections_client, project_id, plan_id))[2]
    assert row["trigger_status"] == "awaiting_trigger"
    assert row["actual_due_date"] is None


def test_an_attestation_may_be_dated_today_or_backdated(
    collections_client: TestClient, cfo_client: TestClient, project_id: str, plan_id: str
) -> None:
    """Events are often recorded a few days after they happen, and the date
    that matters is the day it happened."""
    installment_id = _manual_plan(collections_client, cfo_client, project_id, plan_id)
    yesterday = date.today() - timedelta(days=1)
    submitted = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/installments/{installment_id}/manual-trigger",
        json={
            "event_date": yesterday.isoformat(),
            "evidence_reference": "LENDER-88",
            "reason": "Drawdown confirmation received",
        },
    )
    assert submitted.status_code == 201, submitted.text
    assert submitted.json()["event_date"] == yesterday.isoformat()

    approved = cfo_client.post(
        f"{plans_url(project_id)}/{plan_id}/trigger-events/{submitted.json()['id']}/approve",
        json={},
    )
    assert approved.status_code == 200, approved.text
    row = _rows_by_sequence(plan_detail(collections_client, project_id, plan_id))[2]
    assert row["actual_due_date"] == yesterday.isoformat()


def test_an_attestation_cannot_be_approved_after_its_version_is_superseded(
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    plan_id: str,
) -> None:
    """Submission and approval are separated in time, and a revision can be
    activated in between.

    Approving then would make an instalment due on a schedule the sale is no
    longer running on: a date written into terms nobody is being held to, on a
    version whose whole point is that it has been replaced. Submission already
    required the active version; approval has to require it again, because by
    then it may be a different one.
    """
    installment_id = _manual_plan(collections_client, cfo_client, project_id, plan_id)
    event_id = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/installments/{installment_id}/manual-trigger",
        json={
            "event_date": "2026-02-20",
            "evidence_reference": "LENDER-88",
            "reason": "Drawdown confirmed",
        },
    ).json()["id"]

    # A revision overtakes it before the CFO gets to the attestation.
    revised = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/versions",
        json={"change_reason": "Renegotiated timing"},
    )
    assert revised.status_code == 201, revised.text
    second = revised.json()["version"]["id"]
    _activate(collections_client, cfo_client, project_id, plan_id, second)

    refused = cfo_client.post(
        f"{plans_url(project_id)}/{plan_id}/trigger-events/{event_id}/approve", json={}
    )
    assert refused.status_code == 409
    assert "superseded" in refused.json()["detail"]

    # The attestation stands unchanged, and made nothing due.
    history = collections_client.get(
        f"{plans_url(project_id)}/{plan_id}/installments/{installment_id}/trigger-events"
    ).json()
    assert [event["status"] for event in history] == ["submitted"]
    assert history[0]["approved_by_user_id"] is None
    assert history[0]["approved_at"] is None

    superseded = collections_client.get(
        f"{plans_url(project_id)}/{plan_id}/versions/"
        f"{collections_client.get(f'{plans_url(project_id)}/{plan_id}').json()['versions'][1]['id']}"
    ).json()
    old_row = {row["sequence"]: row for row in superseded["installments"]}[2]
    assert old_row["trigger_status"] == "awaiting_trigger"
    assert old_row["actual_due_date"] is None
