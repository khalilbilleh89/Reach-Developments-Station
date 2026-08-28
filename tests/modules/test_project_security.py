"""Adversarial coverage: cost redaction and cross-project identifier substitution.

Both are checked against the raw response body. Asserting a ``financials_visible``
flag would prove only that a flag was set; what matters is whether the number is
in the bytes that leave the server.
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
    parcel_payload,
    permit_payload,
    project_payload,
)

#: Deliberately distinctive so a leak anywhere in a response is unmistakable.
PURCHASE_PRICE = "987654.32"
ACQUISITION_FEES = "12345.67"
PERMIT_FEE = "7654.32"

SECRET_FIGURES = (PURCHASE_PRICE, ACQUISITION_FEES, PERMIT_FEE)

#: Roles cleared to see development cost, and roles that are not.
FINANCIAL_ROLES = ("finance", "approver_cfo", "executive_viewer", "auditor")
RESTRICTED_ROLES = ("sales_advisor", "sales_operations", "legal", "collections")


@pytest.fixture
def funded_project(admin_client: TestClient, project_id: str) -> str:
    """A project carrying land cost and a permit fee."""
    created = admin_client.post(
        f"{PROJECTS}/{project_id}/parcels",
        json=parcel_payload(purchase_price=PURCHASE_PRICE, acquisition_fees=ACQUISITION_FEES),
    )
    assert created.status_code == 201, created.text
    permit = admin_client.post(
        f"{PROJECTS}/{project_id}/permits", json=permit_payload(fee_amount=PERMIT_FEE)
    )
    assert permit.status_code == 201, permit.text
    return project_id


# --------------------------------------------------------------------------- #
# Financial redaction
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("role", RESTRICTED_ROLES)
def test_a_restricted_role_never_receives_development_cost(
    admin_client: TestClient, db: Session, funded_project: str, role: str
) -> None:
    """Given a role with no business seeing cost, then no figure reaches the body."""
    user = make_user(db, email=f"{role}@example.com", roles=(role,))
    grant_access(admin_client, funded_project, user)
    client = client_for(user.email)

    parcels = client.get(f"{PROJECTS}/{funded_project}/parcels")
    permits = client.get(f"{PROJECTS}/{funded_project}/permits")

    for response in (parcels, permits):
        assert response.status_code == 200
        for figure in SECRET_FIGURES:
            assert figure not in response.text, f"{role} saw {figure}"
    assert parcels.json()[0]["purchase_price"] is None
    assert parcels.json()[0]["acquisition_fees"] is None
    assert parcels.json()[0]["financials_visible"] is False
    assert permits.json()["permits"][0]["fee_amount"] is None


def test_a_hidden_cost_is_null_and_never_a_zero(
    admin_client: TestClient, db: Session, funded_project: str
) -> None:
    """Given a restricted caller, then absence reads as absence, not as free land."""
    user = make_user(db, email="advisor2@example.com", roles=("sales_advisor",))
    grant_access(admin_client, funded_project, user)

    parcel = client_for(user.email).get(f"{PROJECTS}/{funded_project}/parcels").json()[0]

    assert parcel["purchase_price"] is None
    assert parcel["purchase_price"] != "0.00"
    assert parcel["base_currency_code"] is None


@pytest.mark.parametrize("role", FINANCIAL_ROLES)
def test_an_authorised_role_receives_the_exact_decimal(
    admin_client: TestClient, db: Session, funded_project: str, role: str
) -> None:
    """Given a role cleared for cost, then the figure comes back exactly."""
    user = make_user(db, email=f"{role}@example.com", roles=(role,))
    grant_access(admin_client, funded_project, user)
    client = client_for(user.email)

    parcel = client.get(f"{PROJECTS}/{funded_project}/parcels").json()[0]
    permit = client.get(f"{PROJECTS}/{funded_project}/permits").json()["permits"][0]

    assert parcel["purchase_price"] == PURCHASE_PRICE
    assert parcel["acquisition_fees"] == ACQUISITION_FEES
    assert parcel["financials_visible"] is True
    # The governing currency travels with the money, so nothing has to assume.
    assert parcel["base_currency_code"] == "JOD"
    assert permit["fee_amount"] == PERMIT_FEE


def test_restricted_callers_still_read_the_operational_facts(
    admin_client: TestClient, db: Session, funded_project: str
) -> None:
    """Given cost is withheld, then the rest of the land record is still usable."""
    user = make_user(db, email="ops@example.com", roles=("sales_operations",))
    grant_access(admin_client, funded_project, user)

    parcel = client_for(user.email).get(f"{PROJECTS}/{funded_project}/parcels").json()[0]

    assert parcel["plot_number"] == "PLOT-1"
    assert parcel["land_area"] == "4500.0000"
    assert parcel["title_status_code"] == "REGISTERED"


def test_a_single_parcel_read_redacts_as_the_list_does(
    admin_client: TestClient, db: Session, funded_project: str
) -> None:
    """Given the detail route, then it redacts identically to the register."""
    user = make_user(db, email="legal2@example.com", roles=("legal",))
    grant_access(admin_client, funded_project, user)
    client = client_for(user.email)
    parcel_id = admin_client.get(f"{PROJECTS}/{funded_project}/parcels").json()[0]["id"]

    response = client.get(f"{PROJECTS}/{funded_project}/parcels/{parcel_id}")

    assert response.status_code == 200
    assert PURCHASE_PRICE not in response.text


# --------------------------------------------------------------------------- #
# Cross-project identifier substitution
# --------------------------------------------------------------------------- #


@pytest.fixture
def two_projects(
    admin_client: TestClient, country_pack_id: str, currency_id: str, reference_data: None
) -> dict[str, dict[str, str]]:
    """Two fully populated projects, so every child type can be cross-tested."""
    built: dict[str, dict[str, str]] = {}
    for key, code in (("a", "PROJECT-A"), ("b", "PROJECT-B")):
        project = admin_client.post(
            PROJECTS,
            json=project_payload(
                country_pack_id, currency_id, code=code, name=f"Project {key.upper()}"
            ),
        ).json()["id"]
        parcel = admin_client.post(
            f"{PROJECTS}/{project}/parcels",
            json=parcel_payload(purchase_price=PURCHASE_PRICE),
        ).json()["id"]
        admin_client.put(
            f"{PROJECTS}/{project}/parcels/{parcel}/planning-controls",
            json={"far_ratio": "4.5000", "variance_required": False},
        )
        permit = admin_client.post(
            f"{PROJECTS}/{project}/permits", json=permit_payload(fee_amount=PERMIT_FEE)
        ).json()["id"]
        document = admin_client.post(
            f"{PROJECTS}/{project}/documents",
            json={
                "title": f"Deed {code}",
                "document_type_code": "TITLE_DEED",
                "external_url": "https://records.example.com/deed.pdf",
            },
        ).json()["id"]
        built[key] = {
            "project": project,
            "parcel": parcel,
            "permit": permit,
            "document": document,
        }
    return built


@pytest.fixture
def member_of_a(
    admin_client: TestClient, db: Session, two_projects: dict[str, dict[str, str]]
) -> TestClient:
    """A Project Manager on Project A and nothing else."""
    user = make_user(db, email="only-a@example.com", roles=("project_manager",))
    grant_access(admin_client, two_projects["a"]["project"], user)
    return client_for(user.email)


def test_project_b_is_entirely_invisible(
    member_of_a: TestClient, two_projects: dict[str, dict[str, str]]
) -> None:
    """Given membership of A only, then B leaks neither existence nor content."""
    b = two_projects["b"]

    listing = member_of_a.get(PROJECTS)
    detail = member_of_a.get(f"{PROJECTS}/{b['project']}")

    assert [item["code"] for item in listing.json()] == ["PROJECT-A"]
    assert detail.status_code == 404
    assert "PROJECT-B" not in listing.text
    assert "PROJECT-B" not in detail.text


@pytest.mark.parametrize(
    "template",
    [
        "{project}/parcels",
        "{project}/parcels/{parcel}",
        "{project}/parcels/{parcel}/planning-controls",
        "{project}/permits",
        "{project}/permits/{permit}",
        "{project}/permits/{permit}/status-history",
        "{project}/documents",
        "{project}/access",
    ],
)
def test_every_nested_route_of_an_inaccessible_project_is_not_found(
    member_of_a: TestClient, two_projects: dict[str, dict[str, str]], template: str
) -> None:
    """Given Project B's own paths, then each answers 404 and reveals nothing."""
    b = two_projects["b"]
    path = template.format(project=b["project"], parcel=b["parcel"], permit=b["permit"])

    response = member_of_a.get(f"{PROJECTS}/{path}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Project not found."}
    for figure in SECRET_FIGURES:
        assert figure not in response.text


