"""Shared arrangement for the project-domain tests.

Configuration (currency, country pack, reference values) is created through the
Settings API by an administrator, exactly as it would be in production: a
project cannot be created against configuration that does not exist, and these
tests should fail if that stops being true.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy.orm import Session

from app.modules.access.models import User
from tests.factories import client_for, make_user

SETTINGS = "/api/v1/settings"
PROJECTS = "/api/v1/projects"

#: Reference values every project-domain test can rely on existing.
REFERENCE_VALUES = (
    ("project_type", "RESIDENTIAL", "Residential"),
    ("ownership_type", "FREEHOLD", "Freehold"),
    ("title_status", "REGISTERED", "Registered"),
    ("zoning_class", "RES_B", "Residential B"),
    ("permit_type", "BUILDING", "Building permit"),
    ("permit_type", "PLANNING", "Planning approval"),
    ("document_type", "TITLE_DEED", "Title deed"),
)


@pytest.fixture
def admin(db: Session) -> User:
    return make_user(db, email="admin@example.com", roles=("system_admin",))


@pytest.fixture
def admin_client(admin: User) -> TestClient:
    return client_for(admin.email)


@pytest.fixture
def manager(db: Session) -> User:
    return make_user(db, email="pm@example.com", roles=("project_manager",))


@pytest.fixture
def manager_client(manager: User) -> TestClient:
    return client_for(manager.email)


@pytest.fixture
def engineer(db: Session) -> User:
    return make_user(db, email="design@example.com", roles=("design_engineering",))


@pytest.fixture
def advisor(db: Session) -> User:
    """A Sales Advisor: has a real role, but no business seeing development cost."""
    return make_user(db, email="advisor@example.com", roles=("sales_advisor",))


@pytest.fixture
def currency_id(admin_client: TestClient) -> str:
    response = admin_client.post(
        f"{SETTINGS}/currencies", json={"code": "JOD", "name": "Jordanian dinar"}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.fixture
def country_pack_id(admin_client: TestClient, currency_id: str) -> str:
    response = admin_client.post(
        f"{SETTINGS}/country-packs",
        json={
            "country_code": "JO",
            "name": "Jordan",
            "locale": "en-JO",
            "timezone": "Asia/Amman",
            "default_currency_id": currency_id,
            "area_unit": "sqm",
            "fiscal_year_start_month": 4,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.fixture
def reference_data(admin_client: TestClient, country_pack_id: str) -> None:
    """Seed the configured codes the project domain validates against."""
    for category, code, label in REFERENCE_VALUES:
        response = admin_client.post(
            f"{SETTINGS}/reference-values",
            json={
                "country_pack_id": country_pack_id,
                "category": category,
                "code": code,
                "label": label,
            },
        )
        assert response.status_code == 201, response.text


def project_payload(
    country_pack_id: str, currency_id: str, **overrides: object
) -> dict[str, object]:
    payload: dict[str, object] = {
        "code": "GALINI-BLU",
        "name": "Galini Blu",
        "developer_entity": "Reach Developments",
        "country_pack_id": country_pack_id,
        "base_currency_id": currency_id,
        "reporting_currency_id": currency_id,
        "city": "Amman",
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def project_id(
    admin_client: TestClient, country_pack_id: str, currency_id: str, reference_data: None
) -> str:
    response = admin_client.post(PROJECTS, json=project_payload(country_pack_id, currency_id))
    assert response.status_code == 201, response.text
    return response.json()["id"]


def parcel_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "plot_number": "PLOT-1",
        "land_area": "4500.0000",
        "ownership_type_code": "FREEHOLD",
        "title_status_code": "REGISTERED",
        "zoning_class_code": "RES_B",
    }
    payload.update(overrides)
    return payload


def permit_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "permit_code": "BLD-001",
        "permit_type_code": "BUILDING",
        "authority": "Greater Amman Municipality",
        "status_effective_date": "2026-01-01",
    }
    payload.update(overrides)
    return payload


def grant_access(admin_client: TestClient, project_id: str, user: User) -> None:
    response = admin_client.put(f"{PROJECTS}/{project_id}/access/{user.id}")
    assert response.status_code == 200, response.text


# --------------------------------------------------------------------------- #
# Inventory (PR-MVP-03)
# --------------------------------------------------------------------------- #

#: Reference values the inventory domain validates unit codes against, on top of
#: the ones PR-MVP-02's conftest already seeds.
INVENTORY_REFERENCE_VALUES = (
    ("unit_type", "2BR", "Two bedroom"),
    ("unit_type", "3BR", "Three bedroom"),
    ("floor_band", "MID", "Middle floors"),
    ("orientation", "NORTH", "North facing"),
    ("view_class", "SEA", "Sea view"),
    ("furnishing_specification", "STANDARD", "Standard finish"),
    ("accessibility", "STEP_FREE", "Step free"),
    ("garden_class", "PRIVATE", "Private garden"),
    ("sub_asset_subtype", "COVERED", "Covered bay"),
)


def inventory_url(project_id: str) -> str:
    return f"{PROJECTS}/{project_id}/inventory"


@pytest.fixture
def operational_project(admin_client: TestClient, project_id: str) -> str:
    """A project whose basis has been finalised, so inventory may begin.

    Inventory is refused while a project is still in ``setup``, because that is
    exactly the window in which its country pack can still be changed under the
    units already validated against it. The fixture does what an operator does:
    confirm the configuration, then leave setup.
    """
    response = admin_client.patch(f"{PROJECTS}/{project_id}", json={"status": "predevelopment"})
    assert response.status_code == 200, response.text
    return project_id


@pytest.fixture
def inventory_reference_data(
    admin_client: TestClient, country_pack_id: str, operational_project: str
) -> None:
    for category, code, label in INVENTORY_REFERENCE_VALUES:
        response = admin_client.post(
            f"{SETTINGS}/reference-values",
            json={
                "country_pack_id": country_pack_id,
                "category": category,
                "code": code,
                "label": label,
            },
        )
        assert response.status_code == 201, response.text


@pytest.fixture
def phase_id(admin_client: TestClient, project_id: str, inventory_reference_data: None) -> str:
    response = admin_client.post(
        f"{inventory_url(project_id)}/phases",
        json={"code": "PHASE-1", "name": "Phase 1", "sequence": 1},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.fixture
def building_id(admin_client: TestClient, project_id: str, phase_id: str) -> str:
    response = admin_client.post(
        f"{inventory_url(project_id)}/buildings",
        json={"phase_id": phase_id, "code": "B1", "name": "Building 1"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.fixture
def floor_id(admin_client: TestClient, project_id: str, building_id: str) -> str:
    response = admin_client.post(
        f"{inventory_url(project_id)}/floors",
        json={"building_id": building_id, "code": "01", "label": "First floor"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def unit_payload(floor_id: str, **overrides: object) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "floor_id": floor_id,
        "unit_number": "101",
        "unit_reference": "B1-101",
        "asset_class": "apartment",
        "unit_type_code": "2BR",
        "bedrooms": 2,
        "bathrooms": 2,
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def unit_id(admin_client: TestClient, project_id: str, floor_id: str) -> str:
    response = admin_client.post(f"{inventory_url(project_id)}/units", json=unit_payload(floor_id))
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.fixture
def area_types(
    admin_client: TestClient, project_id: str, operational_project: str
) -> dict[str, str]:
    """An internal area required for release, and a half-weighted balcony.

    Area types are a project's own inventory configuration, so like every other
    inventory fixture this one needs the project's basis settled first.
    """
    created: dict[str, str] = {}
    for code, label, role, factor, required in (
        ("INTERNAL", "Internal area", "internal", "1.000000", True),
        ("BALCONY", "Balcony", "outdoor", "0.500000", False),
    ):
        response = admin_client.post(
            f"{inventory_url(project_id)}/area-types",
            json={
                "code": code,
                "label": label,
                "area_role": role,
                "weight_factor": factor,
                "required_for_release": required,
            },
        )
        assert response.status_code == 201, response.text
        created[code] = response.json()["id"]
    return created


def approve_areas(
    client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    *,
    internal: str = "100.0000",
    balcony: str | None = "20.0000",
    revision: str = "R0",
) -> str:
    """Record and approve one measured revision, the way the UI would."""
    values = [{"area_type_id": area_types["INTERNAL"], "raw_area": internal}]
    if balcony is not None:
        values.append({"area_type_id": area_types["BALCONY"], "raw_area": balcony})
    created = client.post(
        f"{inventory_url(project_id)}/units/{unit_id}/area-schedules",
        json={"revision_code": revision, "reconciled": True, "values": values},
    )
    assert created.status_code == 201, created.text
    schedule_id = created.json()["id"]
    approved = client.post(
        f"{inventory_url(project_id)}/units/{unit_id}/area-schedules/{schedule_id}/approve"
    )
    assert approved.status_code == 200, approved.text
    return schedule_id


def make_releasable(
    client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    db: Session,
    *,
    release_date: str = "2026-01-01",
) -> None:
    """Satisfy every release gate, including the one no API may set.

    ``pricing_approved`` is written directly because PR-MVP-03 deliberately
    exposes no way to set it: PR-MVP-04 does that when a real approved price
    exists. A test of the final release formula still needs the flag, and using
    the database for it keeps the API honest.
    """
    from sqlalchemy import select

    from app.modules.inventory.models import Unit

    approve_areas(client, project_id, unit_id, area_types)
    response = client.patch(
        f"{inventory_url(project_id)}/units/{unit_id}/release-controls",
        json={
            "drawings_approved": True,
            "legal_sale_eligible": True,
            "release_date": release_date,
        },
    )
    assert response.status_code == 200, response.text
    unit = db.scalars(select(Unit).where(Unit.id == unit_id)).one()
    unit.pricing_approved = True
    db.commit()


@pytest.fixture
def engineer_member(db: Session, admin_client: TestClient, project_id: str) -> User:
    """A Design / Engineering user who is a member of the project."""
    user = make_user(db, email="design2@example.com", roles=("design_engineering",))
    response = admin_client.put(f"{PROJECTS}/{project_id}/access/{user.id}")
    assert response.status_code == 200, response.text
    return user


# --------------------------------------------------------------------------- #
# Pricing (PR-MVP-04)
# --------------------------------------------------------------------------- #


def pricing_url(project_id: str) -> str:
    return f"{PROJECTS}/{project_id}/pricing"


@pytest.fixture
def finance(db: Session) -> User:
    """Somebody who prepares pricing but may not sanction it."""
    return make_user(db, email="finance@example.com", roles=("finance",))


@pytest.fixture
def finance_client(admin_client: TestClient, project_id: str, finance: User) -> TestClient:
    """Finance, and a member of the project.

    A global role says what somebody may do inside a project; membership says
    which projects exist for them. Pricing needs both, so the fixture grants the
    membership rather than letting every pricing test discover the 404.
    """
    grant_access(admin_client, project_id, finance)
    return client_for(finance.email)


@pytest.fixture
def cfo(db: Session) -> User:
    """The second signature. Deliberately not an administrator."""
    return make_user(db, email="cfo@example.com", roles=("approver_cfo",))


@pytest.fixture
def cfo_client(admin_client: TestClient, project_id: str, cfo: User) -> TestClient:
    grant_access(admin_client, project_id, cfo)
    return client_for(cfo.email)


@pytest.fixture
def advisor_client(admin_client: TestClient, project_id: str, advisor: User) -> TestClient:
    grant_access(admin_client, project_id, advisor)
    return client_for(advisor.email)


@pytest.fixture
def sales_ops(db: Session) -> User:
    return make_user(db, email="salesops@example.com", roles=("sales_operations",))


def configuration_payload(currency_id: str, **overrides: object) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": "Launch pricing",
        "pricing_currency_id": currency_id,
        "base_internal_rate": "1500.00",
        "valid_from": "2026-01-01",
        "maximum_premium_fraction": "0.200000",
        "offer_valid_days": 14,
        "price_lock_days": 30,
        "reservation_expiry_days": 7,
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def draft_configuration(
    finance_client: TestClient,
    project_id: str,
    currency_id: str,
    area_types: dict[str, str],
) -> str:
    """A draft policy that prices internal area at 1,500 and balcony at half.

    Built through the API by Finance, exactly as an operator would: a
    configuration nobody could have created through the real routes is not a
    fixture worth testing against.
    """
    created = finance_client.post(
        f"{pricing_url(project_id)}/configurations", json=configuration_payload(currency_id)
    )
    assert created.status_code == 201, created.text
    configuration_id = created.json()["id"]
    for area_type_id, method, extra in (
        (area_types["INTERNAL"], "internal_base", {}),
        (area_types["BALCONY"], "factor_of_internal_rate", {"internal_rate_factor": "0.500000"}),
    ):
        rule = finance_client.post(
            f"{pricing_url(project_id)}/configurations/{configuration_id}/area-rules",
            json={"area_type_id": area_type_id, "pricing_method": method, **extra},
        )
        assert rule.status_code == 201, rule.text
    return configuration_id


@pytest.fixture
def active_configuration(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    draft_configuration: str,
) -> str:
    """The same policy, submitted by Finance and put live by the CFO."""
    base = f"{pricing_url(project_id)}/configurations/{draft_configuration}"
    submitted = finance_client.post(f"{base}/submit", json={"reason": "Launch pricing"})
    assert submitted.status_code == 200, submitted.text
    approved = cfo_client.post(f"{base}/approve", json={"reason": "Reviewed against feasibility"})
    assert approved.status_code == 200, approved.text
    activated = cfo_client.post(f"{base}/activate")
    assert activated.status_code == 200, activated.text
    return draft_configuration


@pytest.fixture
def priced_unit(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    active_configuration: str,
) -> str:
    """A unit with measured areas and a live list price.

    Runs the whole governed path — measure, approve, draft, submit, approve,
    activate — because a price that arrived any other way would not exercise the
    thing every later test depends on.
    """
    approve_areas(admin_client, project_id, unit_id, area_types)
    draft = finance_client.post(
        f"{pricing_url(project_id)}/units/{unit_id}/price-versions", json={}
    )
    assert draft.status_code == 201, draft.text
    version_id = draft.json()["id"]
    base = f"{pricing_url(project_id)}/price-versions/{version_id}"
    assert finance_client.post(f"{base}/submit", json={}).status_code == 200
    approved = cfo_client.post(f"{base}/approve", json={"reason": "Within feasibility"})
    assert approved.status_code == 200, approved.text
    activated = cfo_client.post(f"{base}/activate")
    assert activated.status_code == 200, activated.text
    return version_id


# --------------------------------------------------------------------------- #
# Sales and legal (PR-MVP-05)
# --------------------------------------------------------------------------- #

#: Codes the sales domain validates newly assigned values against.
SALES_REFERENCE_VALUES = (
    ("sales_channel", "DIRECT", "Direct"),
    ("sales_channel", "BROKER", "Broker"),
    ("sales_branch", "AMMAN", "Amman office"),
    ("client_language", "EN", "English"),
    ("nationality", "JO", "Jordanian"),
    ("residency", "JO", "Resident in Jordan"),
)


def sales_url(project_id: str) -> str:
    return f"{PROJECTS}/{project_id}/sales"


@pytest.fixture
def sales_reference_data(admin_client: TestClient, country_pack_id: str) -> None:
    for category, code, label in SALES_REFERENCE_VALUES:
        response = admin_client.post(
            f"{SETTINGS}/reference-values",
            json={
                "country_pack_id": country_pack_id,
                "category": category,
                "code": code,
                "label": label,
            },
        )
        assert response.status_code == 201, response.text


def add_sale_tax(
    admin_client: TestClient, country_pack_id: str, *, rate_fraction: str = "0.160000"
) -> str:
    """Configure one sale tax for the country, the way an administrator would."""
    response = admin_client.post(
        f"{SETTINGS}/country-packs/{country_pack_id}/tax-rules",
        json={
            "tax_code": "VAT",
            "label": "Value added tax",
            "applies_to": "sale",
            "calculation_basis": "net_amount",
            "rate_fraction": rate_fraction,
            "valid_from": "2026-01-01",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.fixture
def sales_ops_client(admin_client: TestClient, project_id: str, sales_ops: User) -> TestClient:
    grant_access(admin_client, project_id, sales_ops)
    return client_for(sales_ops.email)


@pytest.fixture
def legal_officer(db: Session) -> User:
    return make_user(db, email="legal@example.com", roles=("legal",))


@pytest.fixture
def legal_client(admin_client: TestClient, project_id: str, legal_officer: User) -> TestClient:
    grant_access(admin_client, project_id, legal_officer)
    return client_for(legal_officer.email)


@pytest.fixture
def collections_officer(db: Session) -> User:
    return make_user(db, email="collections@example.com", roles=("collections",))


@pytest.fixture
def collections_client(
    admin_client: TestClient, project_id: str, collections_officer: User
) -> TestClient:
    grant_access(admin_client, project_id, collections_officer)
    return client_for(collections_officer.email)


@pytest.fixture
def delivery_client(db: Session, admin_client: TestClient, project_id: str) -> TestClient:
    """Whoever answers for the building being ready — here, the Project Manager.

    Delivery clearance belongs to the people who built the thing, so it is a
    different signature from Sales Operations completing the handover.
    """
    user = make_user(db, email="delivery@example.com", roles=("project_manager",))
    grant_access(admin_client, project_id, user)
    return client_for(user.email)


@pytest.fixture
def released_unit(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    priced_unit: str,
) -> str:
    """A priced unit that has passed every release gate and is on the market.

    Runs the real route in each case: the release controls through inventory's
    own endpoint, then the commercial transition to ``available``. A unit that
    arrived at ``available`` by any other path would not prove the sales gates
    are standing on the release gates.
    """
    controls = admin_client.patch(
        f"{inventory_url(project_id)}/units/{unit_id}/release-controls",
        json={
            "drawings_approved": True,
            "legal_sale_eligible": True,
            "release_date": "2026-01-01",
        },
    )
    assert controls.status_code == 200, controls.text
    released = admin_client.post(
        f"{inventory_url(project_id)}/units/{unit_id}/commercial-transitions",
        json={"to_status": "available", "effective_date": "2026-01-02"},
    )
    assert released.status_code == 201, released.text
    return unit_id


@pytest.fixture
def buyer_id(
    sales_ops_client: TestClient,
    project_id: str,
    operational_project: str,
    sales_reference_data: None,
) -> str:
    """A buyer with one purchaser holding the whole unit."""
    created = sales_ops_client.post(
        f"{sales_url(project_id)}/clients",
        json={
            "display_name": "Rana Haddad",
            "email": "rana@example.com",
            "phone": "+962790000000",
            "preferred_language_code": "EN",
        },
    )
    assert created.status_code == 201, created.text
    client_id = created.json()["id"]
    party = sales_ops_client.post(
        f"{sales_url(project_id)}/clients/{client_id}/parties",
        json={
            "name_as_identification": "Rana Haddad",
            "share_fraction": "1.000000",
            "nationality_code": "JO",
            "residency_code": "JO",
            "identity_document_type": "passport",
            "identity_document_number": "P1234567",
            "is_primary": True,
        },
    )
    assert party.status_code == 201, party.text
    return client_id


@pytest.fixture
def reservation_id(
    sales_ops_client: TestClient, project_id: str, released_unit: str, buyer_id: str
) -> str:
    """A reservation in preparation, quoted from the unit's live price."""
    created = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations",
        json={
            "unit_id": released_unit,
            "client_id": buyer_id,
            "sales_channel_code": "DIRECT",
            "sales_branch_code": "AMMAN",
            "deposit_required_amount": "5000.00",
        },
    )
    assert created.status_code == 201, created.text
    return created.json()["reservation"]["id"]


