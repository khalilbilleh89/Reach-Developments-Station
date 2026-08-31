"""A nested identifier must belong to the plan in its path.

``/payment-plans/plan-A/installments/row-B`` is not two identifiers to check
separately. It is one claim — that B is one of A's instalments — and validating
each half on its own accepts every pair a caller cares to invent.

The concrete leak this file exists to close: a caller who may see plan A, given
any instalment identifier from a plan they may not see, reading that
instalment's attestation history. Its event date, its evidence reference, its
reason and the two officers who handled it are all commercially sensitive, and
none of them belong to the plan the caller was allowed to open.

Every refusal here is 404 with the ordinary "not found" wording. "That
instalment belongs to another plan" would be a more helpful message and a
worse one: it confirms the identifier is real, which is the single fact a
caller guessing at identifiers is trying to establish.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import client_for, make_user
from tests.modules.conftest import (
    current_version_id,
    fixed_row,
    grant_access,
    plan_detail,
    plans_url,
    write_schedule,
)

VERSION_MISSING = "Payment plan version not found."
INSTALLMENT_MISSING = "Instalment not found."
EVENT_MISSING = "Trigger event not found."


def _rows(client: TestClient, project_id: str, plan_id: str) -> dict[int, dict[str, object]]:
    detail = plan_detail(client, project_id, plan_id)
    return {row["sequence"]: row for row in detail["current"]["installments"]}


def _manual_schedule(
    collections: TestClient, cfo: TestClient, project_id: str, plan_id: str
) -> str:
    """Give the first plan an active schedule with a manual instalment."""
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
    base = f"{plans_url(project_id)}/{plan_id}/versions/{version_id}"
    assert collections.post(f"{base}/submit", json={}).status_code == 200
    assert cfo.post(f"{base}/approve", json={"reason": "Agreed"}).status_code == 200
    assert cfo.post(f"{base}/activate", json={}).status_code == 200
    return version_id


# --------------------------------------------------------------------------- #
# Trigger history is the one that leaks the most
# --------------------------------------------------------------------------- #


def test_trigger_history_refuses_an_instalment_from_another_plan(
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    plan_id: str,
    other_phase_plan: dict[str, str],
) -> None:
    """Plan A's path with plan B's instalment reads nothing, even for a caller
    who may legitimately see both."""
    _manual_schedule(collections_client, cfo_client, project_id, plan_id)
    foreign = other_phase_plan["manual_installment_id"]

    refused = collections_client.get(
        f"{plans_url(project_id)}/{plan_id}/installments/{foreign}/trigger-events"
    )
    assert refused.status_code == 404
    assert refused.json()["detail"] == INSTALLMENT_MISSING

    # The same history is readable under its own plan, so the refusal above is
    # about the pairing and not about the data being absent.
    allowed = collections_client.get(
        f"{plans_url(project_id)}/{other_phase_plan['plan_id']}"
        f"/installments/{foreign}/trigger-events"
    )
    assert allowed.status_code == 200
    assert [event["evidence_reference"] for event in allowed.json()] == ["PHASE2-LENDER-9"]


def test_a_hidden_phase_leaks_no_attestation_through_a_visible_plan(
    db: Session,
    admin_client: TestClient,
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    phase_id: str,
    plan_id: str,
    other_phase_plan: dict[str, str],
) -> None:
    """The whole point, stated once.

    An officer scoped to phase 1 knows an instalment identifier from phase 2 —
    from a spreadsheet, a screenshot, a previous role. Pairing it with a plan
    they are allowed to open must reveal nothing: not the date, not the
    evidence reference, not the reason, not who submitted or approved it.
    """
    _manual_schedule(collections_client, cfo_client, project_id, plan_id)

    scoped = make_user(db, email="phase1-only@example.com", roles=("collections",))
    grant_access(admin_client, project_id, scoped)
    assert (
        admin_client.patch(
            f"/api/v1/projects/{project_id}/access/{scoped.id}/phase-scope",
            json={"phase_scope": "selected"},
        ).status_code
        == 200
    )
    assert (
        admin_client.put(
            f"/api/v1/projects/{project_id}/access/{scoped.id}/phases/{phase_id}"
        ).status_code
        == 200
    )
    client = client_for(scoped.email)

    # They can see their own plan.
    assert client.get(f"{plans_url(project_id)}/{plan_id}").status_code == 200
    # And not the other one, by any route into it.
    hidden_plan = other_phase_plan["plan_id"]
    assert client.get(f"{plans_url(project_id)}/{hidden_plan}").status_code == 404

    foreign_installment = other_phase_plan["manual_installment_id"]
    attempts = (
        f"{plans_url(project_id)}/{plan_id}/installments/{foreign_installment}/trigger-events",
        f"{plans_url(project_id)}/{hidden_plan}/installments/{foreign_installment}/trigger-events",
    )
    for url in attempts:
        response = client.get(url)
        assert response.status_code == 404, url
        body = response.text
        for secret in ("PHASE2-LENDER-9", "2026-02-20", "Drawdown confirmed by the lender"):
            assert secret not in body, f"{secret} leaked through {url}"


def test_trigger_history_refuses_an_instalment_from_another_project(
    admin_client: TestClient,
    collections_client: TestClient,
    cfo_client: TestClient,
    db: Session,
    project_id: str,
    plan_id: str,
    other_phase_plan: dict[str, str],
    collections_officer: object,
) -> None:
    """A second project's path over this project's instalment finds nothing."""
    _manual_schedule(collections_client, cfo_client, project_id, plan_id)
    other = admin_client.post(
        "/api/v1/projects",
        json={
            "code": "SCOPE-PRJ",
            "name": "Other development",
            "developer_entity": "Reach",
            "country_pack_id": admin_client.get("/api/v1/settings/country-packs").json()[0]["id"],
            "base_currency_id": admin_client.get("/api/v1/settings/currencies").json()[0]["id"],
            "reporting_currency_id": admin_client.get("/api/v1/settings/currencies").json()[0][
                "id"
            ],
        },
    )
    assert other.status_code == 201, other.text
    other_id = other.json()["id"]
    grant_access(admin_client, other_id, collections_officer)  # type: ignore[arg-type]

    refused = collections_client.get(
        f"{plans_url(other_id)}/{plan_id}"
        f"/installments/{other_phase_plan['manual_installment_id']}/trigger-events"
    )
    assert refused.status_code == 404


# --------------------------------------------------------------------------- #
# Substituting a nested identifier on every mutating route
# --------------------------------------------------------------------------- #


def test_a_version_of_another_plan_cannot_be_submitted_through_this_one(
    collections_client: TestClient,
    project_id: str,
    reconciled_plan: tuple[str, str],
    other_phase_plan: dict[str, str],
) -> None:
    plan_id, _version_id = reconciled_plan
    foreign_version = other_phase_plan["version_id"]
    refused = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/versions/{foreign_version}/submit", json={}
    )
    assert refused.status_code == 404
    assert refused.json()["detail"] == VERSION_MISSING

    # Untouched: still the active schedule of the plan it actually belongs to.
    detail = plan_detail(collections_client, project_id, other_phase_plan["plan_id"])
    assert detail["current"]["version"]["id"] == foreign_version
    assert detail["current"]["version"]["status"] == "active"


def test_a_version_of_another_plan_cannot_be_read_or_decided_through_this_one(
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    reconciled_plan: tuple[str, str],
    other_phase_plan: dict[str, str],
) -> None:
    plan_id, _version_id = reconciled_plan
    base = f"{plans_url(project_id)}/{plan_id}/versions/{other_phase_plan['version_id']}"
    assert collections_client.get(base).status_code == 404
    assert (
        collections_client.put(
            f"{base}/installments",
            json={
                "allocation_mode": "percentage",
                "charge_allocation_mode": "pro_rata",
                "installments": [fixed_row(1, "1.000000", "2026-03-01")],
            },
        ).status_code
        == 404
    )
    assert cfo_client.post(f"{base}/approve", json={"reason": "No"}).status_code == 404
    assert cfo_client.post(f"{base}/reject", json={"reason": "No"}).status_code == 404
    assert cfo_client.post(f"{base}/activate", json={}).status_code == 404


def test_an_instalment_of_another_plan_cannot_be_mutated_through_this_one(
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    plan_id: str,
    other_phase_plan: dict[str, str],
) -> None:
    _manual_schedule(collections_client, cfo_client, project_id, plan_id)
    foreign = other_phase_plan["manual_installment_id"]
    base = f"{plans_url(project_id)}/{plan_id}/installments/{foreign}"

    forecast = collections_client.patch(
        f"{base}/forecast",
        json={"forecast_due_date": "2027-01-01", "reason": "Not mine to move"},
    )
    assert forecast.status_code == 404
    assert forecast.json()["detail"] == INSTALLMENT_MISSING
    assert (
        collections_client.patch(f"{base}/owner", json={"owner_user_id": None}).status_code == 404
    )
    assert (
        collections_client.post(
            f"{base}/manual-trigger",
            json={
                "event_date": "2026-02-21",
                "evidence_reference": "NOT-MINE",
                "reason": "Should not land",
            },
        ).status_code
        == 404
    )

    # The other plan's instalment is exactly as it was.
    theirs = _rows(collections_client, project_id, other_phase_plan["plan_id"])[2]
    assert theirs["forecast_due_date"] is None
    assert theirs["trigger_status"] == "awaiting_trigger"
    assert theirs["actual_due_date"] is None


def test_an_attestation_of_another_plan_cannot_be_decided_through_this_one(
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    plan_id: str,
    other_phase_plan: dict[str, str],
) -> None:
    _manual_schedule(collections_client, cfo_client, project_id, plan_id)
    foreign_event = other_phase_plan["event_id"]
    base = f"{plans_url(project_id)}/{plan_id}/trigger-events/{foreign_event}"

    approved = cfo_client.post(f"{base}/approve", json={})
    assert approved.status_code == 404
    assert approved.json()["detail"] == EVENT_MISSING
    assert cfo_client.post(f"{base}/reverse", json={"reason": "No"}).status_code == 404

    # Still submitted, still making nothing due.
    history = collections_client.get(
        f"{plans_url(project_id)}/{other_phase_plan['plan_id']}"
        f"/installments/{other_phase_plan['manual_installment_id']}/trigger-events"
    ).json()
    assert [event["status"] for event in history] == ["submitted"]
    assert (
        _rows(collections_client, project_id, other_phase_plan["plan_id"])[2]["actual_due_date"]
        is None
    )


def test_an_invented_nested_identifier_is_not_found(
    collections_client: TestClient, project_id: str, plan_id: str
) -> None:
    """An identifier that names nothing answers exactly as one that names
    somebody else's row."""
    base = f"{plans_url(project_id)}/{plan_id}"
    assert collections_client.get(f"{base}/versions/{uuid.uuid4()}").status_code == 404
    assert (
        collections_client.get(f"{base}/installments/{uuid.uuid4()}/trigger-events").status_code
        == 404
    )