@pytest.mark.parametrize(
    "template",
    [
        "{project_a}/parcels/{parcel_b}",
        "{project_a}/parcels/{parcel_b}/planning-controls",
        "{project_a}/permits/{permit_b}",
        "{project_a}/permits/{permit_b}/status-history",
        "{project_a}/documents/{document_b}",
    ],
)
def test_another_projects_child_id_cannot_be_smuggled_into_an_accessible_path(
    member_of_a: TestClient, two_projects: dict[str, dict[str, str]], template: str
) -> None:
    """Given a path the caller may use and a foreign child id, then it is not found.

    The substitution attack this module's project scoping exists to defeat:
    loading a child by primary key alone would answer it.
    """
    path = template.format(
        project_a=two_projects["a"]["project"],
        parcel_b=two_projects["b"]["parcel"],
        permit_b=two_projects["b"]["permit"],
        document_b=two_projects["b"]["document"],
    )

    response = member_of_a.get(f"{PROJECTS}/{path}")

    assert response.status_code == 404
    assert "PROJECT-B" not in response.text
    for figure in SECRET_FIGURES:
        assert figure not in response.text


def test_a_foreign_child_cannot_be_written_through_an_accessible_project(
    member_of_a: TestClient, two_projects: dict[str, dict[str, str]]
) -> None:
    """Given a write aimed at another project's child, then it is refused."""
    a, b = two_projects["a"], two_projects["b"]

    parcel = member_of_a.patch(
        f"{PROJECTS}/{a['project']}/parcels/{b['parcel']}", json={"seller": "Hijacked"}
    )
    planning = member_of_a.put(
        f"{PROJECTS}/{a['project']}/parcels/{b['parcel']}/planning-controls",
        json={"far_ratio": "9.0000", "variance_required": False},
    )
    transition = member_of_a.post(
        f"{PROJECTS}/{a['project']}/permits/{b['permit']}/transitions",
        json={"to_status": "preparing", "effective_date": "2026-02-01"},
    )

    assert parcel.status_code == 404
    assert planning.status_code == 404
    assert transition.status_code == 404