@pytest.fixture
def active_reservation(sales_ops_client: TestClient, project_id: str, reservation_id: str) -> str:
    """The same reservation, deposit confirmed and the unit committed."""
    base = f"{sales_url(project_id)}/reservations/{reservation_id}"
    confirmed = sales_ops_client.post(
        f"{base}/confirm-deposit", json={"evidence_reference": "BANK-REF-1"}
    )
    assert confirmed.status_code == 200, confirmed.text
    activated = sales_ops_client.post(f"{base}/activate", json={})
    assert activated.status_code == 200, activated.text
    return reservation_id


@pytest.fixture
def sale_id(sales_ops_client: TestClient, project_id: str, active_reservation: str) -> str:
    """A contract drafted on the active reservation, at the price it froze."""
    created = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts",
        json={"reservation_id": active_reservation, "spa_number": "SPA-0001"},
    )
    assert created.status_code == 201, created.text
    return created.json()["sale"]["id"]


@pytest.fixture
def submitted_sale(sales_ops_client: TestClient, project_id: str, sale_id: str) -> str:
    """The contract put forward for signature: the unit is now contract pending."""
    submitted = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts/{sale_id}/submit", json={}
    )
    assert submitted.status_code == 200, submitted.text
    return sale_id


def record_legal(
    client: TestClient, project_id: str, sale_id: str, event_type: str, event_date: str
) -> None:
    """Put one milestone on a contract's legal timeline, the way Legal would."""
    response = client.post(
        f"{sales_url(project_id)}/contracts/{sale_id}/legal-events",
        json={"event_type": event_type, "event_date": event_date},
    )
    assert response.status_code == 201, response.text


