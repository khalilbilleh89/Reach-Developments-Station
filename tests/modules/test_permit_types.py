"""Adding a permit type from the permit workspace, without opening Settings.

A project team files the consents their authority asks for, and until PR-V2-01
adding a missing one meant leaving the permit half-created, opening system-wide
Settings, understanding reference categories, creating a row in the right one,
scoping it to the right country pack, and coming back. In practice that meant
asking a System Administrator, and in the meantime the permit was filed under
whichever existing type was closest — which is how a register loses the ability
to answer how many building permits are outstanding.

So permit type stays a controlled vocabulary and gains a project-scoped way in.
The whole security argument for that endpoint is what it *cannot* do: the two
facts deciding what the row is — its category and its jurisdiction — come from
the route's project, never from the request. These tests are mostly about that.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.settings.models import ReferenceValue
from tests.factories import client_for, make_user
from tests.modules.conftest import PROJECTS, SETTINGS, grant_access, permit_payload


def permit_types_url(project_id: str) -> str:
    return f"{PROJECTS}/{project_id}/permit-types"


def type_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {"code": "CIVIL_DEFENCE", "label": "Civil defence approval"}
    payload.update(overrides)
    return payload


class TestReadingTheVocabulary:
    def test_the_project_offers_the_types_configured_for_its_jurisdiction(
        self, admin_client: TestClient, project_id: str
    ) -> None:
        """Given the pack's permit types, then the project lists them."""
        response = admin_client.get(permit_types_url(project_id))

        assert response.status_code == 200, response.text
        codes = {value["code"] for value in response.json()}
        assert {"BUILDING", "PLANNING"} <= codes

    def test_no_other_reference_category_leaks_through(
        self, admin_client: TestClient, project_id: str
    ) -> None:
        """Given zoning and document types exist, then this route shows neither.

        The route reads one category. A permit-type selector that also offered
        ``TITLE_DEED`` would be a general reference browser wearing a permit
        label, and the first person to pick one would create a permit nobody
        can file.
        """
        response = admin_client.get(permit_types_url(project_id))

        codes = {value["code"] for value in response.json()}
        assert "TITLE_DEED" not in codes
        assert "RES_B" not in codes

    def test_a_retired_type_is_still_listed_and_says_so(
        self, admin_client: TestClient, project_id: str
    ) -> None:
        """Given a retired type, then it is returned inactive rather than dropped.

        Two different questions share this list: *what may I file today* and
        *what is this permit from 2019 called*. Dropping the retired rows would
        answer the first by making the second impossible, and a permit whose
        type rendered as a bare code — or worse, got rewritten to a current
        one — is a permit whose history was edited to tidy a dropdown.
        """
        values = admin_client.get(f"{SETTINGS}/reference-values?category=permit_type").json()
        planning = next(value for value in values if value["code"] == "PLANNING")
        admin_client.patch(
            f"{SETTINGS}/reference-values/{planning['id']}", json={"is_active": False}
        )

        listed = admin_client.get(permit_types_url(project_id)).json()

        retired = next(value for value in listed if value["code"] == "PLANNING")
        assert retired["is_active"] is False
        assert retired["label"] == "Planning approval"
        assert next(value for value in listed if value["code"] == "BUILDING")["is_active"] is True

    def test_a_project_the_caller_cannot_open_answers_not_found(
        self, db: Session, project_id: str
    ) -> None:
        """Given no membership, then the vocabulary is not even enumerable."""
        outsider = make_user(db, email="outsider@example.com", roles=("project_manager",))

        response = client_for(outsider.email).get(permit_types_url(project_id))

        assert response.status_code == 404