def test_a_guessed_identifier_reveals_nothing(
    member_of_a: TestClient, two_projects: dict[str, dict[str, str]]
) -> None:
    """Given a random UUID, then the answer matches the answer for a real one.

    A different status for "exists but forbidden" would turn identifier guessing
    into an inventory of what exists.
    """
    unknown = uuid.uuid4()

    guessed = member_of_a.get(f"{PROJECTS}/{unknown}")
    real_but_forbidden = member_of_a.get(f"{PROJECTS}/{two_projects['b']['project']}")

    assert guessed.status_code == real_but_forbidden.status_code == 404
    assert guessed.json() == real_but_forbidden.json()


def test_a_member_cannot_grant_themselves_access_to_another_project(
    member_of_a: TestClient, db: Session, two_projects: dict[str, dict[str, str]]
) -> None:
    """Given a project they cannot see, then self-granting is not even addressable."""
    user = db.query(User).filter(User.email == "only-a@example.com").one()

    response = member_of_a.put(f"{PROJECTS}/{two_projects['b']['project']}/access/{user.id}")

    assert response.status_code == 404


def test_a_member_cannot_administer_access_on_their_own_project(
    member_of_a: TestClient, db: Session, two_projects: dict[str, dict[str, str]]
) -> None:
    """Given membership without administration rights, then it is 403, not silent success."""
    user = db.query(User).filter(User.email == "only-a@example.com").one()

    response = member_of_a.put(f"{PROJECTS}/{two_projects['a']['project']}/access/{user.id}")

    assert response.status_code == 403


def test_an_unauthenticated_caller_reaches_nothing(two_projects: dict[str, dict[str, str]]) -> None:
    """Given no session, then the project namespace is closed."""
    from tests.factories import anonymous_client

    client = anonymous_client()
    a = two_projects["a"]

    assert client.get(PROJECTS).status_code == 401
    assert client.get(f"{PROJECTS}/{a['project']}").status_code == 401
    assert client.get(f"{PROJECTS}/{a['project']}/parcels").status_code == 401
