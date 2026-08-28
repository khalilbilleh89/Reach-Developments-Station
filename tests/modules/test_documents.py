"""Document references: pointers to evidence, not a document management system."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from tests.modules.conftest import (
    PROJECTS,
    SETTINGS,
    parcel_payload,
    permit_payload,
    project_payload,
)


def _document(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "title": "Title deed 9911",
        "document_type_code": "TITLE_DEED",
        "external_url": "https://records.example.com/deeds/9911.pdf",
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def documents_url(project_id: str) -> str:
    return f"{PROJECTS}/{project_id}/documents"


def test_a_document_may_be_attached_to_the_project_alone(
    admin_client: TestClient, documents_url: str
) -> None:
    response = admin_client.post(documents_url, json=_document())

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["parcel_id"] is None
    assert body["permit_id"] is None
    assert body["external_url"] == "https://records.example.com/deeds/9911.pdf"


def test_a_document_may_be_attached_to_a_parcel(
    admin_client: TestClient, project_id: str, documents_url: str
) -> None:
    parcel = admin_client.post(f"{PROJECTS}/{project_id}/parcels", json=parcel_payload()).json()[
        "id"
    ]

    response = admin_client.post(documents_url, json=_document(parcel_id=parcel))

    assert response.status_code == 201
    assert response.json()["parcel_id"] == parcel


def test_a_document_may_be_attached_to_a_permit(
    admin_client: TestClient, project_id: str, documents_url: str
) -> None:
    permit = admin_client.post(f"{PROJECTS}/{project_id}/permits", json=permit_payload()).json()[
        "id"
    ]

    response = admin_client.post(documents_url, json=_document(permit_id=permit))

    assert response.status_code == 201
    assert response.json()["permit_id"] == permit


def test_a_document_cannot_attach_to_a_parcel_and_a_permit_at_once(
    admin_client: TestClient, project_id: str, documents_url: str
) -> None:
    """Given both, then 'which record does this support' would have no answer."""
    parcel = admin_client.post(f"{PROJECTS}/{project_id}/parcels", json=parcel_payload()).json()[
        "id"
    ]
    permit = admin_client.post(f"{PROJECTS}/{project_id}/permits", json=permit_payload()).json()[
        "id"
    ]

    response = admin_client.post(documents_url, json=_document(parcel_id=parcel, permit_id=permit))

    assert response.status_code == 422
    assert "not to both" in response.json()["detail"]


def test_the_database_refuses_a_double_attachment_independently(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    """Given the service check were bypassed, then the check constraint still holds."""
    import uuid as uuid_module

    from sqlalchemy.exc import IntegrityError

    from app.modules.projects.models import DocumentReference, LandParcel, Permit, Project

    admin_client.post(f"{PROJECTS}/{project_id}/parcels", json=parcel_payload())
    admin_client.post(f"{PROJECTS}/{project_id}/permits", json=permit_payload())
    project = db.scalars(select(Project)).one()
    parcel = db.scalars(select(LandParcel)).one()
    permit = db.scalars(select(Permit)).one()

    db.add(
        DocumentReference(
            id=uuid_module.uuid4(),
            project_id=project.id,
            parcel_id=parcel.id,
            permit_id=permit.id,
            title="Sneaky",
            document_type_code="TITLE_DEED",
            external_url="https://example.com/x.pdf",
            created_by_user_id=project.created_by_user_id,
        )
    )

    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_a_parcel_from_another_project_cannot_be_attached(
    admin_client: TestClient, documents_url: str, country_pack_id: str, currency_id: str
) -> None:
    other = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="OTHER")
    ).json()["id"]
    foreign = admin_client.post(f"{PROJECTS}/{other}/parcels", json=parcel_payload()).json()["id"]

    response = admin_client.post(documents_url, json=_document(parcel_id=foreign))

    assert response.status_code == 404
    assert response.json() == {"detail": "Land parcel not found."}


@pytest.mark.parametrize(
    "url", ["not-a-url", "ftp://files.example.com/a.pdf", "javascript:alert(1)", ""]
)
def test_an_unusable_document_url_is_rejected(
    admin_client: TestClient, documents_url: str, url: str
) -> None:
    """Given something that is not an ordinary web address, then it is refused."""
    response = admin_client.post(documents_url, json=_document(external_url=url))

    assert response.status_code == 422


def test_an_unconfigured_document_type_is_rejected(
    admin_client: TestClient, documents_url: str
) -> None:
    response = admin_client.post(documents_url, json=_document(document_type_code="INVENTED"))

    assert response.status_code == 422
    assert "document_type" in response.json()["detail"]


def test_a_retired_document_stays_visible_in_history(
    admin_client: TestClient, documents_url: str
) -> None:
    """Given a superseded reference, then it is deactivated and still listed."""
    created = admin_client.post(documents_url, json=_document()).json()

    admin_client.patch(f"{documents_url}/{created['id']}", json={"is_active": False})

    everything = admin_client.get(documents_url).json()
    active_only = admin_client.get(f"{documents_url}?is_active=true").json()
    assert [item["id"] for item in everything] == [created["id"]]
    assert active_only == []


def test_documents_can_be_filtered_by_what_they_support(
    admin_client: TestClient, project_id: str, documents_url: str
) -> None:
    parcel = admin_client.post(f"{PROJECTS}/{project_id}/parcels", json=parcel_payload()).json()[
        "id"
    ]
    admin_client.post(documents_url, json=_document(parcel_id=parcel))
    admin_client.post(documents_url, json=_document(title="Project charter"))

    filtered = admin_client.get(f"{documents_url}?parcel_id={parcel}").json()

    assert [item["title"] for item in filtered] == ["Title deed 9911"]


def test_there_is_no_file_upload_endpoint(admin_client: TestClient, project_id: str) -> None:
    """Given this PR stores references only, then no upload path exists."""
    for path in ("documents/upload", "documents/files", "files"):
        response = admin_client.post(f"{PROJECTS}/{project_id}/{path}", json={})
        assert response.status_code == 404, path


def test_documents_have_no_delete_endpoint(admin_client: TestClient, documents_url: str) -> None:
    created = admin_client.post(documents_url, json=_document()).json()

    assert admin_client.delete(f"{documents_url}/{created['id']}").status_code == 404


def test_a_retired_document_type_stays_on_existing_references(
    admin_client: TestClient, documents_url: str
) -> None:
    created = admin_client.post(documents_url, json=_document()).json()
    values = admin_client.get(f"{SETTINGS}/reference-values?category=document_type").json()
    admin_client.patch(f"{SETTINGS}/reference-values/{values[0]['id']}", json={"is_active": False})

    listing = admin_client.get(documents_url).json()

    assert listing[0]["document_type_code"] == "TITLE_DEED"
    assert listing[0]["id"] == created["id"]


def test_document_changes_are_audited(
    admin_client: TestClient, documents_url: str, db: Session
) -> None:
    created = admin_client.post(documents_url, json=_document()).json()
    admin_client.patch(f"{documents_url}/{created['id']}", json={"title": "Title deed 9911 (v2)"})

    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.action.like("document_reference.%"))
        .order_by(AuditEvent.occurred_at)
    ).all()

    assert [event.action for event in events] == [
        "document_reference.created",
        "document_reference.updated",
    ]
    assert events[1].before_data["title"] == "Title deed 9911"
    assert events[1].after_data["title"] == "Title deed 9911 (v2)"
