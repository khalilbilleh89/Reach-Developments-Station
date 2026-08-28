"""Request bodies refuse what they do not declare.

Pydantic's default is to ignore an unknown key. For a register of statutory and
financial record that is the wrong default: a client that misspells a control
flag, or names a field this API deliberately does not accept, would be told the
mutation succeeded when part of it was silently dropped.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from tests.modules.conftest import (
    PROJECTS,
    parcel_payload,
    permit_payload,
    project_payload,
)


def test_a_project_cannot_be_created_with_an_unknown_field(
    admin_client: TestClient, country_pack_id: str, currency_id: str, reference_data: None
) -> None:
    response = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, budget="1000000")
    )

    assert response.status_code == 422


def test_a_misspelled_project_field_is_refused(admin_client: TestClient, project_id: str) -> None:
    """Given ``citty``, then the request fails rather than quietly doing nothing."""
    response = admin_client.patch(f"{PROJECTS}/{project_id}", json={"citty": "Aqaba"})

    assert response.status_code == 422
    assert admin_client.get(f"{PROJECTS}/{project_id}").json()["city"] == "Amman"


def test_a_refused_request_writes_no_audit_event(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    """Given a rejected body, then nothing reached the service at all."""
    before = len(db.scalars(select(AuditEvent).where(AuditEvent.action == "project.updated")).all())

    admin_client.patch(f"{PROJECTS}/{project_id}", json={"citty": "Aqaba", "city": "Aqaba"})

    assert (
        len(db.scalars(select(AuditEvent).where(AuditEvent.action == "project.updated")).all())
        == before
    )


@pytest.mark.parametrize("field", ["land_aera", "purchase_prize", "is_activ"])
def test_a_misspelled_parcel_field_is_refused(
    admin_client: TestClient, project_id: str, field: str
) -> None:
    created = admin_client.post(f"{PROJECTS}/{project_id}/parcels", json=parcel_payload()).json()

    response = admin_client.patch(
        f"{PROJECTS}/{project_id}/parcels/{created['id']}", json={field: "1"}
    )

    assert response.status_code == 422


def test_a_parcel_cannot_be_created_with_an_unknown_field(
    admin_client: TestClient, project_id: str
) -> None:
    response = admin_client.post(
        f"{PROJECTS}/{project_id}/parcels", json=parcel_payload(market_value="5000000.00")
    )

    assert response.status_code == 422


def test_planning_controls_refuse_an_unknown_control(
    admin_client: TestClient, project_id: str
) -> None:
    parcel = admin_client.post(f"{PROJECTS}/{project_id}/parcels", json=parcel_payload()).json()[
        "id"
    ]

    response = admin_client.put(
        f"{PROJECTS}/{project_id}/parcels/{parcel}/planning-controls",
        json={"far_ratio": "4.5000", "variance_required": False, "max_units": 120},
    )

    assert response.status_code == 422


def test_a_permit_cannot_be_created_with_a_status(
    admin_client: TestClient, project_id: str
) -> None:
    """Given a status on creation, then it is refused: permits start not_started."""
    response = admin_client.post(
        f"{PROJECTS}/{project_id}/permits", json=permit_payload(status="issued")
    )

    assert response.status_code == 422


def test_a_transition_refuses_an_unknown_field(admin_client: TestClient, project_id: str) -> None:
    permit = admin_client.post(f"{PROJECTS}/{project_id}/permits", json=permit_payload()).json()[
        "id"
    ]

    response = admin_client.post(
        f"{PROJECTS}/{project_id}/permits/{permit}/transitions",
        json={"to_status": "preparing", "effective_date": "2026-01-05", "note": "typo"},
    )

    assert response.status_code == 422


def test_a_document_reference_refuses_an_unknown_field(
    admin_client: TestClient, project_id: str
) -> None:
    response = admin_client.post(
        f"{PROJECTS}/{project_id}/documents",
        json={
            "title": "Deed",
            "document_type_code": "TITLE_DEED",
            "external_url": "https://records.example.com/deed.pdf",
            "file": "deed.pdf",
        },
    )

    assert response.status_code == 422


def test_an_access_change_refuses_an_unknown_field(
    admin_client: TestClient, manager: object, project_id: str
) -> None:
    response = admin_client.patch(
        f"{PROJECTS}/{project_id}/access/{manager.id}",  # type: ignore[attr-defined]
        json={"is_active": False, "role_key": "system_admin"},
    )

    assert response.status_code == 422


def test_declared_fields_still_work(admin_client: TestClient, project_id: str) -> None:
    """Given only declared fields, then strictness changes nothing about ordinary use."""
    response = admin_client.patch(
        f"{PROJECTS}/{project_id}", json={"city": "Aqaba", "status": "predevelopment"}
    )

    assert response.status_code == 200
    assert response.json()["city"] == "Aqaba"