@pytest.fixture
def active_sale(
    sales_ops_client: TestClient, legal_client: TestClient, project_id: str, submitted_sale: str
) -> str:
    """A live contract: both signatures recorded, the unit contracted."""
    for event_type, event_date in (
        ("spa_drafted", "2026-02-01"),
        ("spa_issued", "2026-02-02"),
        ("buyer_signed", "2026-02-03"),
        ("seller_signed", "2026-02-04"),
    ):
        record_legal(legal_client, project_id, submitted_sale, event_type, event_date)
    activated = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts/{submitted_sale}/activate", json={}
    )
    assert activated.status_code == 200, activated.text
    return submitted_sale


# --------------------------------------------------------------------------- #
# Payment plans (PR-MVP-06)
# --------------------------------------------------------------------------- #


def plans_url(project_id: str) -> str:
    return f"/api/v1/projects/{project_id}/payment-plans"


@pytest.fixture
def second_cfo(db: Session) -> User:
    """A second sanctioning officer, for the cases where the first is the maker."""
    return make_user(db, email="cfo2@example.com", roles=("approver_cfo",))


@pytest.fixture
def second_cfo_client(admin_client: TestClient, project_id: str, second_cfo: User) -> TestClient:
    grant_access(admin_client, project_id, second_cfo)
    return client_for(second_cfo.email)


