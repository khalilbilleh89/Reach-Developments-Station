"""Shared arrangement for the project-domain tests.

Configuration (currency, country pack, reference values) is created through the
Settings API by an administrator, exactly as it would be in production: a
project cannot be created against configuration that does not exist, and these
tests should fail if that stops being true.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import text
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


# --------------------------------------------------------------------------- #
# Giving a test a past to read
# --------------------------------------------------------------------------- #

#: The tables whose lifecycle timestamps a test may move. Named explicitly
#: rather than accepting any string, because the point of the helper is to
#: simulate elapsed time on append-only rows, not to be a general back door
#: into the schema.
_HISTORICAL_TABLES = frozenset(
    {
        "payment_plan_versions",
        "collection_receipts",
        "collection_receipt_allocations",
        "collection_disputes",
        "collection_waivers",
        # A certificate's formal certification is what a forecast's cutoff is
        # measured against, and a valuation signed off days after its document
        # date is the ordinary case rather than the exception. There is no API
        # that can produce that gap — certifying stamps ``now`` — so the gap is
        # arranged here and every assertion afterwards goes through the ordinary
        # route. What is simulated is the passage of time, never a figure.
        "construction_certificates",
        # Cashflow's own movements confirm at ``now`` like every other cash
        # record in the platform, so a test that needs one to have been standing
        # last week has to move the timestamp. What is simulated is the passage
        # of time, never a figure.
        "cashflow_development_movements",
        "cashflow_financing_movements",
        # An escrow is standing at a cutoff only if it and the transfer behind it
        # were both standing then, and proving that needs a restriction whose
        # confirmation predates a later reversal of its receipt.
        "cashflow_receipt_restrictions",
        "cashflow_restriction_releases",
    }
)


def at(day: str | date, hour: int = 12) -> datetime:
    """Midday UTC on a given day, for stamping a lifecycle column."""
    when = date.fromisoformat(day) if isinstance(day, str) else day
    return datetime.combine(when, time(hour=hour), tzinfo=UTC)


def backdate(db: Session, *, table: str, row_id: str, **stamps: datetime | None) -> None:
    """Move one row's lifecycle timestamps, so the test has a history to read.

    Collections derives every historical figure from when things actually
    happened — a plan activated, a receipt confirmed, an allocation superseded.
    A test that wants to ask "what did March look like?" therefore needs rows
    that were stamped in March, and no amount of driving the API can produce
    them: activation stamps ``now`` and refuses a receipt dated in the future.

    So the arrangement is done here, against the same PostgreSQL the code
    reads, and every assertion afterwards goes through the ordinary route. What
    is simulated is the passage of time, never a figure.
    """
    assert table in _HISTORICAL_TABLES, f"{table} is not a lifecycle table"
    assert stamps, "backdate needs at least one timestamp; an empty SET is invalid SQL"
    assignments = ", ".join(f"{column} = :{column}" for column in stamps)
    db.execute(
        text(f"UPDATE {table} SET {assignments} WHERE id = :row_id"),
        {**stamps, "row_id": row_id},
    )
    db.commit()


@pytest.fixture
def historical_schedule(
    collections_client: TestClient,
    db: Session,
    project_id: str,
    collecting_sale: str,
    plan_id: str,
) -> str:
    """The fixture schedule, as though it had been activated on 5 January 2026.

    The 20 / 30 / 50 schedule falls due on 1 March, 1 June and 1 September, so
    every test that wants to age it on a named date needs it to have been
    governing the sale on that date. It really was activated today, and
    Collections reconstructs the governing version from when it was activated,
    so without this the honest answer to "what did March look like?" is "this
    sale had no schedule then".
    """
    del collecting_sale
    version_id = current_version_id(collections_client, project_id, plan_id)
    backdate(db, table="payment_plan_versions", row_id=version_id, activated_at=at("2026-01-05"))
    return version_id


@pytest.fixture
def relative_plan(
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    plan_id: str,
) -> dict[str, Any]:
    """A governing schedule anchored to today rather than to a fixed calendar.

    Three instalments, one of each shape the "due now" rule has to separate:
    one long past its date, one whose date has passed but is still inside its
    grace period, and one falling due three months from now. The dates move
    with the clock, so the assertions below stay true whenever the suite runs —
    a fixture pinned to named dates would quietly change meaning as those dates
    slid into the past.
    """
    version_id = current_version_id(collections_client, project_id, plan_id)
    today = date.today()
    response = write_schedule(
        collections_client,
        project_id,
        plan_id,
        version_id,
        [
            fixed_row(1, "0.200000", (today - timedelta(days=120)).isoformat()),
            fixed_row(2, "0.300000", (today - timedelta(days=3)).isoformat(), grace_days=10),
            fixed_row(3, "0.500000", (today + timedelta(days=90)).isoformat()),
        ],
    )
    assert response.status_code == 200, response.text
    base = f"{plans_url(project_id)}/{plan_id}/versions/{version_id}"
    assert collections_client.post(f"{base}/submit", json={}).status_code == 200
    assert cfo_client.post(f"{base}/approve", json={"reason": "Terms agreed"}).status_code == 200
    assert cfo_client.post(f"{base}/activate", json={}).status_code == 200
    return {"plan_id": plan_id, "version_id": version_id}


# --------------------------------------------------------------------------- #
# Unit economics (PR-MVP-08)
# --------------------------------------------------------------------------- #


def economics_url(project_id: str) -> str:
    return f"{PROJECTS}/{project_id}/unit-economics"


@pytest.fixture
def executive(db: Session) -> User:
    """A reader entitled to margin but to nothing that writes it."""
    return make_user(db, email="exec@example.com", roles=("executive_viewer",))


@pytest.fixture
def executive_client(admin_client: TestClient, project_id: str, executive: User) -> TestClient:
    grant_access(admin_client, project_id, executive)
    return client_for(executive.email)


@pytest.fixture
def auditor(db: Session) -> User:
    return make_user(db, email="auditor@example.com", roles=("auditor",))


@pytest.fixture
def auditor_client(admin_client: TestClient, project_id: str, auditor: User) -> TestClient:
    grant_access(admin_client, project_id, auditor)
    return client_for(auditor.email)


@pytest.fixture
def land_cost(admin_client: TestClient, project_id: str) -> str:
    """A parcel bought for 800,000 with 40,000 of acquisition fees.

    The land register is the only source a land cost pool may be derived from,
    so the economics tests buy real land through the real route rather than
    typing a total into a pool.
    """
    response = admin_client.post(
        f"{PROJECTS}/{project_id}/parcels",
        json=parcel_payload(
            acquisition_date="2026-01-05",
            purchase_price="800000.00",
            acquisition_fees="40000.00",
        ),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.fixture
def second_unit(admin_client: TestClient, project_id: str, floor_id: str) -> str:
    """A second unit on the same floor, so a pool has something to divide."""
    response = admin_client.post(
        f"{inventory_url(project_id)}/units",
        json=unit_payload(floor_id, unit_number="102", unit_reference="B1-102", sequence=2),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.fixture
def priced_pair(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
    second_unit: str,
    area_types: dict[str, str],
    priced_unit: str,
) -> tuple[str, str]:
    """Two measured, priced units. The smallest population an allocation needs.

    The first comes from ``priced_unit`` so the whole governed pricing path is
    exercised once; the second follows the same path with a smaller internal
    area, which is what makes a weighted-area division produce two different
    numbers instead of two identical halves.
    """
    del priced_unit
    approve_areas(
        admin_client,
        project_id,
        second_unit,
        area_types,
        internal="60.0000",
        balcony="8.0000",
    )
    draft = finance_client.post(
        f"{pricing_url(project_id)}/units/{second_unit}/price-versions", json={}
    )
    assert draft.status_code == 201, draft.text
    version_id = draft.json()["id"]
    base = f"{pricing_url(project_id)}/price-versions/{version_id}"
    assert finance_client.post(f"{base}/submit", json={}).status_code == 200
    assert (
        cfo_client.post(f"{base}/approve", json={"reason": "Within feasibility"}).status_code == 200
    )
    assert cfo_client.post(f"{base}/activate").status_code == 200
    return unit_id, second_unit


def today() -> str:
    """The only date a replacement cost basis may take effect on.

    A project's *first* basis may be back-dated — PR-MVP-08 arrives after sales
    exist and those contracts need a baseline. Every later one takes effect
    today, because a replacement dated in the past would restate a period units
    were already signed under. Tests that create a second version therefore have
    to use the real current date, not a fixed one.
    """
    return date.today().isoformat()


def create_version(
    client: TestClient,
    project_id: str,
    *,
    effective_from: str = "2026-01-01",
    reason: str = "Opening cost basis",
    finance_treatment: str = "excluded",
) -> str:
    response = client.post(
        f"{economics_url(project_id)}/allocation-versions",
        json={
            "effective_from": effective_from,
            "change_reason": reason,
            "finance_treatment": finance_treatment,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def add_pool(
    client: TestClient,
    project_id: str,
    version_id: str,
    *,
    pool_number: str,
    category: str,
    allocation_method: str = "unit_count",
    amount: str | None = "0.00",
    source_kind: str = "manual",
    **overrides: object,
) -> Response:
    body: dict[str, Any] = {
        "pool_number": pool_number,
        "name": f"{category.title()} pool {pool_number}",
        "category": category,
        "source_kind": source_kind,
        "allocation_method": allocation_method,
    }
    if amount is not None:
        body["amount"] = amount
    body.update(overrides)
    return client.post(
        f"{economics_url(project_id)}/allocation-versions/{version_id}/pools", json=body
    )


def cover_required_pools(
    client: TestClient,
    project_id: str,
    version_id: str,
    *,
    hard: str = "0.00",
    soft: str = "0.00",
) -> None:
    """Give a version the land, hard and soft pools submission insists on.

    Zero is allowed and explicit; omission is not. A basis that simply left soft
    cost out would report a margin that silently assumed there was none.

    The land pool is never given an amount: land cost is whatever the project's
    land register says, which is zero on a project that has bought none. A test
    that wants a real land cost buys a parcel through the ``land_cost`` fixture,
    because there is no other way to put one here.
    """
    land = add_pool(
        client,
        project_id,
        version_id,
        pool_number="LAND-01",
        category="land",
        source_kind="project_land",
        amount=None,
    )
    assert land.status_code == 201, land.text
    for number, category, amount in (("HARD-01", "hard", hard), ("SOFT-01", "soft", soft)):
        response = add_pool(
            client,
            project_id,
            version_id,
            pool_number=number,
            category=category,
            amount=amount,
        )
        assert response.status_code == 201, response.text


def govern(
    finance: TestClient,
    checker: TestClient,
    project_id: str,
    version_id: str,
) -> Response:
    """Calculate, submit, approve and activate one cost basis."""
    base = f"{economics_url(project_id)}/allocation-versions/{version_id}"
    assert finance.post(f"{base}/calculate", json={}).status_code == 200
    submitted = finance.post(f"{base}/submit", json={})
    assert submitted.status_code == 200, submitted.text
    approved = checker.post(f"{base}/approve", json={"reason": "Reviewed against feasibility"})
    assert approved.status_code == 200, approved.text
    return finance.post(f"{base}/activate", json={})


def unit_economics(client: TestClient, project_id: str, unit_id: str) -> dict[str, Any]:
    response = client.get(f"{economics_url(project_id)}/units/{unit_id}")
    assert response.status_code == 200, response.text
    return response.json()["economics"]


# --------------------------------------------------------------------------- #
# Construction (PR-MVP-09)
# --------------------------------------------------------------------------- #


def construction_url(project_id: str) -> str:
    return f"{PROJECTS}/{project_id}/construction"


@pytest.fixture
def engineer_client(admin_client: TestClient, project_id: str, engineer_member: User) -> TestClient:
    """Design / Engineering, and a member of the project."""
    return client_for(engineer_member.email)


def create_cost_code(
    client: TestClient,
    project_id: str,
    *,
    code: str,
    cost_category: str = "hard",
    name: str | None = None,
    **overrides: object,
) -> Response:
    body: dict[str, Any] = {
        "code": code,
        "name": name or f"{code} works",
        "cost_category": cost_category,
    }
    body.update(overrides)
    return client.post(f"{construction_url(project_id)}/cost-codes", json=body)


@pytest.fixture
def cost_codes(finance_client: TestClient, project_id: str) -> dict[str, str]:
    """One cost code per category, keyed by category.

    Every governed surface in this module is addressed by cost code, so a test
    that wants to prove a rule about hard cost should not have to build a
    breakdown first.
    """
    codes: dict[str, str] = {}
    for category, code in (
        ("hard", "HRD-01"),
        ("soft", "SFT-01"),
        ("contingency", "CNT-01"),
        ("other", "OTH-01"),
    ):
        response = create_cost_code(finance_client, project_id, code=code, cost_category=category)
        assert response.status_code == 201, response.text
        codes[category] = response.json()["id"]
    return codes


def create_budget(
    client: TestClient,
    project_id: str,
    *,
    effective_date: str = "2026-01-01",
    change_reason: str = "Opening authorisation",
    **overrides: object,
) -> Response:
    body: dict[str, Any] = {
        "effective_date": effective_date,
        "change_reason": change_reason,
    }
    body.update(overrides)
    return client.post(f"{construction_url(project_id)}/budgets", json=body)


def set_budget_line(
    client: TestClient,
    project_id: str,
    version_id: str,
    *,
    cost_code_id: str,
    approved_budget_amount: str,
    **overrides: object,
) -> Response:
    body: dict[str, Any] = {
        "cost_code_id": cost_code_id,
        "approved_budget_amount": approved_budget_amount,
    }
    body.update(overrides)
    return client.put(f"{construction_url(project_id)}/budgets/{version_id}/lines", json=body)


def cover_budget(
    client: TestClient,
    project_id: str,
    version_id: str,
    cost_codes: dict[str, str],
    *,
    hard: str = "10000000.00",
    soft: str = "0.00",
    contingency: str = "0.00",
    other: str = "0.00",
) -> None:
    """Authorise every active cost code, which is what submission insists on.

    An explicit zero is an answer; an omission is not. A budget that simply left
    a cost code out would let a contract be signed against an authorisation
    nobody made.
    """
    for category, amount in (
        ("hard", hard),
        ("soft", soft),
        ("contingency", contingency),
        ("other", other),
    ):
        response = set_budget_line(
            client,
            project_id,
            version_id,
            cost_code_id=cost_codes[category],
            approved_budget_amount=amount,
        )
        assert response.status_code == 200, response.text


def govern_budget(
    preparer: TestClient,
    approver: TestClient,
    project_id: str,
    version_id: str,
    *,
    activator: TestClient | None = None,
) -> Response:
    """Submit, approve and activate one budget version."""
    base = f"{construction_url(project_id)}/budgets/{version_id}"
    submitted = preparer.post(f"{base}/submit", json={})
    assert submitted.status_code == 200, submitted.text
    approved = approver.post(f"{base}/approve", json={"reason": "Authorised against feasibility"})
    assert approved.status_code == 200, approved.text
    return (activator or preparer).post(f"{base}/activate", json={})


@pytest.fixture
def active_budget(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    cost_codes: dict[str, str],
) -> str:
    """A budget in force, with headroom on every category."""
    created = create_budget(finance_client, project_id)
    assert created.status_code == 201, created.text
    version_id = created.json()["id"]
    cover_budget(
        finance_client,
        project_id,
        version_id,
        cost_codes,
        hard="10000000.00",
        soft="1000000.00",
        contingency="500000.00",
        other="250000.00",
    )
    activated = govern_budget(finance_client, cfo_client, project_id, version_id)
    assert activated.status_code == 200, activated.text
    return version_id


def create_contract(
    client: TestClient,
    project_id: str,
    currency_id: str,
    *,
    contract_number: str = "CT-001",
    vendor_name: str = "Meridian Construction LLC",
    original_contract_value_ex_tax: str = "1000000.00",
    contract_type: str = "works",
    **overrides: object,
) -> Response:
    body: dict[str, Any] = {
        "contract_number": contract_number,
        "contract_type": contract_type,
        "vendor_name": vendor_name,
        "original_contract_value_ex_tax": original_contract_value_ex_tax,
        "currency_id": currency_id,
    }
    body.update(overrides)
    return client.post(f"{construction_url(project_id)}/contracts", json=body)


def set_contract_line(
    client: TestClient,
    project_id: str,
    contract_id: str,
    *,
    sequence: int,
    cost_code_id: str,
    original_amount_ex_tax: str,
    description: str = "Works",
    **overrides: object,
) -> Response:
    body: dict[str, Any] = {
        "sequence": sequence,
        "description": description,
        "cost_code_id": cost_code_id,
        "original_amount_ex_tax": original_amount_ex_tax,
    }
    body.update(overrides)
    return client.put(f"{construction_url(project_id)}/contracts/{contract_id}/lines", json=body)


def govern_contract(
    preparer: TestClient,
    approver: TestClient,
    project_id: str,
    contract_id: str,
) -> Response:
    """Submit and activate one contract, by two different people."""
    base = f"{construction_url(project_id)}/contracts/{contract_id}"
    submitted = preparer.post(f"{base}/submit", json={})
    assert submitted.status_code == 200, submitted.text
    return approver.post(f"{base}/activate", json={})


@pytest.fixture
def active_contract(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    currency_id: str,
    cost_codes: dict[str, str],
    active_budget: str,
) -> str:
    """A live main-works contract for 1,000,000, 10% retention, 100,000 advance.

    The worked example the module's arithmetic is pinned against, so a test that
    needs a commitment does not have to restate one.
    """
    created = create_contract(
        finance_client,
        project_id,
        currency_id,
        retention_rate_fraction="0.1000",
        advance_entitlement_amount="100000.00",
        planned_start_date="2026-01-05",
        planned_completion_date="2026-12-31",
    )
    assert created.status_code == 201, created.text
    contract_id = created.json()["id"]
    line = set_contract_line(
        finance_client,
        project_id,
        contract_id,
        sequence=1,
        cost_code_id=cost_codes["hard"],
        original_amount_ex_tax="1000000.00",
    )
    assert line.status_code == 200, line.text
    activated = govern_contract(finance_client, cfo_client, project_id, contract_id)
    assert activated.status_code == 200, activated.text
    return contract_id


def create_certificate(
    client: TestClient,
    project_id: str,
    contract_id: str,
    *,
    certificate_number: str = "IPC-01",
    period_start: str = "2026-01-01",
    period_end: str = "2026-01-31",
    certificate_date: str = "2026-02-05",
    **overrides: object,
) -> Response:
    body: dict[str, Any] = {
        "certificate_number": certificate_number,
        "period_start": period_start,
        "period_end": period_end,
        "certificate_date": certificate_date,
    }
    body.update(overrides)
    return client.post(
        f"{construction_url(project_id)}/contracts/{contract_id}/certificates", json=body
    )


def set_certificate_line(
    client: TestClient,
    project_id: str,
    certificate_id: str,
    *,
    cost_code_id: str,
    current_work_value_ex_tax: str,
    **overrides: object,
) -> Response:
    body: dict[str, Any] = {
        "cost_code_id": cost_code_id,
        "current_work_value_ex_tax": current_work_value_ex_tax,
    }
    body.update(overrides)
    return client.put(
        f"{construction_url(project_id)}/certificates/{certificate_id}/lines", json=body
    )


def certify(
    preparer: TestClient,
    certifier: TestClient,
    project_id: str,
    certificate_id: str,
) -> Response:
    """Submit and certify one certificate, by two different people."""
    base = f"{construction_url(project_id)}/certificates/{certificate_id}"
    submitted = preparer.post(f"{base}/submit", json={})
    assert submitted.status_code == 200, submitted.text
    return certifier.post(f"{base}/certify", json={})


@pytest.fixture
def certified_certificate(
    finance_client: TestClient,
    manager_member_client: TestClient,
    project_id: str,
    cost_codes: dict[str, str],
    active_contract: str,
) -> str:
    """The first certificate: 200,000 certified, 20,000 retained, 180,000 net due.

    No retention release, because at this point none is held: retention is
    released out of what earlier certificates withheld, and this is the first.
    The 185,000 figure the calculator is pinned against needs a second
    certificate to release from, which
    ``test_construction_certificates.py`` builds explicitly.
    """
    created = create_certificate(
        finance_client,
        project_id,
        active_contract,
    )
    assert created.status_code == 201, created.text
    certificate_id = created.json()["id"]
    line = set_certificate_line(
        finance_client,
        project_id,
        certificate_id,
        cost_code_id=cost_codes["hard"],
        current_work_value_ex_tax="200000.00",
    )
    assert line.status_code == 200, line.text
    certified = certify(finance_client, manager_member_client, project_id, certificate_id)
    assert certified.status_code == 200, certified.text
    return certificate_id


@pytest.fixture
def manager_member_client(admin_client: TestClient, project_id: str, manager: User) -> TestClient:
    """A Project Manager who is a member of the project.

    Distinct from ``finance`` so that the maker/checker comparison has two real
    identifiers to compare on the technical ladder.
    """
    grant_access(admin_client, project_id, manager)
    return client_for(manager.email)


def record_invoice(
    client: TestClient,
    project_id: str,
    contract_id: str,
    *,
    invoice_number: str = "INV-001",
    invoice_type: str = "progress",
    invoice_date: str = "2026-02-06",
    amount_ex_tax: str = "185000.00",
    **overrides: object,
) -> Response:
    body: dict[str, Any] = {
        "invoice_number": invoice_number,
        "invoice_type": invoice_type,
        "invoice_date": invoice_date,
        "amount_ex_tax": amount_ex_tax,
    }
    body.update(overrides)
    return client.post(
        f"{construction_url(project_id)}/contracts/{contract_id}/invoices", json=body
    )


def record_payment(
    client: TestClient,
    project_id: str,
    contract_id: str,
    currency_id: str,
    *,
    payment_reference: str = "PMT-001",
    payment_date: str = "2026-02-20",
    amount: str = "185000.00",
    **overrides: object,
) -> Response:
    body: dict[str, Any] = {
        "payment_reference": payment_reference,
        "payment_date": payment_date,
        "amount": amount,
        "currency_id": currency_id,
    }
    body.update(overrides)
    return client.post(
        f"{construction_url(project_id)}/contracts/{contract_id}/payments", json=body
    )


def create_milestone(
    client: TestClient,
    project_id: str,
    *,
    code: str = "FOUNDATION",
    name: str = "Foundation complete",
    milestone_type: str = "progress",
    **overrides: object,
) -> Response:
    body: dict[str, Any] = {
        "code": code,
        "name": name,
        "milestone_type": milestone_type,
    }
    body.update(overrides)
    return client.post(f"{construction_url(project_id)}/milestones", json=body)


def create_forecast(
    client: TestClient,
    project_id: str,
    *,
    as_of_date: str | None = None,
    change_reason: str = "Month-end forecast",
    **overrides: object,
) -> Response:
    body: dict[str, Any] = {
        "as_of_date": as_of_date or date.today().isoformat(),
        "change_reason": change_reason,
    }
    body.update(overrides)
    return client.post(f"{construction_url(project_id)}/forecasts", json=body)


def set_forecast_line(
    client: TestClient,
    project_id: str,
    version_id: str,
    *,
    cost_code_id: str,
    forecast_remaining_amount_ex_tax: str,
    **overrides: object,
) -> Response:
    body: dict[str, Any] = {
        "cost_code_id": cost_code_id,
        "forecast_remaining_amount_ex_tax": forecast_remaining_amount_ex_tax,
    }
    body.update(overrides)
    return client.put(f"{construction_url(project_id)}/forecasts/{version_id}/lines", json=body)


def govern_forecast(
    preparer: TestClient,
    approver: TestClient,
    project_id: str,
    version_id: str,
) -> Response:
    """Submit, approve and activate one forecast version."""
    base = f"{construction_url(project_id)}/forecasts/{version_id}"
    submitted = preparer.post(f"{base}/submit", json={})
    assert submitted.status_code == 200, submitted.text
    approved = approver.post(f"{base}/approve", json={"reason": "Reviewed with the team"})
    assert approved.status_code == 200, approved.text
    return preparer.post(f"{base}/activate", json={})


def construction_summary(client: TestClient, project_id: str) -> dict[str, Any]:
    response = client.get(f"{construction_url(project_id)}/summary")
    assert response.status_code == 200, response.text
    return response.json()


# --------------------------------------------------------------------------- #
# Cashflow (PR-MVP-10)
# --------------------------------------------------------------------------- #


def cashflow_url(project_id: str) -> str:
    return f"{PROJECTS}/{project_id}/cashflow"


def cover_construction_forecast(
    client: TestClient,
    project_id: str,
    version_id: str,
    cost_codes: dict[str, str],
    *,
    hard: str = "1000000.00",
    soft: str = "0.00",
    contingency: str = "0.00",
    other: str = "0.00",
) -> None:
    """Forecast every active cost code, which is what submission insists on."""
    for category, amount in (
        ("hard", hard),
        ("soft", soft),
        ("contingency", contingency),
        ("other", other),
    ):
        response = set_forecast_line(
            client,
            project_id,
            version_id,
            cost_code_id=cost_codes[category],
            forecast_remaining_amount_ex_tax=amount,
        )
        assert response.status_code == 200, response.text


@pytest.fixture
def active_construction_forecast(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    cost_codes: dict[str, str],
    active_budget: str,
) -> str:
    """A construction forecast in force: 1,000,000 left on hard cost, nothing else.

    The pin every cashflow forecast needs. Kept deliberately simple — one cost
    code with a round number — so a cashflow test's monthly schedule can be read
    at a glance against what it has to reconcile to.
    """
    version_id = create_forecast(finance_client, project_id).json()["id"]
    cover_construction_forecast(finance_client, project_id, version_id, cost_codes)
    governed = govern_forecast(finance_client, cfo_client, project_id, version_id)
    assert governed.status_code == 200, governed.text
    return version_id


@pytest.fixture
def flat_construction_forecast(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    cost_codes: dict[str, str],
    active_budget: str,
) -> str:
    """A construction forecast in force with nothing left to spend.

    The pin a cashflow forecast needs, without the build schedule that comes
    with it. A test proving the cash bridge on real transactions should not also
    have to schedule a million pounds of construction across its months to get a
    forecast activated — and an explicit zero is a perfectly good statement:
    the build is costed and finished.
    """
    version_id = create_forecast(finance_client, project_id).json()["id"]
    cover_construction_forecast(finance_client, project_id, version_id, cost_codes, hard="0.00")
    governed = govern_forecast(finance_client, cfo_client, project_id, version_id)
    assert governed.status_code == 200, governed.text
    return version_id


def create_cashflow_forecast(
    client: TestClient,
    project_id: str,
    *,
    as_of_date: str | None = None,
    forecast_start_month: str | None = None,
    forecast_end_month: str | None = None,
    opening_unrestricted_cash: str = "0.00",
    opening_restricted_cash: str = "0.00",
    discount_rate_per_period: str = "0.000000",
    change_reason: str = "Opening cash forecast",
    **overrides: object,
) -> Response:
    today = date.today()
    body: dict[str, Any] = {
        "as_of_date": as_of_date or today.isoformat(),
        "forecast_start_month": forecast_start_month or today.replace(day=1).isoformat(),
        "forecast_end_month": forecast_end_month
        or date(today.year + 1, today.month, 1).isoformat(),
        "opening_unrestricted_cash": opening_unrestricted_cash,
        "opening_restricted_cash": opening_restricted_cash,
        "discount_rate_per_period": discount_rate_per_period,
        "change_reason": change_reason,
    }
    body.update(overrides)
    return client.post(f"{cashflow_url(project_id)}/forecasts", json=body)


def set_cashflow_line(
    client: TestClient,
    project_id: str,
    version_id: str,
    *,
    period_month: str,
    source_kind: str,
    category: str,
    amount: str,
    **overrides: object,
) -> Response:
    body: dict[str, Any] = {
        "period_month": period_month,
        "source_kind": source_kind,
        "category": category,
        "amount": amount,
    }
    body.update(overrides)
    return client.put(f"{cashflow_url(project_id)}/forecasts/{version_id}/lines", json=body)


def cover_cashflow_construction(
    client: TestClient,
    project_id: str,
    version_id: str,
    cost_codes: dict[str, str],
    *,
    month: str | None = None,
) -> None:
    """Write an explicit zero for every pinned cost code this version is silent on.

    What a preparer has to do before a forecast can be governed, and what the
    ``construction_schedule_covers_*`` check exists to insist on. A code the
    forecast says nothing about is not a code expecting nothing — it is a code
    nobody opened — so the difference has to be written down. Lines the test
    already wrote are left exactly as they are.
    """
    detail = client.get(f"{cashflow_url(project_id)}/forecasts/{version_id}")
    assert detail.status_code == 200, detail.text
    already = {
        line["construction_cost_code_id"]
        for line in detail.json()["lines"]
        if line["source_kind"] == "construction"
    }
    for cost_code_id in cost_codes.values():
        if cost_code_id in already:
            continue
        response = set_cashflow_line(
            client,
            project_id,
            version_id,
            period_month=month or month_named(0),
            source_kind="construction",
            category="construction",
            amount="0.00",
            construction_cost_code_id=cost_code_id,
        )
        assert response.status_code == 200, response.text


def govern_cashflow_forecast(
    preparer: TestClient,
    approver: TestClient,
    project_id: str,
    version_id: str,
    *,
    activator: TestClient | None = None,
    cost_codes: dict[str, str] | None = None,
) -> Response:
    """Submit, approve and activate one cashflow forecast."""
    if cost_codes is not None:
        cover_cashflow_construction(preparer, project_id, version_id, cost_codes)
    base = f"{cashflow_url(project_id)}/forecasts/{version_id}"
    submitted = preparer.post(f"{base}/submit", json={})
    assert submitted.status_code == 200, submitted.text
    approved = approver.post(f"{base}/approve", json={"reason": "Reviewed with Finance"})
    assert approved.status_code == 200, approved.text
    return (activator or preparer).post(f"{base}/activate", json={})


def record_development(
    client: TestClient,
    project_id: str,
    currency_id: str,
    *,
    category: str = "consultants",
    amount: str = "50000.00",
    movement_date: str | None = None,
    **overrides: object,
) -> Response:
    body: dict[str, Any] = {
        "category": category,
        "amount": amount,
        "movement_date": movement_date or date.today().isoformat(),
        "currency_id": currency_id,
    }
    body.update(overrides)
    return client.post(f"{cashflow_url(project_id)}/development-movements", json=body)


def record_financing(
    client: TestClient,
    project_id: str,
    currency_id: str,
    *,
    movement_type: str = "equity_contribution",
    amount: str = "1000000.00",
    movement_date: str | None = None,
    **overrides: object,
) -> Response:
    body: dict[str, Any] = {
        "movement_type": movement_type,
        "amount": amount,
        "movement_date": movement_date or date.today().isoformat(),
        "currency_id": currency_id,
    }
    body.update(overrides)
    return client.post(f"{cashflow_url(project_id)}/financing-movements", json=body)


def restrict_receipt(
    client: TestClient,
    project_id: str,
    receipt_id: str,
    *,
    restricted_amount: str,
    reason: str = "Escrow account under the trust deed",
    **overrides: object,
) -> Response:
    body: dict[str, Any] = {"restricted_amount": restricted_amount, "reason": reason}
    body.update(overrides)
    return client.post(f"{cashflow_url(project_id)}/receipts/{receipt_id}/restriction", json=body)


def release_restriction(
    client: TestClient,
    project_id: str,
    restriction_id: str,
    *,
    amount: str,
    release_date: str | None = None,
    **overrides: object,
) -> Response:
    body: dict[str, Any] = {
        "amount": amount,
        "release_date": release_date or date.today().isoformat(),
    }
    body.update(overrides)
    return client.post(
        f"{cashflow_url(project_id)}/restrictions/{restriction_id}/releases", json=body
    )


def cashflow_summary(client: TestClient, project_id: str, **params: str) -> dict[str, Any]:
    response = client.get(f"{cashflow_url(project_id)}/summary", params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def cashflow_monthly(client: TestClient, project_id: str, **params: str) -> dict[str, Any]:
    response = client.get(f"{cashflow_url(project_id)}/monthly", params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def month_named(offset: int) -> str:
    """The first of the month ``offset`` months from this one, as an ISO date."""
    today = date.today().replace(day=1)
    month = today.month - 1 + offset
    return date(today.year + month // 12, month % 12 + 1, 1).isoformat()


def approve_construction_invoice(client: TestClient, project_id: str, invoice_id: str) -> None:
    response = client.post(f"{construction_url(project_id)}/invoices/{invoice_id}/approve", json={})
    assert response.status_code == 200, response.text


def allocate_construction_payment(
    client: TestClient,
    project_id: str,
    payment_id: str,
    *,
    invoice_id: str,
    amount: str,
) -> None:
    response = client.put(
        f"{construction_url(project_id)}/payments/{payment_id}/allocations",
        json={"invoice_id": invoice_id, "amount": amount},
    )
    assert response.status_code == 200, response.text


def confirm_construction_payment(client: TestClient, project_id: str, payment_id: str) -> Response:
    return client.post(f"{construction_url(project_id)}/payments/{payment_id}/confirm", json={})


def pay_construction(
    finance: TestClient,
    checker: TestClient,
    project_id: str,
    contract_id: str,
    currency_id: str,
    certificate_id: str,
    *,
    amount: str,
    payment_date: str | None = None,
    reference: str = "PMT-CF",
    invoice_number: str = "INV-CF",
) -> str:
    """Drive a construction disbursement all the way to confirmed cash.

    Cashflow reads construction's confirmed payments and never writes one, so a
    cashflow test that needs construction cash out has to produce it the way the
    business does: an invoice against a certificate, approved by a second
    person, paid, allocated and confirmed.
    """
    invoice = record_invoice(
        finance,
        project_id,
        contract_id,
        certificate_id=certificate_id,
        invoice_number=invoice_number,
        amount_ex_tax=amount,
    )
    assert invoice.status_code == 201, invoice.text
    invoice_id = invoice.json()["id"]
    approve_construction_invoice(checker, project_id, invoice_id)
    payment = record_payment(
        finance,
        project_id,
        contract_id,
        currency_id,
        payment_reference=reference,
        amount=amount,
        payment_date=payment_date or date.today().isoformat(),
    )
    assert payment.status_code == 201, payment.text
    payment_id: str = payment.json()["id"]
    allocate_construction_payment(
        finance, project_id, payment_id, invoice_id=invoice_id, amount=amount
    )
    confirmed = confirm_construction_payment(checker, project_id, payment_id)
    assert confirmed.status_code == 200, confirmed.text
    return payment_id


def refund_buyer(
    sales_ops: TestClient,
    cfo: TestClient,
    collections: TestClient,
    finance: TestClient,
    project_id: str,
    sale_id: str,
    *,
    refund_due: str = "12000.00",
    amount: str,
    refund_date: str | None = None,
) -> str:
    """Cancel a sale and pay part of the refund. Cash out, never a negative receipt."""
    opened = sales_ops.post(
        f"{sales_url(project_id)}/contracts/{sale_id}/cancellation",
        json={
            "initiated_by_party": "buyer",
            "initiation_date": "2026-01-05",
            "reason": "Buyer withdrew",
            "refund_due_amount": refund_due,
            "forfeiture_amount": "0.00",
        },
    )
    assert opened.status_code == 201, opened.text
    cancellation_id = opened.json()["id"]
    approved = cfo.post(
        f"{sales_url(project_id)}/cancellations/{cancellation_id}/approve-financial-terms",
        json={"reason": "Terms reviewed"},
    )
    assert approved.status_code == 200, approved.text
    recorded = collections.post(
        f"{collections_url(project_id)}/sales/{sale_id}/refunds",
        json={
            "cancellation_id": cancellation_id,
            "amount": amount,
            "refund_date": refund_date or date.today().isoformat(),
        },
    )
    assert recorded.status_code == 201, recorded.text
    refund_id: str = recorded.json()["id"]
    confirmed = finance.post(f"{collections_url(project_id)}/refunds/{refund_id}/confirm", json={})
    assert confirmed.status_code == 200, confirmed.text
    return refund_id
