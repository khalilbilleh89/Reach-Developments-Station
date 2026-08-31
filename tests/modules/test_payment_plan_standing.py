"""Two truths at once: the version being prepared, and the one governing.

The backend deliberately shows a reader the version in preparation by default,
because that is the one somebody is working on. What it must never do is let
that convenience be mistaken for the answer to a different question — which
schedule the buyer is actually being held to today.

A revision takes days or weeks to agree. Throughout, the standing schedule
keeps falling due, instalments keep needing attestation, and events keep
happening that resolve its triggers. So the plan response carries both, in
full, and nothing operational is allowed to land on the revision.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

from tests.modules.conftest import (
    current_version_id,
    fixed_row,
    plan_detail,
    plans_url,
    sales_url,
    write_schedule,
)


def _revise(collections: TestClient, project_id: str, plan_id: str, reason: str) -> str:
    opened = collections.post(
        f"{plans_url(project_id)}/{plan_id}/versions", json={"change_reason": reason}
    )
    assert opened.status_code == 201, opened.text
    return opened.json()["version"]["id"]


def _submit(collections: TestClient, project_id: str, plan_id: str, version_id: str) -> None:
    response = collections.post(
        f"{plans_url(project_id)}/{plan_id}/versions/{version_id}/submit", json={}
    )
    assert response.status_code == 200, response.text


def _approve(cfo: TestClient, project_id: str, plan_id: str, version_id: str) -> None:
    response = cfo.post(
        f"{plans_url(project_id)}/{plan_id}/versions/{version_id}/approve",
        json={"reason": "Agreed"},
    )
    assert response.status_code == 200, response.text


def _rows(detail: dict, key: str) -> dict[int, dict]:
    return {row["sequence"]: row for row in detail[key]["installments"]}


def _manual_active_plan(
    collections: TestClient, cfo: TestClient, project_id: str, plan_id: str
) -> tuple[str, str]:
    """An active schedule whose second instalment waits on an attested event."""
    version_id = current_version_id(collections, project_id, plan_id)
    written = write_schedule(
        collections,
        project_id,
        plan_id,
        version_id,
        [
            fixed_row(1, "0.600000", "2026-03-01"),
            {
                "sequence": 2,
                "label": "On drawdown",
                "trigger_type": "manual_approved_event",
                "trigger_reference": "Lender releases funds",
                "principal_fraction": "0.400000",
            },
        ],
    )
    assert written.status_code == 200, written.text
    _submit(collections, project_id, plan_id, version_id)
    _approve(cfo, project_id, plan_id, version_id)
    activated = cfo.post(
        f"{plans_url(project_id)}/{plan_id}/versions/{version_id}/activate", json={}
    )
    assert activated.status_code == 200, activated.text
    detail = plan_detail(collections, project_id, plan_id)
    return version_id, _rows(detail, "current")[2]["id"]


# --------------------------------------------------------------------------- #
# The shape of the two answers
# --------------------------------------------------------------------------- #


def test_a_plan_with_no_active_version_says_so(
    collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    """Before the first activation there is a draft and nothing governing."""
    detail = plan_detail(collections_client, project_id, plan_id)
    assert detail["current"]["version"]["status"] == "draft"
    assert detail["active"] is None
    assert detail["active_version_id"] is None


def test_with_nothing_in_preparation_both_answers_are_the_same_version(
    collections_client: TestClient, project_id: str, active_plan: tuple[str, str]
) -> None:
    plan_id, version_id = active_plan
    detail = plan_detail(collections_client, project_id, plan_id)
    assert detail["current"]["version"]["id"] == version_id
    assert detail["active"]["version"]["id"] == version_id
    assert detail["active"]["version"]["status"] == "active"
    assert detail["current"]["installments"] == detail["active"]["installments"]


def test_a_draft_revision_does_not_displace_the_governing_schedule(
    collections_client: TestClient, project_id: str, active_plan: tuple[str, str]
) -> None:
    """The defect this file exists to close.

    Opening a revision changes which version is being worked on. It does not
    change which one the buyer is being held to, and the response has to say
    both — with the standing schedule's rows, not just its identifier, because
    every screen that reports what is owed needs the rows.
    """
    plan_id, standing = active_plan
    revision = _revise(collections_client, project_id, plan_id, "Renegotiating timing")

    detail = plan_detail(collections_client, project_id, plan_id)
    assert detail["current"]["version"]["id"] == revision
    assert detail["current"]["version"]["status"] == "draft"
    assert detail["active"]["version"]["id"] == standing
    assert detail["active"]["version"]["status"] == "active"
    assert detail["active_version_id"] == standing
    assert len(detail["active"]["installments"]) == 3
    assert detail["active"]["reconciliation"]["is_reconciled"] is True


def test_a_submitted_revision_does_not_displace_it_either(
    collections_client: TestClient, project_id: str, active_plan: tuple[str, str]
) -> None:
    plan_id, standing = active_plan
    revision = _revise(collections_client, project_id, plan_id, "Renegotiating timing")
    _submit(collections_client, project_id, plan_id, revision)

    detail = plan_detail(collections_client, project_id, plan_id)
    assert detail["current"]["version"]["status"] == "submitted"
    assert detail["active"]["version"]["id"] == standing


def test_an_approved_future_effective_revision_does_not_displace_it_either(
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    active_plan: tuple[str, str],
) -> None:
    """The longest window of all: agreed, signed, and not yet in force."""
    plan_id, standing = active_plan
    start = date.today() + timedelta(days=45)
    opened = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/versions",
        json={"change_reason": "Effective next quarter", "effective_date": start.isoformat()},
    )
    assert opened.status_code == 201, opened.text
    revision = opened.json()["version"]["id"]
    _submit(collections_client, project_id, plan_id, revision)
    _approve(cfo_client, project_id, plan_id, revision)

    detail = plan_detail(collections_client, project_id, plan_id)
    assert detail["current"]["version"]["status"] == "approved"
    assert detail["current"]["version"]["effective_date"] == start.isoformat()
    assert detail["active"]["version"]["id"] == standing
    assert detail["active"]["version"]["status"] == "active"


def test_once_the_revision_is_activated_both_answers_agree_again(
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    active_plan: tuple[str, str],
) -> None:
    plan_id, standing = active_plan
    revision = _revise(collections_client, project_id, plan_id, "Renegotiating timing")
    _submit(collections_client, project_id, plan_id, revision)
    _approve(cfo_client, project_id, plan_id, revision)
    activated = cfo_client.post(
        f"{plans_url(project_id)}/{plan_id}/versions/{revision}/activate", json={}
    )
    assert activated.status_code == 200, activated.text

    detail = plan_detail(collections_client, project_id, plan_id)
    assert detail["current"]["version"]["id"] == revision
    assert detail["active"]["version"]["id"] == revision
    statuses = {version["id"]: version["status"] for version in detail["versions"]}
    assert statuses[standing] == "superseded"


# --------------------------------------------------------------------------- #
# The standing schedule keeps operating
# --------------------------------------------------------------------------- #


def test_an_attestation_on_the_standing_schedule_survives_an_open_revision(
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    plan_id: str,
) -> None:
    """A revision in preparation must not freeze the live schedule.

    Collections attests, a revision is opened while the CFO is still deciding,
    and the decision must still land — on the version that governs, leaving the
    draft untouched.
    """
    standing, installment_id = _manual_active_plan(
        collections_client, cfo_client, project_id, plan_id
    )
    submitted = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/installments/{installment_id}/manual-trigger",
        json={
            "event_date": "2026-02-20",
            "evidence_reference": "LENDER-88",
            "reason": "Drawdown confirmed",
        },
    )
    assert submitted.status_code == 201, submitted.text
    event_id = submitted.json()["id"]

    revision = _revise(collections_client, project_id, plan_id, "Unrelated retiming")

    approved = cfo_client.post(
        f"{plans_url(project_id)}/{plan_id}/trigger-events/{event_id}/approve", json={}
    )
    assert approved.status_code == 200, approved.text

    detail = plan_detail(collections_client, project_id, plan_id)
    standing_rows = _rows(detail, "active")
    assert detail["active"]["version"]["id"] == standing
    assert standing_rows[2]["trigger_status"] == "triggered"
    assert standing_rows[2]["actual_due_date"] == "2026-02-20"

    # The draft is a different set of rows and none of them was touched.
    draft_rows = _rows(detail, "current")
    assert detail["current"]["version"]["id"] == revision
    assert detail["current"]["version"]["status"] == "draft"
    assert draft_rows[2]["trigger_status"] == "awaiting_trigger"
    assert draft_rows[2]["actual_due_date"] is None
    assert draft_rows[2]["trigger_events"] == []


def test_a_refresh_resolves_the_standing_schedule_and_not_the_revision(
    collections_client: TestClient,
    cfo_client: TestClient,
    sales_ops_client: TestClient,
    legal_client: TestClient,
    delivery_client: TestClient,
    project_id: str,
    plan_id: str,
) -> None:
    """The event happens in the real world while a revision is being drafted."""
    version_id = current_version_id(collections_client, project_id, plan_id)
    written = write_schedule(
        collections_client,
        project_id,
        plan_id,
        version_id,
        [
            fixed_row(1, "0.700000", "2026-03-01"),
            {
                "sequence": 2,
                "label": "On completion",
                "trigger_type": "handover",
                "forecast_due_date": "2026-10-01",
                "principal_fraction": "0.300000",
            },
        ],
    )
    assert written.status_code == 200, written.text
    _submit(collections_client, project_id, plan_id, version_id)
    _approve(cfo_client, project_id, plan_id, version_id)
    assert (
        cfo_client.post(
            f"{plans_url(project_id)}/{plan_id}/versions/{version_id}/activate", json={}
        ).status_code
        == 200
    )

    revision = _revise(collections_client, project_id, plan_id, "Retiming while we wait")

    sale_id = plan_detail(collections_client, project_id, plan_id)["sale_id"]
    opened = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts/{sale_id}/handover",
        json={"scheduled_handover_date": "2026-06-01"},
    )
    assert opened.status_code == 201, opened.text
    handover_id = opened.json()["handover"]["id"]
    for client, clearance in (
        (legal_client, "legal"),
        (collections_client, "collection"),
        (delivery_client, "delivery"),
    ):
        given = client.post(
            f"{sales_url(project_id)}/handovers/{handover_id}/clearances/{clearance}",
            json={"evidence_reference": f"{clearance.upper()}-OK"},
        )
        assert given.status_code == 200, given.text
    completed = sales_ops_client.post(
        f"{sales_url(project_id)}/handovers/{handover_id}/complete",
        json={
            "handover_date": "2026-06-01",
            "acceptance_document_reference": "ACC-2026-0001",
            "keys_reference": "KEY-101",
        },
    )
    assert completed.status_code == 200, completed.text

    refreshed = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/refresh-triggers", json={}
    )
    assert refreshed.status_code == 200, refreshed.text
    assert [row["sequence"] for row in refreshed.json()["triggered"]] == [2]

    detail = plan_detail(collections_client, project_id, plan_id)
    assert _rows(detail, "active")[2]["actual_due_date"] == "2026-06-01"
    assert detail["current"]["version"]["id"] == revision
    assert _rows(detail, "current")[2]["actual_due_date"] is None
    assert _rows(detail, "current")[2]["trigger_status"] == "awaiting_trigger"


# --------------------------------------------------------------------------- #
# What the register offers as a source
# --------------------------------------------------------------------------- #


def test_an_open_revision_does_not_withdraw_the_plan_as_a_copy_source(
    collections_client: TestClient, project_id: str, active_plan: tuple[str, str]
) -> None:
    """Governing version, copy source and revision answer three questions.

    They coincide often enough to be conflated and must not be: the copy source
    is the best *settled* schedule, which outlives an activation into
    supersession, while the governing one does not.
    """
    plan_id, standing = active_plan
    register = collections_client.get(plans_url(project_id)).json()
    row = next(row for row in register["rows"] if row["plan_id"] == plan_id)
    assert row["copy_source_version_id"] == standing
    assert row["copy_source_status"] == "active"

    _revise(collections_client, project_id, plan_id, "Renegotiating timing")

    register = collections_client.get(plans_url(project_id)).json()
    row = next(row for row in register["rows"] if row["plan_id"] == plan_id)
    assert row["version_status"] == "active", "the row still describes what governs"
    assert row["revision_status"] == "draft", "and names the revision separately"
    assert row["copy_source_version_id"] == standing, "and still names the settled source"
    assert row["copy_source_status"] == "active"
    assert row["copy_source_version_number"] == 1


def test_a_plan_with_only_a_draft_offers_no_copy_source(
    collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    """A draft is a proposal. Nobody has agreed to it, so nobody copies it."""
    register = collections_client.get(plans_url(project_id)).json()
    row = next(row for row in register["rows"] if row["plan_id"] == plan_id)
    assert row["copy_source_version_id"] is None
    assert row["copy_source_status"] is None


# --------------------------------------------------------------------------- #
# Forward-looking summary dates, on the version itself
# --------------------------------------------------------------------------- #


def test_a_version_reports_the_next_date_still_to_come(
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    plan_id: str,
) -> None:
    """One past date, one future one. "Next" is the future one.

    Every surface that summarises a schedule reads this rather than sorting the
    dates itself, so none of them can accidentally present a date from last
    March as what falls due next — which reads as arrears, and PR-MVP-06
    cannot know whether anything is in arrears.
    """
    past = date.today() - timedelta(days=120)
    soon = date.today() + timedelta(days=30)
    version_id = current_version_id(collections_client, project_id, plan_id)
    written = write_schedule(
        collections_client,
        project_id,
        plan_id,
        version_id,
        [
            fixed_row(1, "0.500000", past.isoformat()),
            fixed_row(2, "0.500000", soon.isoformat()),
        ],
    )
    assert written.status_code == 200, written.text
    _submit(collections_client, project_id, plan_id, version_id)
    _approve(cfo_client, project_id, plan_id, version_id)
    assert (
        cfo_client.post(
            f"{plans_url(project_id)}/{plan_id}/versions/{version_id}/activate", json={}
        ).status_code
        == 200
    )

    detail = plan_detail(collections_client, project_id, plan_id)
    assert detail["active"]["next_scheduled_date"] == soon.isoformat()
    assert detail["active"]["next_forecast_date"] is None

    register = collections_client.get(plans_url(project_id)).json()
    row = next(row for row in register["rows"] if row["plan_id"] == plan_id)
    assert row["next_scheduled_date"] == soon.isoformat()


def test_a_schedule_entirely_in_the_past_reports_no_future_date(
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    plan_id: str,
) -> None:
    """And says nothing at all about whether it was paid."""
    long_ago = date.today() - timedelta(days=200)
    version_id = current_version_id(collections_client, project_id, plan_id)
    assert (
        write_schedule(
            collections_client,
            project_id,
            plan_id,
            version_id,
            [fixed_row(1, "1.000000", long_ago.isoformat())],
        ).status_code
        == 200
    )
    _submit(collections_client, project_id, plan_id, version_id)
    _approve(cfo_client, project_id, plan_id, version_id)
    assert (
        cfo_client.post(
            f"{plans_url(project_id)}/{plan_id}/versions/{version_id}/activate", json={}
        ).status_code
        == 200
    )

    detail = plan_detail(collections_client, project_id, plan_id)
    assert detail["active"]["next_scheduled_date"] is None
    assert detail["active"]["next_forecast_date"] is None
    serialised = str(detail)
    for absent in ("paid", "outstanding", "overdue", "settled", "arrears"):
        assert absent not in serialised.lower()


# --------------------------------------------------------------------------- #
# The register describes what governs, not what is being drafted
# --------------------------------------------------------------------------- #


def _register_row(client: TestClient, project_id: str, plan_id: str) -> dict:
    body = client.get(plans_url(project_id)).json()
    return next(row for row in body["rows"] if row["plan_id"] == plan_id)


def test_opening_a_revision_does_not_change_what_the_register_reports(
    collections_client: TestClient, project_id: str, active_plan: tuple[str, str]
) -> None:
    """A project register is a management overview, and this is the whole of it.

    Opening a draft is the beginning of a conversation. It is not a change to
    what the sale runs on, so it must not drop a live plan out of the project's
    active count or replace a reconciled twenty-instalment schedule with an
    empty draft's figures.
    """
    plan_id, standing = active_plan
    before = _register_row(collections_client, project_id, plan_id)
    assert before["version_id"] == standing
    assert before["version_status"] == "active"
    assert before["revision_version_id"] is None

    _revise(collections_client, project_id, plan_id, "Renegotiating timing")

    after = _register_row(collections_client, project_id, plan_id)
    for field in (
        "version_id",
        "version_number",
        "version_status",
        "effective_date",
        "currency_id",
        "contract_value_covered",
        "installment_count",
        "scheduled_principal_total",
        "is_reconciled",
        "next_scheduled_date",
        "next_forecast_date",
        "awaiting_trigger_count",
        "approved_by_user_id",
    ):
        assert after[field] == before[field], f"{field} changed when a revision was opened"

    assert after["revision_version_number"] == 2
    assert after["revision_status"] == "draft"
    assert after["revision_version_id"] != standing


def test_a_submitted_revision_is_named_but_does_not_take_the_row_over(
    collections_client: TestClient, project_id: str, active_plan: tuple[str, str]
) -> None:
    plan_id, standing = active_plan
    revision = _revise(collections_client, project_id, plan_id, "Renegotiating timing")
    _submit(collections_client, project_id, plan_id, revision)

    row = _register_row(collections_client, project_id, plan_id)
    assert row["version_id"] == standing
    assert row["version_status"] == "active"
    assert row["revision_status"] == "submitted"


def test_an_approved_future_revision_is_named_but_does_not_take_the_row_over(
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    active_plan: tuple[str, str],
) -> None:
    """Approved and not yet in force is the longest window of all, and the one
    where a register that reported it as the plan would be most misleading."""
    plan_id, standing = active_plan
    start = date.today() + timedelta(days=45)
    opened = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/versions",
        json={"change_reason": "Effective next quarter", "effective_date": start.isoformat()},
    )
    assert opened.status_code == 201, opened.text
    revision = opened.json()["version"]["id"]
    _submit(collections_client, project_id, plan_id, revision)
    _approve(cfo_client, project_id, plan_id, revision)

    row = _register_row(collections_client, project_id, plan_id)
    assert row["version_id"] == standing
    assert row["version_status"] == "active"
    assert row["effective_date"] != start.isoformat()
    assert row["revision_status"] == "approved"
    assert row["revision_version_id"] == revision


def test_activating_the_revision_hands_the_row_over_to_it(
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    active_plan: tuple[str, str],
) -> None:
    plan_id, standing = active_plan
    revision = _revise(collections_client, project_id, plan_id, "Renegotiating timing")
    _submit(collections_client, project_id, plan_id, revision)
    _approve(cfo_client, project_id, plan_id, revision)
    assert (
        cfo_client.post(
            f"{plans_url(project_id)}/{plan_id}/versions/{revision}/activate", json={}
        ).status_code
        == 200
    )

    row = _register_row(collections_client, project_id, plan_id)
    assert row["version_id"] == revision
    assert row["version_id"] != standing
    assert row["version_status"] == "active"
    assert row["version_number"] == 2
    assert row["revision_version_id"] is None
    assert row["revision_status"] is None


def test_a_plan_before_its_first_activation_shows_its_draft_and_governs_nothing(
    collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    """There is nothing else to show, and the status says it governs nothing.

    No revision metadata either: a draft is not a revision *of* anything until
    something is standing for it to revise.
    """
    row = _register_row(collections_client, project_id, plan_id)
    assert row["version_status"] == "draft"
    assert row["version_number"] == 1
    assert row["revision_version_id"] is None
    assert row["revision_status"] is None