# --------------------------------------------------------------------------- #
# Copying a plan is a read of the plan being copied
# --------------------------------------------------------------------------- #


def test_a_plan_cannot_be_copied_from_a_phase_the_caller_cannot_see(
    db: Session,
    admin_client: TestClient,
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    phase_id: str,
    active_sale: str,
    other_phase_plan: dict[str, str],
) -> None:
    """Copying hands over the negotiated shape of a schedule — the fractions,
    the triggers, the timing. So it has to pass the same visibility a read
    passes, or a version identifier becomes a way to lift a hidden phase's
    commercial terms without ever opening it.
    """
    scoped = make_user(db, email="copy-scoped@example.com", roles=("collections",))
    grant_access(admin_client, project_id, scoped)
    assert (
        admin_client.patch(
            f"/api/v1/projects/{project_id}/access/{scoped.id}/phase-scope",
            json={"phase_scope": "selected"},
        ).status_code
        == 200
    )
    assert (
        admin_client.put(
            f"/api/v1/projects/{project_id}/access/{scoped.id}/phases/{phase_id}"
        ).status_code
        == 200
    )
    client = client_for(scoped.email)

    refused = client.post(
        plans_url(project_id),
        json={
            "sale_contract_id": active_sale,
            "name": "Lifted from phase 2",
            "origin_type": "copied_plan",
            "source_version_id": other_phase_plan["version_id"],
        },
    )
    assert refused.status_code == 404
    assert refused.json()["detail"] == "The plan being copied was not found in this project."

    # Nothing was created on the way to the refusal.
    register = collections_client.get(plans_url(project_id)).json()
    assert [row["sale_id"] for row in register["rows"]] == [other_phase_plan["sale_id"]]


def test_a_visible_approved_plan_may_still_be_copied(
    collections_client: TestClient,
    project_id: str,
    active_sale: str,
    other_phase_plan: dict[str, str],
) -> None:
    """The same source, for a caller who may see both phases, works — and
    brings the shape across without the source's money."""
    created = collections_client.post(
        plans_url(project_id),
        json={
            "sale_contract_id": active_sale,
            "name": "Same terms as phase 2",
            "origin_type": "copied_plan",
            "source_version_id": other_phase_plan["version_id"],
        },
    )
    assert created.status_code == 201, created.text
    rows = created.json()["current"]["installments"]
    assert [row["principal_fraction"] for row in rows] == ["0.600000", "0.400000"]
    assert [row["trigger_type"] for row in rows] == ["fixed_date", "manual_approved_event"]

    # The target's own basis, not the source's figures.
    version = created.json()["current"]["version"]
    total = sum(float(row["principal_amount"]) for row in rows)
    assert f"{total:.2f}" == version["contract_value_covered"]