@pytest.fixture
def plan_id(collections_client: TestClient, project_id: str, active_sale: str) -> str:
    """A payment plan opened on a live contract, with its first draft version."""
    created = collections_client.post(
        plans_url(project_id),
        json={"sale_contract_id": active_sale, "name": "Standard terms"},
    )
    assert created.status_code == 201, created.text
    return created.json()["plan"]["id"]


def plan_detail(client: TestClient, project_id: str, plan_id: str) -> dict[str, Any]:
    response = client.get(f"{plans_url(project_id)}/{plan_id}")
    assert response.status_code == 200, response.text
    return response.json()


def current_version_id(client: TestClient, project_id: str, plan_id: str) -> str:
    return plan_detail(client, project_id, plan_id)["current"]["version"]["id"]


def contract_basis(client: TestClient, project_id: str, plan_id: str) -> dict[str, str]:
    """The frozen sale figures the schedule has to reconcile against."""
    version = plan_detail(client, project_id, plan_id)["current"]["version"]
    return {
        "principal": version["contract_value_covered"],
        "tax": version["tax_total_snapshot"],
        "fee": version["buyer_fee_total_snapshot"],
        "payable": version["total_buyer_payable_snapshot"],
    }


def write_schedule(
    client: TestClient,
    project_id: str,
    plan_id: str,
    version_id: str,
    installments: list[dict[str, Any]],
    *,
    allocation_mode: str = "percentage",
    charge_allocation_mode: str = "pro_rata",
) -> Response:
    """Replace a draft version's whole schedule."""
    return client.put(
        f"{plans_url(project_id)}/{plan_id}/versions/{version_id}/installments",
        json={
            "allocation_mode": allocation_mode,
            "charge_allocation_mode": charge_allocation_mode,
            "installments": installments,
        },
    )


