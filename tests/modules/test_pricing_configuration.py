"""Governed pricing policy: who prepares it, who sanctions it, and what is live.

The rule this file exists for is that the person who prepares a price is not the
person who approves it, and that a System Administrator — who can do almost
everything else — cannot sanction money. A financial control that the most
privileged account can walk around is not a control.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.access.models import User
from app.modules.audit.models import AuditEvent
from app.modules.pricing.models import PricingConfiguration
from tests.modules.conftest import configuration_payload, pricing_url


def _base(project_id: str, configuration_id: str) -> str:
    return f"{pricing_url(project_id)}/configurations/{configuration_id}"


def test_the_first_configuration_is_version_one(
    finance_client: TestClient, project_id: str, currency_id: str, area_types: dict[str, str]
) -> None:
    response = finance_client.post(
        f"{pricing_url(project_id)}/configurations", json=configuration_payload(currency_id)
    )

    assert response.status_code == 201, response.text
    assert response.json()["version_number"] == 1
    assert response.json()["status"] == "draft"


def test_versions_are_issued_in_sequence(
    finance_client: TestClient, project_id: str, currency_id: str, area_types: dict[str, str]
) -> None:
    """The client never proposes a version number; the server issues it."""
    numbers = [
        finance_client.post(
            f"{pricing_url(project_id)}/configurations",
            json=configuration_payload(currency_id, name=f"Policy {index}"),
        ).json()["version_number"]
        for index in range(3)
    ]

    assert numbers == [1, 2, 3]


def test_a_configuration_needs_a_priced_internal_area_before_submission(
    finance_client: TestClient, project_id: str, currency_id: str, area_types: dict[str, str]
) -> None:
    """A policy that prices no internal area would price every unit at nothing."""
    configuration_id = finance_client.post(
        f"{pricing_url(project_id)}/configurations", json=configuration_payload(currency_id)
    ).json()["id"]

    response = finance_client.post(f"{_base(project_id, configuration_id)}/submit", json={})

    assert response.status_code == 422
    assert "internal" in response.json()["detail"]


def test_a_submitted_configuration_cannot_be_edited(
    finance_client: TestClient, project_id: str, draft_configuration: str
) -> None:
    """Everything a submission says has already been put in front of an approver."""
    finance_client.post(f"{_base(project_id, draft_configuration)}/submit", json={})

    response = finance_client.patch(
        _base(project_id, draft_configuration), json={"base_internal_rate": "1600.00"}
    )

    assert response.status_code == 409
    assert "draft" in response.json()["detail"]


def test_only_the_approver_may_approve(
    finance_client: TestClient, project_id: str, draft_configuration: str
) -> None:
    finance_client.post(f"{_base(project_id, draft_configuration)}/submit", json={})

    response = finance_client.post(
        f"{_base(project_id, draft_configuration)}/approve", json={"reason": "Looks fine to me"}
    )

    assert response.status_code == 403
    assert "Approver / CFO" in response.json()["detail"]


def test_a_system_administrator_cannot_approve_a_price_policy(
    admin_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    draft_configuration: str,
) -> None:
    """Given the most privileged account, then financial approval is still refused.

    Administering a system is not the authority to sanction what it charges, and
    a role that silently contained every other role would make the whole
    maker/checker separation decorative.
    """
    finance_client.post(f"{_base(project_id, draft_configuration)}/submit", json={})

    response = admin_client.post(
        f"{_base(project_id, draft_configuration)}/approve", json={"reason": "Administrator"}
    )

    assert response.status_code == 403


def test_the_submitter_cannot_approve_their_own_configuration(
    db: Session,
    admin_client: TestClient,
    project_id: str,
    draft_configuration: str,
) -> None:
    """Given one person holding both roles, then they still cannot self-approve."""
    from tests.factories import client_for, make_user
    from tests.modules.conftest import grant_access

    both = make_user(db, email="both@example.com", roles=("finance", "approver_cfo"))
    grant_access(admin_client, project_id, both)
    client = client_for(both.email)
    client.post(f"{_base(project_id, draft_configuration)}/submit", json={})

    response = client.post(
        f"{_base(project_id, draft_configuration)}/approve", json={"reason": "Mine"}
    )

    assert response.status_code == 403
    assert "may not approve it" in response.json()["detail"]


def test_a_returned_configuration_goes_back_to_draft_with_the_reason(
    finance_client: TestClient, cfo_client: TestClient, project_id: str, draft_configuration: str
) -> None:
    finance_client.post(f"{_base(project_id, draft_configuration)}/submit", json={})

    response = cfo_client.post(
        f"{_base(project_id, draft_configuration)}/return",
        json={"reason": "The balcony factor is not what the feasibility assumed"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "draft"
    assert "feasibility" in response.json()["change_reason"]
    edited = finance_client.patch(
        _base(project_id, draft_configuration), json={"base_internal_rate": "1600.00"}
    )
    assert edited.status_code == 200, edited.text


def test_approved_is_not_yet_live(
    finance_client: TestClient, cfo_client: TestClient, project_id: str, draft_configuration: str
) -> None:
    """Approved means "may be activated". Active means "this is what we price at"."""
    finance_client.post(f"{_base(project_id, draft_configuration)}/submit", json={})
    cfo_client.post(f"{_base(project_id, draft_configuration)}/approve", json={"reason": "Fine"})

    overview = finance_client.get(f"{pricing_url(project_id)}/overview").json()

    assert overview["configuration"] is None


def test_activating_a_second_configuration_supersedes_the_first(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    currency_id: str,
    area_types: dict[str, str],
    active_configuration: str,
    db: Session,
) -> None:
    """One live policy per project, and the one it replaced stays readable."""
    second = finance_client.post(
        f"{pricing_url(project_id)}/configurations",
        json=configuration_payload(
            currency_id, name="Phase 2 pricing", base_internal_rate="1650.00"
        ),
    ).json()["id"]
    finance_client.post(
        f"{pricing_url(project_id)}/configurations/{second}/area-rules",
        json={"area_type_id": area_types["INTERNAL"], "pricing_method": "internal_base"},
    )
    finance_client.post(f"{_base(project_id, second)}/submit", json={})
    cfo_client.post(f"{_base(project_id, second)}/approve", json={"reason": "Re-based"})

    response = cfo_client.post(f"{_base(project_id, second)}/activate")

    assert response.status_code == 200, response.text
    db.expire_all()
    rows = {str(row.id): row.status for row in db.scalars(select(PricingConfiguration)).all()}
    assert rows[second] == "active"
    assert rows[active_configuration] == "superseded"
    assert sum(1 for status in rows.values() if status == "active") == 1


def test_a_superseded_configuration_is_still_readable(
    finance_client: TestClient, project_id: str, active_configuration: str
) -> None:
    """History is not deleted. It is what a price version points at."""
    response = finance_client.get(_base(project_id, active_configuration))

    assert response.status_code == 200
    assert response.json()["version_number"] == 1


def test_there_is_no_delete_route_for_a_configuration(
    finance_client: TestClient, project_id: str, active_configuration: str
) -> None:
    """Financial policy is superseded, never removed."""
    response = finance_client.delete(_base(project_id, active_configuration))

    assert response.status_code == 404


def test_status_cannot_be_patched(
    finance_client: TestClient, project_id: str, draft_configuration: str
) -> None:
    """The approval a client could grant itself is not an approval."""
    response = finance_client.patch(
        _base(project_id, draft_configuration), json={"status": "active"}
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "body", [{"curreny_id": "x"}, {"base_internal_rate": "1", "statuz": "draft"}]
)
def test_a_misspelled_field_is_refused(
    finance_client: TestClient, project_id: str, draft_configuration: str, body: dict
) -> None:
    response = finance_client.patch(_base(project_id, draft_configuration), json=body)

    assert response.status_code == 422


def test_pricing_is_refused_while_the_project_is_still_in_setup(
    finance_client: TestClient,
    admin_client: TestClient,
    project_id: str,
    currency_id: str,
) -> None:
    """A price is denominated in a currency the project can still change in setup."""
    response = finance_client.post(
        f"{pricing_url(project_id)}/configurations", json=configuration_payload(currency_id)
    )

    assert response.status_code == 409
    assert "Finalize the project setup" in response.json()["detail"]


def test_the_whole_lifecycle_is_audited(
    finance_client: TestClient,
    project_id: str,
    active_configuration: str,
    db: Session,
) -> None:
    actions = {
        event.action
        for event in db.scalars(
            select(AuditEvent).where(AuditEvent.action.like("pricing_configuration.%"))
        )
    }

    assert {
        "pricing_configuration.created",
        "pricing_configuration.submitted",
        "pricing_configuration.approved",
        "pricing_configuration.activated",
    } <= actions


def test_a_project_member_without_a_pricing_role_may_not_configure(
    engineer_member: User, admin_client: TestClient, project_id: str, currency_id: str
) -> None:
    """Design and Engineering build the model of a development. They do not price it."""
    from tests.factories import client_for

    client = client_for(engineer_member.email)

    response = client.post(
        f"{pricing_url(project_id)}/configurations", json=configuration_payload(currency_id)
    )

    assert response.status_code == 403


def test_a_currency_that_is_not_configured_is_refused(
    finance_client: TestClient, project_id: str, area_types: dict[str, str]
) -> None:
    import uuid

    response = finance_client.post(
        f"{pricing_url(project_id)}/configurations",
        json=configuration_payload(str(uuid.uuid4())),
    )

    assert response.status_code == 422
    assert "not configured" in response.json()["detail"]