class TestAddingATypeFromTheWorkspace:
    def test_the_technical_writer_may_add_the_consent_their_authority_asks_for(
        self, engineer_client: TestClient, project_id: str
    ) -> None:
        """Given Design / Engineering, then a permit type can be created.

        The role already trusted with permits and planning controls, and
        deliberately not the System Administrator the generic Settings write
        requires: the point of this endpoint is that a project team can extend
        one vocabulary without being handed global configuration.
        """
        response = engineer_client.post(permit_types_url(project_id), json=type_payload())

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["code"] == "CIVIL_DEFENCE"
        assert body["label"] == "Civil defence approval"
        assert body["is_active"] is True

    def test_a_role_without_technical_write_is_refused(
        self, advisor_client: TestClient, project_id: str
    ) -> None:
        """Given a Sales Advisor inside the project, then creation is refused.

        403 rather than 404: they can already see the project, so there is
        nothing left to conceal — only an action to refuse.
        """
        response = advisor_client.post(permit_types_url(project_id), json=type_payload())

        assert response.status_code == 403

    def test_a_project_the_caller_cannot_open_answers_not_found(
        self, db: Session, project_id: str
    ) -> None:
        """Given no membership, then creation is 404 rather than 403.

        A 403 would confirm the identifier names a real project, which is what
        somebody enumerating them wants to learn.
        """
        outsider = make_user(db, email="outsider2@example.com", roles=("design_engineering",))

        response = client_for(outsider.email).post(
            permit_types_url(project_id), json=type_payload()
        )

        assert response.status_code == 404

    def test_the_category_comes_from_the_route(
        self, engineer_client: TestClient, project_id: str, db: Session
    ) -> None:
        """Given a created type, then it is stored under ``permit_type``."""
        created = engineer_client.post(permit_types_url(project_id), json=type_payload()).json()

        stored = db.scalars(select(ReferenceValue).where(ReferenceValue.id == created["id"])).one()
        assert stored.category == "permit_type"

    def test_the_jurisdiction_comes_from_the_project(
        self, engineer_client: TestClient, project_id: str, country_pack_id: str, db: Session
    ) -> None:
        """Given a created type, then it is scoped to the project's country pack.

        Not global, and not a pack the caller named. A permit type is a
        jurisdictional fact, and one project's team should not be able to add a
        consent to every other jurisdiction in the system.
        """
        created = engineer_client.post(permit_types_url(project_id), json=type_payload()).json()

        stored = db.scalars(select(ReferenceValue).where(ReferenceValue.id == created["id"])).one()
        assert str(stored.country_pack_id) == country_pack_id

    def test_naming_another_category_is_refused_rather_than_ignored(
        self, engineer_client: TestClient, project_id: str
    ) -> None:
        """Given ``category`` in the body, then the request is refused.

        Refused, not ignored. A caller reaching for this field is trying to
        write somewhere else, and answering 201 to a request that did something
        other than what it asked for is how that gets discovered late.
        """
        response = engineer_client.post(
            permit_types_url(project_id), json=type_payload(category="tax_rule")
        )

        assert response.status_code == 422

    def test_naming_another_jurisdiction_is_refused_rather_than_ignored(
        self, engineer_client: TestClient, project_id: str
    ) -> None:
        """Given ``country_pack_id`` in the body, then the request is refused."""
        response = engineer_client.post(
            permit_types_url(project_id), json=type_payload(country_pack_id=None)
        )

        assert response.status_code == 422

    def test_a_duplicate_code_conflicts_rather_than_inventing_a_suffix(
        self, engineer_client: TestClient, project_id: str
    ) -> None:
        """Given a code already in the pack, then it is a conflict.

        Not ``BUILDING_2``. An identifier the operator never chose is one they
        will not recognise in a register six months later, and two types whose
        codes differ by a digit are two types nobody can tell apart.
        """
        response = engineer_client.post(
            permit_types_url(project_id), json=type_payload(code="BUILDING", label="Building")
        )

        assert response.status_code == 409

    def test_creation_is_audited_once(
        self, engineer_client: TestClient, project_id: str, db: Session
    ) -> None:
        """Given a created type, then exactly one audit event records it.

        The Settings service owns the creation and writes its own event. A
        second event from the Projects router would be duplicate noise about
        one mutation, and an audit trail that double-counts is one nobody
        trusts to count.
        """
        created = engineer_client.post(permit_types_url(project_id), json=type_payload()).json()

        events = list(
            db.scalars(
                select(AuditEvent).where(
                    AuditEvent.entity_type == "reference_value",
                    AuditEvent.entity_id == created["id"],
                )
            )
        )
        assert [event.action for event in events] == ["reference_value.created"]

    def test_a_new_type_is_immediately_usable_on_a_permit(
        self, engineer_client: TestClient, project_id: str
    ) -> None:
        """Given the type was just added, then a permit may be filed under it.

        The whole point of the endpoint. If the value needed a Settings
        round-trip, an activation step or a cache to clear before a permit
        could name it, the operator would still be stuck mid-form.
        """
        engineer_client.post(permit_types_url(project_id), json=type_payload())

        response = engineer_client.post(
            f"{PROJECTS}/{project_id}/permits",
            json=permit_payload(permit_code="CD-001", permit_type_code="CIVIL_DEFENCE"),
        )

        assert response.status_code == 201, response.text
        assert response.json()["permit_type_code"] == "CIVIL_DEFENCE"

    def test_the_endpoint_cannot_write_a_global_value(
        self, engineer_client: TestClient, project_id: str, db: Session
    ) -> None:
        """Given any request to this route, then no global reference value appears.

        The strict body already refuses ``country_pack_id``; this asserts the
        outcome rather than the mechanism, so replacing the schema with
        something more permissive fails here too.
        """
        before = set(
            db.scalars(select(ReferenceValue.id).where(ReferenceValue.country_pack_id.is_(None)))
        )

        engineer_client.post(permit_types_url(project_id), json=type_payload())

        after = set(
            db.scalars(select(ReferenceValue.id).where(ReferenceValue.country_pack_id.is_(None)))
        )
        assert after == before


class TestGenericSettingsStaysAdministratorOnly:
    def test_the_new_route_does_not_widen_the_settings_write(
        self, admin_client: TestClient, db: Session, project_id: str
    ) -> None:
        """Given Design / Engineering, then generic reference writes stay refused.

        The permit-type endpoint is narrow on purpose. If it had been built by
        relaxing the Settings permission instead, the same person could create
        a tax rule — and this is the test that would have caught it.
        """
        engineer = make_user(db, email="design3@example.com", roles=("design_engineering",))
        grant_access(admin_client, project_id, engineer)

        response = client_for(engineer.email).post(
            f"{SETTINGS}/reference-values",
            json={"category": "permit_type", "code": "SNEAKY", "label": "Sneaky"},
        )

        assert response.status_code == 403