def fixed_row(sequence: int, fraction: str, due: str, **overrides: object) -> dict[str, Any]:
    """One instalment falling due on a contractual date."""
    row: dict[str, Any] = {
        "sequence": sequence,
        "label": f"Instalment {sequence}",
        "trigger_type": "fixed_date",
        "contractual_due_date": due,
        "principal_fraction": fraction,
    }
    row.update(overrides)
    return row


@pytest.fixture
def reconciled_plan(
    collections_client: TestClient, project_id: str, plan_id: str
) -> tuple[str, str]:
    """A plan whose draft schedule reconciles exactly: 20 / 30 / 50."""
    version_id = current_version_id(collections_client, project_id, plan_id)
    response = write_schedule(
        collections_client,
        project_id,
        plan_id,
        version_id,
        [
            fixed_row(1, "0.200000", "2026-03-01"),
            fixed_row(2, "0.300000", "2026-06-01"),
            fixed_row(3, "0.500000", "2026-09-01"),
        ],
    )
    assert response.status_code == 200, response.text
    assert response.json()["reconciliation"]["is_reconciled"] is True
    return plan_id, version_id


@pytest.fixture
def approved_plan(
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    reconciled_plan: tuple[str, str],
) -> tuple[str, str]:
    """A schedule put forward by Collections and sanctioned by the CFO."""
    plan_id, version_id = reconciled_plan
    base = f"{plans_url(project_id)}/{plan_id}/versions/{version_id}"
    submitted = collections_client.post(f"{base}/submit", json={})
    assert submitted.status_code == 200, submitted.text
    approved = cfo_client.post(f"{base}/approve", json={"reason": "Terms reviewed"})
    assert approved.status_code == 200, approved.text
    return plan_id, version_id


