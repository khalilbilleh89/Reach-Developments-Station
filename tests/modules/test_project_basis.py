"""The project's legal and monetary basis, and why it stops being editable.

A project's base currency is not a label on the record — it is what every amount
recorded under the project *means*. Changing it does not move the numbers, so
changing it after amounts exist silently restates them. The same argument holds
for the country pack and the jurisdictional codes validated against it.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.projects.models import Project
from tests.modules.conftest import (
    PROJECTS,
    SETTINGS,
    parcel_payload,
    permit_payload,
)


@pytest.fixture
def spare_currency(admin_client: TestClient) -> str:
    response = admin_client.post(
        f"{SETTINGS}/currencies", json={"code": "USD", "name": "US dollar"}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.fixture
def spare_country_pack(admin_client: TestClient, spare_currency: str) -> str:
    response = admin_client.post(
        f"{SETTINGS}/country-packs",
        json={
            "country_code": "AE",
            "name": "United Arab Emirates",
            "locale": "en-AE",
            "timezone": "Asia/Dubai",
            "default_currency_id": spare_currency,
            "area_unit": "sqm",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


# --------------------------------------------------------------------------- #
# Base currency
# --------------------------------------------------------------------------- #


def test_the_base_currency_can_be_corrected_before_any_money_exists(
    admin_client: TestClient, project_id: str, spare_currency: str
) -> None:
    """Given a setup project with no amounts, then the basis is still a correction."""
    response = admin_client.patch(
        f"{PROJECTS}/{project_id}", json={"base_currency_id": spare_currency}
    )

    assert response.status_code == 200, response.text
    assert response.json()["base_currency_code"] == "USD"


@pytest.mark.parametrize("field", ["purchase_price", "acquisition_fees"])
def test_the_base_currency_locks_once_land_cost_is_recorded(
    admin_client: TestClient, project_id: str, spare_currency: str, field: str
) -> None:
    """Given a recorded land amount, then re-denominating the project is refused.

    The stored figure would not change; only its currency would. That is silent
    financial corruption, and this MVP has no restatement to do it honestly.
    """
    created = admin_client.post(
        f"{PROJECTS}/{project_id}/parcels", json=parcel_payload(**{field: "1000000.00"})
    )
    assert created.status_code == 201, created.text

    response = admin_client.patch(
        f"{PROJECTS}/{project_id}", json={"base_currency_id": spare_currency}
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            "Project base currency cannot be changed after monetary amounts have been recorded."
        )
    }


def test_the_base_currency_locks_once_a_permit_fee_is_recorded(
    admin_client: TestClient, project_id: str, spare_currency: str
) -> None:
    """Given a recorded permit fee, then the project basis is equally locked."""
    created = admin_client.post(
        f"{PROJECTS}/{project_id}/permits", json=permit_payload(fee_amount="5000.00")
    )
    assert created.status_code == 201, created.text

    response = admin_client.patch(
        f"{PROJECTS}/{project_id}", json={"base_currency_id": spare_currency}
    )

    assert response.status_code == 409


def test_a_parcel_without_money_does_not_lock_the_currency(
    admin_client: TestClient, project_id: str, spare_currency: str
) -> None:
    """Given a parcel with no cost recorded, then nothing has been denominated yet."""
    admin_client.post(f"{PROJECTS}/{project_id}/parcels", json=parcel_payload())

    response = admin_client.patch(
        f"{PROJECTS}/{project_id}", json={"base_currency_id": spare_currency}
    )

    assert response.status_code == 200


def test_a_refused_currency_change_leaves_no_trace(
    admin_client: TestClient, project_id: str, spare_currency: str, db: Session
) -> None:
    """Given the refusal, then the currency is unchanged and nothing is audited."""
    admin_client.post(
        f"{PROJECTS}/{project_id}/parcels", json=parcel_payload(purchase_price="1000000.00")
    )
    before = db.scalars(select(Project)).one().base_currency_id
    audited = len(
        db.scalars(select(AuditEvent).where(AuditEvent.action == "project.updated")).all()
    )

    admin_client.patch(f"{PROJECTS}/{project_id}", json={"base_currency_id": spare_currency})

    db.expire_all()
    assert db.scalars(select(Project)).one().base_currency_id == before
    assert (
        len(db.scalars(select(AuditEvent).where(AuditEvent.action == "project.updated")).all())
        == audited
    )


def test_the_reporting_currency_is_not_blocked_by_recorded_money(
    admin_client: TestClient, project_id: str, spare_currency: str
) -> None:
    """Given amounts exist, then the reporting currency may still be corrected.

    Nothing is denominated in the reporting currency — it is recorded, never
    converted to — so changing it restates nothing.
    """
    admin_client.post(
        f"{PROJECTS}/{project_id}/parcels", json=parcel_payload(purchase_price="1000000.00")
    )

    response = admin_client.patch(
        f"{PROJECTS}/{project_id}", json={"reporting_currency_id": spare_currency}
    )

    assert response.status_code == 200
    assert response.json()["reporting_currency_code"] == "USD"


# --------------------------------------------------------------------------- #
# Country pack
# --------------------------------------------------------------------------- #


def test_the_country_pack_can_be_corrected_while_nothing_depends_on_it(
    admin_client: TestClient, project_id: str, spare_country_pack: str
) -> None:
    """Given a bare setup project, then the jurisdiction is still a correction."""
    response = admin_client.patch(
        f"{PROJECTS}/{project_id}", json={"country_pack_id": spare_country_pack}
    )

    assert response.status_code == 200, response.text
    assert response.json()["country_code"] == "AE"


def test_moving_country_revalidates_the_project_type_already_on_the_record(
    admin_client: TestClient,
    project_id: str,
    spare_country_pack: str,
) -> None:
    """Given a type configured only for the old country, then the move is refused.

    The code is already on the project; moving jurisdiction has to check what the
    row will hold, not only what the request happens to name.
    """
    assert (
        admin_client.patch(
            f"{PROJECTS}/{project_id}", json={"project_type_code": "RESIDENTIAL"}
        ).status_code
        == 200
    )

    response = admin_client.patch(
        f"{PROJECTS}/{project_id}", json={"country_pack_id": spare_country_pack}
    )

    assert response.status_code == 422
    assert "project_type" in response.json()["detail"]


def test_moving_country_succeeds_when_the_type_is_configured_there_too(
    admin_client: TestClient, project_id: str, spare_country_pack: str
) -> None:
    """Given the new country configures the same code, then the move is allowed."""
    admin_client.patch(f"{PROJECTS}/{project_id}", json={"project_type_code": "RESIDENTIAL"})
    assert (
        admin_client.post(
            f"{SETTINGS}/reference-values",
            json={
                "country_pack_id": spare_country_pack,
                "category": "project_type",
                "code": "RESIDENTIAL",
                "label": "Residential",
            },
        ).status_code
        == 201
    )

    response = admin_client.patch(
        f"{PROJECTS}/{project_id}", json={"country_pack_id": spare_country_pack}
    )

    assert response.status_code == 200


@pytest.mark.parametrize("record", ["parcel", "permit", "document", "planning"])
def test_the_country_pack_locks_once_dependent_records_exist(
    admin_client: TestClient, project_id: str, spare_country_pack: str, record: str
) -> None:
    """Given records validated against this jurisdiction, then it cannot be swapped.

    Ownership, title, zoning, permit and document codes were all checked against
    the country pack current when they were entered. Repointing the project
    would leave every one of them describing the wrong legal regime.
    """
    if record in {"parcel", "planning"}:
        parcel = admin_client.post(
            f"{PROJECTS}/{project_id}/parcels", json=parcel_payload()
        ).json()["id"]
        if record == "planning":
            admin_client.put(
                f"{PROJECTS}/{project_id}/parcels/{parcel}/planning-controls",
                json={"far_ratio": "4.5000", "variance_required": False},
            )
    elif record == "permit":
        admin_client.post(f"{PROJECTS}/{project_id}/permits", json=permit_payload())
    else:
        admin_client.post(
            f"{PROJECTS}/{project_id}/documents",
            json={
                "title": "Deed",
                "document_type_code": "TITLE_DEED",
                "external_url": "https://records.example.com/deed.pdf",
            },
        )

    response = admin_client.patch(
        f"{PROJECTS}/{project_id}", json={"country_pack_id": spare_country_pack}
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            "Country pack cannot be changed after project land, planning, permits "
            "or documents have been recorded."
        )
    }


# --------------------------------------------------------------------------- #
# Setup is a one-way door
# --------------------------------------------------------------------------- #


def test_a_project_cannot_return_to_setup(admin_client: TestClient, project_id: str) -> None:
    """Given a project that has left setup, then it cannot go back.

    Without this the basis lock is decorative: leave setup, return to it, and
    change the currency after all.
    """
    assert (
        admin_client.patch(f"{PROJECTS}/{project_id}", json={"status": "active"}).status_code == 200
    )

    response = admin_client.patch(f"{PROJECTS}/{project_id}", json={"status": "setup"})

    assert response.status_code == 409
    assert response.json() == {"detail": "A project cannot return to setup once it has left it."}


def test_the_basis_stays_locked_after_the_round_trip_is_refused(
    admin_client: TestClient, project_id: str, spare_currency: str
) -> None:
    """Given the return to setup is refused, then the basis remains locked."""
    admin_client.patch(f"{PROJECTS}/{project_id}", json={"status": "active"})
    admin_client.patch(f"{PROJECTS}/{project_id}", json={"status": "setup"})

    response = admin_client.patch(
        f"{PROJECTS}/{project_id}", json={"base_currency_id": spare_currency}
    )

    assert response.status_code == 409
    assert "still in setup" in response.json()["detail"]


def test_other_status_moves_are_unaffected(admin_client: TestClient, project_id: str) -> None:
    """Given ordinary lifecycle moves, then only the return to setup is special.

    This is one explicit rule, not a project workflow engine.
    """
    for status in ("predevelopment", "active", "on_hold", "active", "completed"):
        response = admin_client.patch(f"{PROJECTS}/{project_id}", json={"status": status})
        assert response.status_code == 200, f"{status}: {response.text}"


def test_staying_in_setup_is_not_a_return_to_setup(
    admin_client: TestClient, project_id: str
) -> None:
    """Given a project still in setup, then resending that status changes nothing."""
    response = admin_client.patch(
        f"{PROJECTS}/{project_id}", json={"status": "setup", "city": "Aqaba"}
    )

    assert response.status_code == 200
    assert response.json()["city"] == "Aqaba"
