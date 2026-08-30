"""Adversarial reads: what a caller learns when they ask for something not theirs.

Two rules under test. A hidden thing answers as a thing that does not exist —
404, never 403, because a 403 confirms the identifier is real. And personal data
is decided before serialisation: a caller who may not see a passport number gets
a response with no such field on it, not a blank one.

Nothing here may answer 5xx. A crash is an answer too, and usually a more
informative one than the API meant to give.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.access.models import User
from tests.factories import client_for, make_user
from tests.modules.conftest import (
    PROJECTS,
    grant_access,
    inventory_url,
    project_payload,
    sales_url,
)


@pytest.fixture
def hidden_phase_advisor(
    db: Session,
    admin_client: TestClient,
    project_id: str,
    phase_id: str,
) -> TestClient:
    """Sales Operations who may see the project, but no phase of it.

    Phase scope ``selected`` with nothing selected is the sharpest form of the
    boundary: every unit in the project is invisible, so every sale of one is
    too.
    """
    user = make_user(db, email="restricted-ops@example.com", roles=("sales_operations",))
    grant_access(admin_client, project_id, user)
    scoped = admin_client.patch(
        f"{PROJECTS}/{project_id}/access/{user.id}/phase-scope",
        json={"phase_scope": "selected"},
    )
    assert scoped.status_code == 200, scoped.text
    return client_for(user.email)


@pytest.fixture
def other_project_id(admin_client: TestClient, country_pack_id: str, currency_id: str) -> str:
    response = admin_client.post(
        PROJECTS,
        json=project_payload(country_pack_id, currency_id, code="OTHER", name="Other project"),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_a_reservation_in_a_hidden_phase_answers_as_missing(
    hidden_phase_advisor: TestClient, project_id: str, active_reservation: str
) -> None:
    response = hidden_phase_advisor.get(
        f"{sales_url(project_id)}/reservations/{active_reservation}"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Unit not found."


def test_a_contract_in_a_hidden_phase_answers_as_missing(
    hidden_phase_advisor: TestClient, project_id: str, active_sale: str
) -> None:
    response = hidden_phase_advisor.get(f"{sales_url(project_id)}/contracts/{active_sale}")

    assert response.status_code == 404


def test_a_hidden_phase_legal_timeline_answers_as_missing(
    hidden_phase_advisor: TestClient, project_id: str, active_sale: str
) -> None:
    response = hidden_phase_advisor.get(
        f"{sales_url(project_id)}/contracts/{active_sale}/legal-events"
    )

    assert response.status_code == 404


def test_a_hidden_phase_register_shows_no_rows(
    hidden_phase_advisor: TestClient, project_id: str, active_sale: str
) -> None:
    response = hidden_phase_advisor.get(f"{sales_url(project_id)}/register")

    assert response.status_code == 200, response.text
    assert response.json()["rows"] == []
    assert response.json()["totals"]["units"] == 0


def test_a_reservation_from_another_project_answers_as_missing(
    sales_ops_client: TestClient,
    admin_client: TestClient,
    other_project_id: str,
    sales_ops: User,
    active_reservation: str,
) -> None:
    """Given a real reservation id under the wrong project, then it is not found."""
    grant_access(admin_client, other_project_id, sales_ops)

    response = sales_ops_client.get(
        f"{sales_url(other_project_id)}/reservations/{active_reservation}"
    )

    assert response.status_code == 404


def test_a_contract_from_another_project_answers_as_missing(
    sales_ops_client: TestClient,
    admin_client: TestClient,
    other_project_id: str,
    sales_ops: User,
    active_sale: str,
) -> None:
    grant_access(admin_client, other_project_id, sales_ops)

    response = sales_ops_client.get(f"{sales_url(other_project_id)}/contracts/{active_sale}")

    assert response.status_code == 404


def test_a_client_from_another_project_cannot_be_reserved_against(
    sales_ops_client: TestClient,
    admin_client: TestClient,
    other_project_id: str,
    sales_ops: User,
    project_id: str,
    released_unit: str,
    buyer_id: str,
    sales_reference_data: None,
) -> None:
    """Unit from this project, buyer from another: refused, not silently mixed."""
    grant_access(admin_client, other_project_id, sales_ops)
    admin_client.patch(f"{PROJECTS}/{other_project_id}", json={"status": "predevelopment"})
    other_buyer = sales_ops_client.post(
        f"{sales_url(other_project_id)}/clients", json={"display_name": "Someone Else"}
    )
    assert other_buyer.status_code == 201, other_buyer.text

    response = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations",
        json={"unit_id": released_unit, "client_id": other_buyer.json()["id"]},
    )

    assert response.status_code == 404


def test_an_unknown_identifier_is_not_found_rather_than_a_crash(
    sales_ops_client: TestClient, project_id: str
) -> None:
    missing = uuid.uuid4()

    for path in (
        f"reservations/{missing}",
        f"contracts/{missing}",
        f"clients/{missing}",
        f"contracts/{missing}/legal-events",
        f"contracts/{missing}/handover",
        f"contracts/{missing}/cancellation",
    ):
        response = sales_ops_client.get(f"{sales_url(project_id)}/{path}")
        assert response.status_code == 404, path


def test_a_malformed_identifier_is_refused_rather_than_a_crash(
    sales_ops_client: TestClient, project_id: str
) -> None:
    response = sales_ops_client.get(f"{sales_url(project_id)}/reservations/not-a-uuid")

    assert response.status_code == 422


def test_an_advisor_does_not_receive_another_buyers_identity_documents(
    advisor_client: TestClient, sales_ops_client: TestClient, project_id: str, buyer_id: str
) -> None:
    """The buyer belongs to nobody in particular, so the advisor cannot see them at all."""
    listed = advisor_client.get(f"{sales_url(project_id)}/clients")
    single = advisor_client.get(f"{sales_url(project_id)}/clients/{buyer_id}")

    assert listed.status_code == 200
    assert listed.json() == []
    assert single.status_code == 404


def test_a_project_manager_sees_the_commercial_summary_and_no_personal_data(
    manager_client: TestClient,
    admin_client: TestClient,
    manager: User,
    project_id: str,
    buyer_id: str,
) -> None:
    grant_access(admin_client, project_id, manager)

    response = manager_client.get(f"{sales_url(project_id)}/clients/{buyer_id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["display_name"] == "Rana Haddad"
    for field in ("email", "phone", "address"):
        assert field not in body


def test_finance_sees_the_money_and_not_the_person(
    finance_client: TestClient, project_id: str, buyer_id: str
) -> None:
    response = finance_client.get(f"{sales_url(project_id)}/clients/{buyer_id}/parties")

    assert response.status_code == 200, response.text
    for party in response.json():
        assert "identity_document_number" not in party
        assert "tax_id" not in party
        assert party["name_as_identification"] == "Rana Haddad"


def test_an_administrator_does_not_become_a_reader_of_personal_data(
    admin_client: TestClient, project_id: str, buyer_id: str
) -> None:
    """Administering a database is not authority over the people in it."""
    response = admin_client.get(f"{sales_url(project_id)}/clients/{buyer_id}")

    assert response.status_code == 200, response.text
    assert "phone" not in response.json()


def test_legal_and_collections_do_receive_what_their_work_needs(
    legal_client: TestClient, collections_client: TestClient, project_id: str, buyer_id: str
) -> None:
    for client in (legal_client, collections_client):
        response = client.get(f"{sales_url(project_id)}/clients/{buyer_id}/parties")
        assert response.status_code == 200, response.text
        assert response.json()[0]["identity_document_number"] == "P1234567"


def test_a_frozen_contract_party_is_redacted_for_the_same_readers(
    manager_client: TestClient,
    admin_client: TestClient,
    manager: User,
    legal_client: TestClient,
    project_id: str,
    submitted_sale: str,
) -> None:
    grant_access(admin_client, project_id, manager)

    restricted = manager_client.get(f"{sales_url(project_id)}/contracts/{submitted_sale}").json()[
        "parties"
    ]
    permitted = legal_client.get(f"{sales_url(project_id)}/contracts/{submitted_sale}").json()[
        "parties"
    ]

    assert "identity_document_number" not in restricted[0]
    assert permitted[0]["identity_document_number"] == "P1234567"


def test_the_audit_trail_never_carries_raw_personal_data(
    sales_ops_client: TestClient, admin_client: TestClient, project_id: str, buyer_id: str
) -> None:
    changed = sales_ops_client.patch(
        f"{sales_url(project_id)}/clients/{buyer_id}", json={"phone": "+962799999999"}
    )
    assert changed.status_code == 200, changed.text

    events = admin_client.get("/api/v1/audit-events", params={"entity_type": "client"})
    assert events.status_code == 200, events.text
    body = events.text

    assert "+962799999999" not in body
    assert "P1234567" not in body
    assert "client.updated" in body
    assert "phone" in body  # the field name is recorded; the value is not


def test_sales_operations_cannot_record_a_registration(
    sales_ops_client: TestClient, project_id: str, active_sale: str
) -> None:
    response = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts/{active_sale}/legal-events",
        json={"event_type": "registered", "event_date": "2026-02-20"},
    )

    assert response.status_code == 403


def test_legal_cannot_change_a_contract_price(
    legal_client: TestClient, project_id: str, submitted_sale: str
) -> None:
    invented = legal_client.patch(
        f"{sales_url(project_id)}/contracts/{submitted_sale}",
        json={"net_contract_price_ex_tax": "1.00"},
    )
    allowed_shape = legal_client.patch(
        f"{sales_url(project_id)}/contracts/{submitted_sale}", json={"spa_number": "SPA-X"}
    )

    assert invented.status_code == 422
    assert allowed_shape.status_code == 403


def test_design_engineering_has_no_business_in_the_sales_workspace(
    db: Session, admin_client: TestClient, project_id: str, active_sale: str
) -> None:
    user = make_user(db, email="design-sales@example.com", roles=("design_engineering",))
    grant_access(admin_client, project_id, user)
    engineer = client_for(user.email)

    assert engineer.get(f"{sales_url(project_id)}/register").status_code == 403
    assert engineer.get(f"{sales_url(project_id)}/contracts").status_code == 403


def test_an_auditor_reads_everything_and_writes_nothing(
    db: Session, admin_client: TestClient, project_id: str, active_sale: str, buyer_id: str
) -> None:
    user = make_user(db, email="auditor@example.com", roles=("auditor",))
    grant_access(admin_client, project_id, user)
    auditor = client_for(user.email)

    read = auditor.get(f"{sales_url(project_id)}/contracts/{active_sale}")
    write = auditor.post(
        f"{sales_url(project_id)}/contracts/{active_sale}/cancellation",
        json={"initiated_by_party": "buyer", "reason": "Trying it on"},
    )

    assert read.status_code == 200, read.text
    assert write.status_code == 403


def test_a_hidden_unit_cannot_be_reserved_through_its_identifier(
    hidden_phase_advisor: TestClient, project_id: str, released_unit: str, buyer_id: str
) -> None:
    response = hidden_phase_advisor.post(
        f"{sales_url(project_id)}/reservations",
        json={"unit_id": released_unit, "client_id": buyer_id},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Unit not found."


def test_the_unit_endpoint_and_the_sales_endpoint_agree_about_what_is_hidden(
    hidden_phase_advisor: TestClient, project_id: str, released_unit: str
) -> None:
    unit = hidden_phase_advisor.get(f"{inventory_url(project_id)}/units/{released_unit}")
    reservations = hidden_phase_advisor.get(
        f"{sales_url(project_id)}/reservations", params={"unit_id": released_unit}
    )

    assert unit.status_code == 404
    assert reservations.status_code == 200
    assert reservations.json() == []