@pytest.fixture
def active_plan(
    cfo_client: TestClient, project_id: str, approved_plan: tuple[str, str]
) -> tuple[str, str]:
    """The schedule governing the sale."""
    plan_id, version_id = approved_plan
    activated = cfo_client.post(
        f"{plans_url(project_id)}/{plan_id}/versions/{version_id}/activate", json={}
    )
    assert activated.status_code == 200, activated.text
    return plan_id, version_id


# --------------------------------------------------------------------------- #
# A second plan, in a phase of its own
# --------------------------------------------------------------------------- #


@pytest.fixture
def other_phase_plan(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    sales_ops_client: TestClient,
    legal_client: TestClient,
    collections_client: TestClient,
    project_id: str,
    area_types: dict[str, str],
    active_configuration: str,
    sales_reference_data: None,
) -> dict[str, str]:
    """A whole second sale and active plan, in a second phase.

    Built through the real routes rather than inserted, because the point of it
    is to be a genuinely separate branch of the hierarchy: its own phase, unit,
    buyer, contract and schedule. That is what makes it usable both as the
    "other plan" whose identifiers must not be accepted under the first plan's
    path, and as the plan a phase-scoped caller must not be able to reach.

    Its schedule carries a manual instalment with an attestation already
    submitted, so every nested identifier a caller might try to substitute —
    version, instalment, trigger event — actually exists.
    """
    phase = admin_client.post(
        f"{inventory_url(project_id)}/phases",
        json={"code": "PHASE-2", "name": "Phase 2", "sequence": 2},
    )
    assert phase.status_code == 201, phase.text
    phase_id = phase.json()["id"]
    building = admin_client.post(
        f"{inventory_url(project_id)}/buildings",
        json={"phase_id": phase_id, "code": "B2", "name": "Building 2"},
    )
    assert building.status_code == 201, building.text
    floor = admin_client.post(
        f"{inventory_url(project_id)}/floors",
        json={"building_id": building.json()["id"], "code": "02", "label": "Second floor"},
    )
    assert floor.status_code == 201, floor.text
    unit = admin_client.post(
        f"{inventory_url(project_id)}/units",
        json=unit_payload(floor.json()["id"], unit_number="201", unit_reference="B2-201"),
    )
    assert unit.status_code == 201, unit.text
    unit_id = unit.json()["id"]

    approve_areas(admin_client, project_id, unit_id, area_types)
    draft = finance_client.post(
        f"{pricing_url(project_id)}/units/{unit_id}/price-versions", json={}
    )
    assert draft.status_code == 201, draft.text
    price_base = f"{pricing_url(project_id)}/price-versions/{draft.json()['id']}"
    assert finance_client.post(f"{price_base}/submit", json={}).status_code == 200
    assert (
        cfo_client.post(f"{price_base}/approve", json={"reason": "Within feasibility"}).status_code
        == 200
    )
    assert cfo_client.post(f"{price_base}/activate").status_code == 200

    controls = admin_client.patch(
        f"{inventory_url(project_id)}/units/{unit_id}/release-controls",
        json={
            "drawings_approved": True,
            "legal_sale_eligible": True,
            "release_date": "2026-01-01",
        },
    )
    assert controls.status_code == 200, controls.text
    released = admin_client.post(
        f"{inventory_url(project_id)}/units/{unit_id}/commercial-transitions",
        json={"to_status": "available", "effective_date": "2026-01-02"},
    )
    assert released.status_code == 201, released.text

    buyer = sales_ops_client.post(
        f"{sales_url(project_id)}/clients",
        json={
            "display_name": "Samer Nasser",
            "email": "samer@example.com",
            "phone": "+962790000001",
            "preferred_language_code": "EN",
        },
    )
    assert buyer.status_code == 201, buyer.text
    buyer_id = buyer.json()["id"]
    party = sales_ops_client.post(
        f"{sales_url(project_id)}/clients/{buyer_id}/parties",
        json={
            "name_as_identification": "Samer Nasser",
            "share_fraction": "1.000000",
            "nationality_code": "JO",
            "residency_code": "JO",
            "identity_document_type": "passport",
            "identity_document_number": "P7654321",
            "is_primary": True,
        },
    )
    assert party.status_code == 201, party.text

    reservation = sales_ops_client.post(
        f"{sales_url(project_id)}/reservations",
        json={
            "unit_id": unit_id,
            "client_id": buyer_id,
            "sales_channel_code": "DIRECT",
            "sales_branch_code": "AMMAN",
            "deposit_required_amount": "5000.00",
        },
    )
    assert reservation.status_code == 201, reservation.text
    reservation_id = reservation.json()["reservation"]["id"]
    reservation_base = f"{sales_url(project_id)}/reservations/{reservation_id}"
    assert (
        sales_ops_client.post(
            f"{reservation_base}/confirm-deposit", json={"evidence_reference": "BANK-REF-2"}
        ).status_code
        == 200
    )
    assert sales_ops_client.post(f"{reservation_base}/activate", json={}).status_code == 200

    contract = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts",
        json={"reservation_id": reservation_id, "spa_number": "SPA-0002"},
    )
    assert contract.status_code == 201, contract.text
    sale_id = contract.json()["sale"]["id"]
    assert (
        sales_ops_client.post(
            f"{sales_url(project_id)}/contracts/{sale_id}/submit", json={}
        ).status_code
        == 200
    )
    for event_type, event_date in (
        ("spa_drafted", "2026-02-01"),
        ("spa_issued", "2026-02-02"),
        ("buyer_signed", "2026-02-03"),
        ("seller_signed", "2026-02-04"),
    ):
        record_legal(legal_client, project_id, sale_id, event_type, event_date)
    assert (
        sales_ops_client.post(
            f"{sales_url(project_id)}/contracts/{sale_id}/activate", json={}
        ).status_code
        == 200
    )

    created = collections_client.post(
        plans_url(project_id),
        json={"sale_contract_id": sale_id, "name": "Phase 2 terms"},
    )
    assert created.status_code == 201, created.text
    plan_id = created.json()["plan"]["id"]
    version_id = current_version_id(collections_client, project_id, plan_id)
    schedule = write_schedule(
        collections_client,
        project_id,
        plan_id,
        version_id,
        [
            fixed_row(1, "0.600000", "2026-03-01"),
            {
                "sequence": 2,
                "label": "On lender drawdown",
                "trigger_type": "manual_approved_event",
                "trigger_reference": "Lender releases funds",
                "principal_fraction": "0.400000",
            },
        ],
    )
    assert schedule.status_code == 200, schedule.text
    version_base = f"{plans_url(project_id)}/{plan_id}/versions/{version_id}"
    assert collections_client.post(f"{version_base}/submit", json={}).status_code == 200
    assert cfo_client.post(f"{version_base}/approve", json={"reason": "Agreed"}).status_code == 200
    assert cfo_client.post(f"{version_base}/activate", json={}).status_code == 200

    rows = plan_detail(collections_client, project_id, plan_id)["current"]["installments"]
    by_sequence = {row["sequence"]: row for row in rows}
    attested = collections_client.post(
        f"{plans_url(project_id)}/{plan_id}/installments/{by_sequence[2]['id']}/manual-trigger",
        json={
            "event_date": "2026-02-20",
            "evidence_reference": "PHASE2-LENDER-9",
            "reason": "Drawdown confirmed by the lender",
        },
    )
    assert attested.status_code == 201, attested.text

    return {
        "phase_id": phase_id,
        "unit_id": unit_id,
        "sale_id": sale_id,
        "plan_id": plan_id,
        "version_id": version_id,
        "dated_installment_id": by_sequence[1]["id"],
        "manual_installment_id": by_sequence[2]["id"],
        "event_id": attested.json()["id"],
    }


# --------------------------------------------------------------------------- #
# Collections (PR-MVP-07)
# --------------------------------------------------------------------------- #


def collections_url(project_id: str) -> str:
    return f"/api/v1/projects/{project_id}/collections"


@pytest.fixture
def second_collections_officer(db: Session) -> User:
    """A second collections officer, for the cases where the first is the maker."""
    return make_user(db, email="collections2@example.com", roles=("collections",))


@pytest.fixture
def second_collections_client(
    admin_client: TestClient, project_id: str, second_collections_officer: User
) -> TestClient:
    grant_access(admin_client, project_id, second_collections_officer)
    return client_for(second_collections_officer.email)


@pytest.fixture
def collections_and_finance(db: Session) -> User:
    """One person holding both roles.

    The point of this fixture is that holding both must not make somebody a
    complete maker/checker pair on their own: the separation is enforced by
    user identifier, not by role, so this user can record a receipt or confirm
    somebody else's but never both halves of the same one.
    """
    return make_user(db, email="both@example.com", roles=("collections", "finance"))


@pytest.fixture
def both_roles_client(
    admin_client: TestClient, project_id: str, collections_and_finance: User
) -> TestClient:
    grant_access(admin_client, project_id, collections_and_finance)
    return client_for(collections_and_finance.email)


@pytest.fixture
def second_finance(db: Session) -> User:
    return make_user(db, email="finance2@example.com", roles=("finance",))


@pytest.fixture
def second_finance_client(
    admin_client: TestClient, project_id: str, second_finance: User
) -> TestClient:
    grant_access(admin_client, project_id, second_finance)
    return client_for(second_finance.email)


def collection_account(
    client: TestClient, project_id: str, sale_id: str, **params: object
) -> dict[str, Any]:
    """One sale's collections account, as the API reports it."""
    response = client.get(f"{collections_url(project_id)}/sales/{sale_id}", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def governing_installments(
    client: TestClient, project_id: str, sale_id: str
) -> list[dict[str, Any]]:
    """The instalments of the schedule currently governing the sale."""
    return collection_account(client, project_id, sale_id)["installments"]


def record_receipt(
    client: TestClient,
    project_id: str,
    sale_id: str,
    amount: str,
    receipt_date: str = "2026-01-15",
    **overrides: object,
) -> Response:
    body: dict[str, Any] = {"amount": amount, "receipt_date": receipt_date}
    body.update(overrides)
    return client.post(f"{collections_url(project_id)}/sales/{sale_id}/receipts", json=body)


def confirm_receipt(client: TestClient, project_id: str, receipt_id: str) -> Response:
    return client.post(f"{collections_url(project_id)}/receipts/{receipt_id}/confirm", json={})


def allocate(
    client: TestClient,
    project_id: str,
    receipt_id: str,
    installment_id: str,
    amount: str,
) -> Response:
    return client.post(
        f"{collections_url(project_id)}/receipts/{receipt_id}/allocations",
        json={"installment_id": installment_id, "amount": amount},
    )


@pytest.fixture
def collecting_sale(
    collections_client: TestClient,
    project_id: str,
    active_sale: str,
    active_plan: tuple[str, str],
) -> str:
    """A live contract with a governing schedule, ready to receive cash.

    The schedule is the 20 / 30 / 50 one from ``reconciled_plan``, activated.
    Every collections test that needs a receivable starts here.
    """
    del collections_client, active_plan
    return active_sale


@pytest.fixture
def recorded_receipt(collections_client: TestClient, project_id: str, collecting_sale: str) -> str:
    """Cash claimed but not yet accepted by Finance. Counts as nothing."""
    response = record_receipt(collections_client, project_id, collecting_sale, "10000.00")
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.fixture
def confirmed_receipt(finance_client: TestClient, project_id: str, recorded_receipt: str) -> str:
    """Cash Finance has accepted. This is the first real money in the system."""
    response = confirm_receipt(finance_client, project_id, recorded_receipt)
    assert response.status_code == 200, response.text
    return recorded_receipt


def settle_and_clear_collections(
    collections_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    sale_id: str,
) -> None:
    """Pay a sale off in full and sign off its collection clearance.

    From PR-MVP-07 the collection clearance is no longer an attestation: it is
    checked against the receivables ledger, so a handover test that needs the
    gate open has to give the ledger something to be clear about. This is the
    shortest honest way to do that — a receipt per instalment, confirmed and
    applied exactly, leaving nothing outstanding and nothing unapplied.
    """
    rows = governing_installments(collections_client, project_id, sale_id)
    assert rows, "the sale needs an active payment schedule before it can be cleared"
    for row in rows:
        if row["outstanding"] == "0.00":
            continue
        recorded = record_receipt(collections_client, project_id, sale_id, row["outstanding"])
        assert recorded.status_code == 201, recorded.text
        receipt_id = recorded.json()["id"]
        assert confirm_receipt(finance_client, project_id, receipt_id).status_code == 200
        applied = allocate(
            collections_client, project_id, receipt_id, row["installment_id"], row["outstanding"]
        )
        assert applied.status_code == 201, applied.text

    granted = collections_client.post(
        f"{collections_url(project_id)}/sales/{sale_id}/collection-clearance",
        json={"evidence_reference": "LEDGER-CLEAR"},
    )
    assert granted.status_code == 200, granted.text
