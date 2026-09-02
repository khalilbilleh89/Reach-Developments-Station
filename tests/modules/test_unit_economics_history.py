"""What a sold unit cost, and the four ways that answer used to be wrong.

Every case here is a way the recorded economic history of a *sold* unit could
move after the fact — which is the one thing this module exists to prevent. They
are grouped by the mechanism rather than by the endpoint, because the endpoint is
rarely where the damage is.

**The date the freeze turns on.** A contract's ``contract_date`` is stamped when
it is drafted. Between drafting and signature a project's cost basis can be
replaced, and a reader that froze on the draft date would hand the deal a basis
that had already been superseded when the parties actually signed.

**Backdating a replacement.** A version whose window reaches into a period
already governed does not merely start early: activating it *closes the standing
version's window early*, and every unit signed in the overlap silently changes
cost basis.

**Land arriving twice, or by hand.** Land is the one pool with a canonical
source. A retyped land pool is the spreadsheet this module replaces, and two
canonical land pools double the project's land cost while every pool still
reconciles exactly.

**A unit the basis never considered.** Missing allocation and zero allocation
are different facts. Reported as the same fact, the second-best margin in the
project is produced by an omission.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.access.models import User
from tests.factories import client_for, make_user
from tests.modules.conftest import (
    PROJECTS,
    SETTINGS,
    add_pool,
    approve_areas,
    cover_required_pools,
    create_version,
    economics_url,
    govern,
    inventory_url,
    pricing_url,
    record_legal,
    sales_url,
    today,
    unit_economics,
    unit_payload,
)


def version_url(project_id: str, version_id: str) -> str:
    return f"{economics_url(project_id)}/allocation-versions/{version_id}"


def _stamp(db: Session, table: str, row_id: str, column: str, value: object) -> None:
    """Move one business date so a test has a history to read.

    A contract drafted today cannot be made to sit in a historical window by
    driving the API. The draft date is moved here, against the same PostgreSQL
    the code reads; every assertion afterwards goes through the ordinary route.
    """
    db.execute(
        text(f"UPDATE {table} SET {column} = :value WHERE id = :row_id"),
        {"value": value, "row_id": row_id},
    )
    db.commit()


def price_unit(
    admin_client: TestClient,
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
) -> None:
    """Measure and price one unit through the governed route."""
    approve_areas(
        admin_client, project_id, unit_id, area_types, internal="70.0000", balcony="7.0000"
    )
    draft = finance_client.post(
        f"{pricing_url(project_id)}/units/{unit_id}/price-versions", json={}
    )
    assert draft.status_code == 201, draft.text
    base = f"{pricing_url(project_id)}/price-versions/{draft.json()['id']}"
    assert finance_client.post(f"{base}/submit", json={}).status_code == 200
    approved = cfo_client.post(f"{base}/approve", json={"reason": "Within feasibility"})
    assert approved.status_code == 200, approved.text
    assert cfo_client.post(f"{base}/activate").status_code == 200


# --------------------------------------------------------------------------- #
# 1. The date the freeze turns on
# --------------------------------------------------------------------------- #


@pytest.fixture
def sale_signed_today(
    sales_ops_client: TestClient,
    legal_client: TestClient,
    db: Session,
    project_id: str,
    submitted_sale: str,
) -> str:
    """A contract drafted in February and signed today.

    The gap is the whole point: these are two different dates, and only one of
    them is the date the deal became a deal.
    """
    _stamp(db, "sale_contracts", submitted_sale, "contract_date", "2026-02-01")
    for event_type, event_date in (
        ("spa_drafted", "2026-02-01"),
        ("spa_issued", "2026-02-02"),
        ("buyer_signed", today()),
        ("seller_signed", today()),
    ):
        record_legal(legal_client, project_id, submitted_sale, event_type, event_date)
    activated = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts/{submitted_sale}/activate", json={}
    )
    assert activated.status_code == 200, activated.text
    return submitted_sale


class TestTheDateTheFreezeTurnsOn:
    """Given a contract drafted under one basis and signed under another."""

    @pytest.fixture
    def two_bases(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
    ) -> tuple[str, str]:
        """V1 from January at 100,000 hard; V2 from today at 200,000."""
        del priced_pair
        first = create_version(finance_client, project_id, effective_from="2026-01-01")
        cover_required_pools(finance_client, project_id, first, hard="100000.00")
        assert govern(finance_client, cfo_client, project_id, first).status_code == 200

        second = create_version(
            finance_client, project_id, effective_from=today(), reason="Forecast raised"
        )
        cover_required_pools(finance_client, project_id, second, hard="200000.00")
        assert govern(finance_client, cfo_client, project_id, second).status_code == 200
        return first, second

    def test_the_basis_is_the_one_governing_at_signature_not_at_drafting(
        self,
        finance_client: TestClient,
        sales_ops_client: TestClient,
        project_id: str,
        sale_signed_today: str,
        two_bases: tuple[str, str],
    ) -> None:
        """The defect this class exists for.

        Drafted 1 February, which sits inside version one's window. Signed
        today, which sits inside version two's. Freezing on the draft date would
        analyse this deal on a cost basis that had already been replaced by the
        time anybody put a pen to it — and would report it as history.
        """
        first, second = two_bases
        sale = sales_ops_client.get(f"{sales_url(project_id)}/contracts/{sale_signed_today}").json()
        assert sale["sale"]["contract_date"] == "2026-02-01"

        row = unit_economics(finance_client, project_id, sale["sale"]["unit_id"])
        assert row["allocation_version_id"] == second
        assert row["allocation_version_id"] != first
        assert row["hard_cost"] == "100000.00"

    def test_the_sale_endpoint_agrees_with_the_unit_endpoint(
        self,
        finance_client: TestClient,
        project_id: str,
        sale_signed_today: str,
        two_bases: tuple[str, str],
    ) -> None:
        """One definition of the economic date, or the two reads disagree."""
        _first, second = two_bases
        response = finance_client.get(f"{economics_url(project_id)}/sales/{sale_signed_today}")
        assert response.status_code == 200, response.text
        assert response.json()["economics"]["allocation_version_id"] == second


class TestAnUnsignedContract:
    """Given a contract nobody has signed, when its economics are asked for."""

    def test_it_has_no_sold_economics(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        submitted_sale: str,
        priced_pair: tuple[str, str],
    ) -> None:
        """A proposal is not a deal, and it has no frozen margin to report."""
        del priced_pair
        version_id = create_version(finance_client, project_id, effective_from="2026-01-01")
        cover_required_pools(finance_client, project_id, version_id, hard="100000.00")
        assert govern(finance_client, cfo_client, project_id, version_id).status_code == 200

        response = finance_client.get(f"{economics_url(project_id)}/sales/{submitted_sale}")
        assert response.status_code == 409, response.text
        assert "signed by both parties" in response.json()["detail"]

    def test_one_signature_is_not_enough(
        self,
        finance_client: TestClient,
        legal_client: TestClient,
        project_id: str,
        submitted_sale: str,
        priced_pair: tuple[str, str],
    ) -> None:
        """A contract binds when both sides have signed, not when one has."""
        del priced_pair
        for event_type, event_date in (
            ("spa_drafted", "2026-02-01"),
            ("spa_issued", "2026-02-02"),
            ("buyer_signed", "2026-02-03"),
        ):
            record_legal(legal_client, project_id, submitted_sale, event_type, event_date)
        response = finance_client.get(f"{economics_url(project_id)}/sales/{submitted_sale}")
        assert response.status_code == 409, response.text


class TestACancelledButSignedSale:
    """Given a deal that was genuinely live and then unwound."""

    def test_it_keeps_the_basis_that_governed_it(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        sales_ops_client: TestClient,
        legal_client: TestClient,
        project_id: str,
        active_sale: str,
        priced_pair: tuple[str, str],
    ) -> None:
        """Cancellation ends the contract. It does not unsign it.

        The signatures stay on the timeline, so the economic date stays, so the
        cost basis the deal was analysed on stays. A business that could not
        read the economics of its failed sales would stop learning from them.
        """
        del priced_pair, legal_client
        version_id = create_version(finance_client, project_id, effective_from="2026-01-01")
        cover_required_pools(finance_client, project_id, version_id, hard="100000.00")
        assert govern(finance_client, cfo_client, project_id, version_id).status_code == 200

        cancelled = sales_ops_client.post(
            f"{sales_url(project_id)}/contracts/{active_sale}/cancellation",
            json={
                "initiated_by_party": "buyer",
                "reason": "Buyer withdrew after signature",
            },
        )
        assert cancelled.status_code == 201, cancelled.text

        response = finance_client.get(f"{economics_url(project_id)}/sales/{active_sale}")
        assert response.status_code == 200, response.text
        economics = response.json()["economics"]
        assert economics["allocation_version_id"] == version_id
        assert economics["basis"] == "sold"


# --------------------------------------------------------------------------- #
# 2. No replacement reaches into a governed period
# --------------------------------------------------------------------------- #


class TestBackdatingAReplacement:
    """Given a project with a governing basis, when a replacement is proposed."""

    @pytest.fixture
    def governing(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
    ) -> str:
        del priced_pair
        version_id = create_version(finance_client, project_id, effective_from="2026-01-01")
        cover_required_pools(finance_client, project_id, version_id, hard="100000.00")
        assert govern(finance_client, cfo_client, project_id, version_id).status_code == 200
        return version_id

    def test_the_opening_basis_may_still_be_back_dated(
        self, finance_client: TestClient, project_id: str, priced_pair: tuple[str, str]
    ) -> None:
        """The one exception, and the reason it exists: sales predate this module."""
        del priced_pair
        response = finance_client.post(
            f"{economics_url(project_id)}/allocation-versions",
            json={
                "effective_from": "2024-01-01",
                "change_reason": "Opening baseline for contracts signed before this module",
                "finance_treatment": "excluded",
            },
        )
        assert response.status_code == 201, response.text

    def test_a_replacement_may_not_start_in_the_past(
        self, finance_client: TestClient, project_id: str, governing: str
    ) -> None:
        """Not "after the one it replaces" — not in the past at all.

        The original rule accepted any date after the standing version's start,
        so a basis running since January would accept a replacement dated June.
        Activating that closes January's window in June, and every contract
        signed between June and today changes cost basis retrospectively.
        """
        del governing
        response = finance_client.post(
            f"{economics_url(project_id)}/allocation-versions",
            json={
                "effective_from": "2026-06-01",
                "change_reason": "Revised hard cost",
                "finance_treatment": "excluded",
            },
        )
        assert response.status_code == 409, response.text
        assert "cannot take effect in the past" in response.json()["detail"]

    def test_a_clone_may_not_either(
        self, finance_client: TestClient, project_id: str, governing: str
    ) -> None:
        """Cloning is the ordinary way to propose a change, so it is the ordinary way in."""
        response = finance_client.post(
            f"{version_url(project_id, governing)}/clone",
            json={"effective_from": "2026-06-01", "change_reason": "Revised hard cost"},
        )
        assert response.status_code == 409, response.text

    def test_today_is_accepted(
        self, finance_client: TestClient, project_id: str, governing: str
    ) -> None:
        del governing
        response = finance_client.post(
            f"{economics_url(project_id)}/allocation-versions",
            json={
                "effective_from": today(),
                "change_reason": "Revised hard cost",
                "finance_treatment": "excluded",
            },
        )
        assert response.status_code == 201, response.text

    def test_an_approved_version_whose_date_has_passed_cannot_be_activated(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        db: Session,
        project_id: str,
        governing: str,
    ) -> None:
        """Approved for a date that then slipped past. Activating it would backfill.

        Prepared for today and approved, but nobody activated it and the date
        moved on. Making it current now would close the standing version's
        window on a date already lived, so it is refused and Finance is told to
        clone it for today rather than have the system quietly restate August.
        """
        del governing
        replacement = create_version(
            finance_client, project_id, effective_from=today(), reason="Prepared last month"
        )
        cover_required_pools(finance_client, project_id, replacement, hard="200000.00")
        base = version_url(project_id, replacement)
        assert finance_client.post(f"{base}/calculate", json={}).status_code == 200
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200
        assert cfo_client.post(f"{base}/approve", json={"reason": "Checked"}).status_code == 200

        _stamp(
            db,
            "unit_economics_allocation_versions",
            replacement,
            "effective_from",
            "2026-08-01",
        )
        response = finance_client.post(f"{base}/activate", json={})
        assert response.status_code == 409, response.text
        assert "has passed" in response.json()["detail"]
        assert "Clone it for today" in response.json()["detail"]

    def test_the_sold_units_basis_does_not_move_when_a_later_version_activates(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        sales_ops_client: TestClient,
        project_id: str,
        active_sale: str,
        priced_pair: tuple[str, str],
    ) -> None:
        """The invariant all of the above protects, asserted directly."""
        del priced_pair
        first = create_version(finance_client, project_id, effective_from="2026-01-01")
        cover_required_pools(finance_client, project_id, first, hard="100000.00")
        assert govern(finance_client, cfo_client, project_id, first).status_code == 200

        sale = sales_ops_client.get(f"{sales_url(project_id)}/contracts/{active_sale}").json()
        unit_id = sale["sale"]["unit_id"]
        before = unit_economics(finance_client, project_id, unit_id)
        assert before["allocation_version_id"] == first

        second = create_version(
            finance_client, project_id, effective_from=today(), reason="Forecast raised"
        )
        cover_required_pools(finance_client, project_id, second, hard="900000.00")
        assert govern(finance_client, cfo_client, project_id, second).status_code == 200

        after = unit_economics(finance_client, project_id, unit_id)
        assert after["allocation_version_id"] == first
        assert after["hard_cost"] == before["hard_cost"]


# --------------------------------------------------------------------------- #
# 3. Land has one source and one shape
# --------------------------------------------------------------------------- #


class TestTheCanonicalLandPool:
    """Given a draft basis, when its land pool is described."""

    @pytest.fixture
    def draft(
        self, finance_client: TestClient, project_id: str, priced_pair: tuple[str, str]
    ) -> str:
        del priced_pair
        return create_version(finance_client, project_id)

    def test_a_land_pool_may_not_be_typed_by_hand(
        self, finance_client: TestClient, project_id: str, draft: str
    ) -> None:
        """The spreadsheet this module exists to delete, except it reconciles."""
        response = add_pool(
            finance_client,
            project_id,
            draft,
            pool_number="LAND-01",
            category="land",
            source_kind="manual",
            amount="500000.00",
        )
        assert response.status_code == 422, response.text
        assert "land register" in response.json()["detail"]

    def test_the_register_may_only_be_drawn_once(
        self, finance_client: TestClient, project_id: str, draft: str, land_cost: str
    ) -> None:
        """Two canonical land pools each draw the whole total, and both reconcile.

        840,000 becomes 1,680,000, every pool equals the sum of its allocations,
        and nothing downstream can tell. This is the most dangerous shape in the
        module, because it is wrong and internally consistent.
        """
        del land_cost
        first = add_pool(
            finance_client,
            project_id,
            draft,
            pool_number="LAND-01",
            category="land",
            source_kind="project_land",
            amount=None,
        )
        assert first.status_code == 201, first.text
        second = add_pool(
            finance_client,
            project_id,
            draft,
            pool_number="LAND-02",
            category="land",
            source_kind="project_land",
            amount=None,
        )
        assert second.status_code == 409, second.text
        assert "allocate the same acquisition cost twice" in second.json()["detail"]

    def test_it_may_not_be_scoped_to_one_phase(
        self, finance_client: TestClient, project_id: str, draft: str, phase_id: str
    ) -> None:
        """There is no governed parcel-to-phase attribution to justify it."""
        response = add_pool(
            finance_client,
            project_id,
            draft,
            pool_number="LAND-01",
            category="land",
            source_kind="project_land",
            amount=None,
            scope_kind="phase",
            phase_id=phase_id,
        )
        assert response.status_code == 422, response.text
        assert "whole project" in response.json()["detail"]

    def test_it_may_not_be_scoped_to_one_building_either(
        self, finance_client: TestClient, project_id: str, draft: str, building_id: str
    ) -> None:
        response = add_pool(
            finance_client,
            project_id,
            draft,
            pool_number="LAND-01",
            category="land",
            source_kind="project_land",
            amount=None,
            scope_kind="building",
            building_id=building_id,
        )
        assert response.status_code == 422, response.text

    def test_a_scope_change_cannot_move_it_off_the_project_afterwards(
        self, finance_client: TestClient, project_id: str, draft: str, phase_id: str
    ) -> None:
        """The refusal that would be missing if only creation were checked."""
        created = add_pool(
            finance_client,
            project_id,
            draft,
            pool_number="LAND-01",
            category="land",
            source_kind="project_land",
            amount=None,
        )
        assert created.status_code == 201, created.text
        response = finance_client.patch(
            f"{version_url(project_id, draft)}/pools/{created.json()['id']}",
            json={"scope_kind": "phase", "phase_id": phase_id},
        )
        assert response.status_code == 422, response.text


# --------------------------------------------------------------------------- #
# 4. The population a version divided among
# --------------------------------------------------------------------------- #


class TestThePopulationSnapshot:
    """Given a calculated basis, when the set of eligible units changes."""

    @pytest.fixture
    def approved_basis(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        method: str = "unit_count",
    ) -> str:
        del priced_pair
        version_id = create_version(finance_client, project_id)
        cover_required_pools(finance_client, project_id, version_id, hard="100000.00")
        base = version_url(project_id, version_id)
        assert finance_client.post(f"{base}/calculate", json={}).status_code == 200
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200
        assert cfo_client.post(f"{base}/approve", json={"reason": "Checked"}).status_code == 200
        return version_id

    def test_a_unit_added_after_calculation_refuses_activation(
        self,
        finance_client: TestClient,
        admin_client: TestClient,
        project_id: str,
        floor_id: str,
        approved_basis: str,
    ) -> None:
        """The blind spot the source-snapshot checks could not see.

        Every other freshness check starts from an allocation row and asks
        whether its source moved, so a unit with no allocation row is invisible
        to all of them. The version reconciles, activates, and the new unit then
        carries no share of any shared cost — a zero somebody will act on.
        """
        created = admin_client.post(
            f"{inventory_url(project_id)}/units",
            json=unit_payload(floor_id, unit_number="103", unit_reference="B1-103", sequence=3),
        )
        assert created.status_code == 201, created.text

        base = version_url(project_id, approved_basis)
        response = finance_client.post(f"{base}/activate", json={})
        assert response.status_code == 409, response.text
        detail = response.json()["detail"]
        assert "B1-103" in detail
        assert "gained" in detail

    def test_a_unit_removed_after_calculation_refuses_activation(
        self,
        finance_client: TestClient,
        admin_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        approved_basis: str,
    ) -> None:
        """Drift in the other direction is drift too."""
        _first, second = priced_pair
        archived = admin_client.patch(
            f"{inventory_url(project_id)}/units/{second}", json={"is_active": False}
        )
        assert archived.status_code == 200, archived.text

        base = version_url(project_id, approved_basis)
        response = finance_client.post(f"{base}/activate", json={})
        assert response.status_code == 409, response.text
        assert "no longer covers" in response.json()["detail"]

    def test_a_custom_driver_pool_detects_it_as_well(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        admin_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        floor_id: str,
    ) -> None:
        """The methods that carry no source snapshot were previously unchecked.

        ``custom_driver`` and ``unit_count`` write no area schedule and no price
        version onto their allocation rows, so *none* of the three original
        checks looked at them at all.
        """
        first, second = priced_pair
        version_id = create_version(finance_client, project_id)
        cover_required_pools(finance_client, project_id, version_id)
        pool = add_pool(
            finance_client,
            project_id,
            version_id,
            pool_number="HARD-02",
            category="hard",
            allocation_method="custom_driver",
            amount="900.00",
        )
        assert pool.status_code == 201, pool.text
        drivers = finance_client.put(
            f"{version_url(project_id, version_id)}/pools/{pool.json()['id']}/drivers",
            json={
                "drivers": [
                    {"unit_id": first, "driver_value": "1.0000"},
                    {"unit_id": second, "driver_value": "2.0000"},
                ]
            },
        )
        assert drivers.status_code == 200, drivers.text

        base = version_url(project_id, version_id)
        assert finance_client.post(f"{base}/calculate", json={}).status_code == 200
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200
        assert cfo_client.post(f"{base}/approve", json={"reason": "Checked"}).status_code == 200

        created = admin_client.post(
            f"{inventory_url(project_id)}/units",
            json=unit_payload(floor_id, unit_number="104", unit_reference="B1-104", sequence=4),
        )
        assert created.status_code == 201, created.text

        response = finance_client.post(f"{base}/activate", json={})
        assert response.status_code == 409, response.text
        assert "HARD-02" in response.json()["detail"]


# --------------------------------------------------------------------------- #
# 5. A category the basis never addressed for this unit
# --------------------------------------------------------------------------- #


@pytest.fixture
def second_phase(admin_client: TestClient, project_id: str, phase_id: str) -> dict[str, str]:
    """A second phase with a building, a floor and a unit on it."""
    del phase_id
    phase = admin_client.post(
        f"{inventory_url(project_id)}/phases",
        json={"code": "PHASE-2", "name": "Phase 2", "sequence": 2},
    )
    assert phase.status_code == 201, phase.text
    building = admin_client.post(
        f"{inventory_url(project_id)}/buildings",
        json={"phase_id": phase.json()["id"], "code": "B2", "name": "Building 2"},
    )
    assert building.status_code == 201, building.text
    floor = admin_client.post(
        f"{inventory_url(project_id)}/floors",
        json={"building_id": building.json()["id"], "code": "01", "label": "First floor"},
    )
    assert floor.status_code == 201, floor.text
    unit = admin_client.post(
        f"{inventory_url(project_id)}/units",
        json=unit_payload(
            floor.json()["id"], unit_number="201", unit_reference="B2-201", sequence=10
        ),
    )
    assert unit.status_code == 201, unit.text
    return {
        "phase": phase.json()["id"],
        "building": building.json()["id"],
        "floor": floor.json()["id"],
        "unit": unit.json()["id"],
    }


class TestRequiredCategoryCoverage:
    """Given a basis whose pools do not reach every unit."""

    def test_submission_refuses_a_phase_the_hard_pool_does_not_reach(
        self,
        finance_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        phase_id: str,
        second_phase: dict[str, str],
    ) -> None:
        """The version-level check passes and the units are still uncovered.

        The basis contains a hard pool, so "a cost basis must address hard cost"
        is satisfied — but the pool is scoped to Phase 1, and every unit in
        Phase 2 carries no hard cost at all. Their margins would be the best in
        the project, produced by an omission.
        """
        del priced_pair
        version_id = create_version(finance_client, project_id)
        land = add_pool(
            finance_client,
            project_id,
            version_id,
            pool_number="LAND-01",
            category="land",
            source_kind="project_land",
            amount=None,
        )
        assert land.status_code == 201, land.text
        for number, category, scope in (
            ("HARD-01", "hard", phase_id),
            ("SOFT-01", "soft", None),
        ):
            extra: dict[str, Any] = {}
            if scope is not None:
                extra = {"scope_kind": "phase", "phase_id": scope}
            created = add_pool(
                finance_client,
                project_id,
                version_id,
                pool_number=number,
                category=category,
                amount="1000.00",
                **extra,
            )
            assert created.status_code == 201, created.text

        base = version_url(project_id, version_id)
        assert finance_client.post(f"{base}/calculate", json={}).status_code == 200
        response = finance_client.post(f"{base}/submit", json={})
        assert response.status_code == 409, response.text
        detail = response.json()["detail"]
        assert "no hard cost reaches" in detail
        assert "B2-201" in detail

    def test_an_explicit_zero_pool_closes_the_gap(
        self,
        finance_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        phase_id: str,
        second_phase: dict[str, str],
    ) -> None:
        """Omission is refused; a decision that the cost is nil is accepted."""
        del priced_pair
        version_id = create_version(finance_client, project_id)
        land = add_pool(
            finance_client,
            project_id,
            version_id,
            pool_number="LAND-01",
            category="land",
            source_kind="project_land",
            amount=None,
        )
        assert land.status_code == 201, land.text
        assert (
            add_pool(
                finance_client,
                project_id,
                version_id,
                pool_number="HARD-01",
                category="hard",
                amount="1000.00",
                scope_kind="phase",
                phase_id=phase_id,
            ).status_code
            == 201
        )
        assert (
            add_pool(
                finance_client,
                project_id,
                version_id,
                pool_number="HARD-02",
                category="hard",
                amount="0.00",
                scope_kind="phase",
                phase_id=second_phase["phase"],
            ).status_code
            == 201
        )
        assert (
            add_pool(
                finance_client,
                project_id,
                version_id,
                pool_number="SOFT-01",
                category="soft",
                amount="500.00",
            ).status_code
            == 201
        )
        base = version_url(project_id, version_id)
        assert finance_client.post(f"{base}/calculate", json={}).status_code == 200
        response = finance_client.post(f"{base}/submit", json={})
        assert response.status_code == 200, response.text

    def test_a_unit_created_after_activation_is_not_a_zero_cost_unit(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        admin_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        floor_id: str,
        area_types: dict[str, str],
    ) -> None:
        """The most attractive fabricated number in the module.

        The version exists, reconciles and is current. This unit simply was not
        part of the population it divided among, so every category reads zero
        and the margin would come out at essentially one hundred per cent.
        """
        del priced_pair
        version_id = create_version(finance_client, project_id)
        cover_required_pools(finance_client, project_id, version_id, hard="100000.00")
        assert govern(finance_client, cfo_client, project_id, version_id).status_code == 200

        created = admin_client.post(
            f"{inventory_url(project_id)}/units",
            json=unit_payload(floor_id, unit_number="105", unit_reference="B1-105", sequence=5),
        )
        assert created.status_code == 201, created.text
        newcomer = created.json()["id"]
        price_unit(admin_client, finance_client, cfo_client, project_id, newcomer, area_types)

        row = unit_economics(finance_client, project_id, newcomer)
        assert row["profitability_status"] == "unreconciled_cost_basis"
        assert row["margin_fraction"] is None
        assert row["profit_after_finance"] is None
        assert row["hard_cost"] == "0.00"

    def test_a_finance_allocated_basis_needs_a_finance_row_too(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        phase_id: str,
        second_phase: dict[str, str],
    ) -> None:
        """Finance is required exactly when the version says it is allocated."""
        del priced_pair, cfo_client
        version_id = create_version(finance_client, project_id, finance_treatment="allocated")
        cover_required_pools(finance_client, project_id, version_id, hard="100.00")
        assert (
            add_pool(
                finance_client,
                project_id,
                version_id,
                pool_number="FIN-01",
                category="finance",
                amount="50.00",
                scope_kind="phase",
                phase_id=phase_id,
            ).status_code
            == 201
        )
        base = version_url(project_id, version_id)
        assert finance_client.post(f"{base}/calculate", json={}).status_code == 200
        response = finance_client.post(f"{base}/submit", json={})
        assert response.status_code == 409, response.text
        assert "no finance cost reaches" in response.json()["detail"]
        assert second_phase["unit"] is not None


# --------------------------------------------------------------------------- #
# 6. Which unit costs belong to which deal
# --------------------------------------------------------------------------- #


class TestActualUnitCostSelection:
    """Given costs recorded before, during and after a deal."""

    def test_a_cost_incurred_before_the_sale_survives_into_it(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        sales_ops_client: TestClient,
        legal_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        submitted_sale: str,
    ) -> None:
        """Rectifying a floor in March is part of what the unit cost in June.

        The money left the business and the building changed; no buyer was
        involved. Reading only costs tagged with the current contract drops it
        and reports a sold margin too high by exactly what was spent.
        """
        del priced_pair
        sale = sales_ops_client.get(f"{sales_url(project_id)}/contracts/{submitted_sale}").json()
        unit_id = sale["sale"]["unit_id"]

        recorded = finance_client.post(
            f"{economics_url(project_id)}/units/{unit_id}/costs",
            json={
                "cost_type": "rectification",
                "basis": "actual",
                "amount": "9500.00",
                "effective_date": "2026-02-01",
            },
        )
        assert recorded.status_code == 201, recorded.text

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

        version_id = create_version(finance_client, project_id, effective_from="2026-01-01")
        cover_required_pools(finance_client, project_id, version_id, hard="100.00")
        assert govern(finance_client, cfo_client, project_id, version_id).status_code == 200

        row = unit_economics(finance_client, project_id, unit_id)
        assert row["basis"] == "sold"
        assert row["direct_cost"] == "9500.00"

    def test_a_forecast_cost_may_not_name_a_contract(
        self,
        finance_client: TestClient,
        sales_ops_client: TestClient,
        project_id: str,
        active_sale: str,
        priced_pair: tuple[str, str],
    ) -> None:
        """A forecast is what the unit is expected to cost, not what a deal cost."""
        del priced_pair
        sale = sales_ops_client.get(f"{sales_url(project_id)}/contracts/{active_sale}").json()
        response = finance_client.post(
            f"{economics_url(project_id)}/units/{sale['sale']['unit_id']}/costs",
            json={
                "cost_type": "finishes",
                "basis": "forecast",
                "amount": "1000.00",
                "effective_date": "2026-04-01",
                "sale_contract_id": active_sale,
            },
        )
        assert response.status_code == 422, response.text
        assert "without a contract" in response.json()["detail"]

    def test_an_actual_direct_cost_may_be_recorded_without_one(
        self,
        finance_client: TestClient,
        sales_ops_client: TestClient,
        project_id: str,
        active_sale: str,
        priced_pair: tuple[str, str],
    ) -> None:
        """Even while a contract is live: the building is what changed, not the deal."""
        del priced_pair
        sale = sales_ops_client.get(f"{sales_url(project_id)}/contracts/{active_sale}").json()
        response = finance_client.post(
            f"{economics_url(project_id)}/units/{sale['sale']['unit_id']}/costs",
            json={
                "cost_type": "rectification",
                "basis": "actual",
                "amount": "250.00",
                "effective_date": "2026-04-01",
            },
        )
        assert response.status_code == 201, response.text


# --------------------------------------------------------------------------- #
# 7. A partial unit scope is not a route to the whole project's costs
# --------------------------------------------------------------------------- #


@pytest.fixture
def phase_scoped_finance(
    db: Session, admin_client: TestClient, project_id: str, phase_id: str
) -> User:
    """A Finance user granted only Phase 1."""
    user = make_user(db, email="scoped-finance@example.com", roles=("finance",))
    assert admin_client.put(f"{PROJECTS}/{project_id}/access/{user.id}").status_code == 200
    assert (
        admin_client.patch(
            f"{PROJECTS}/{project_id}/access/{user.id}/phase-scope",
            json={"phase_scope": "selected"},
        ).status_code
        == 200
    )
    assert (
        admin_client.put(f"{PROJECTS}/{project_id}/access/{user.id}/phases/{phase_id}").status_code
        == 200
    )
    return user


class TestPhaseScopedGovernanceAccess:
    """Given a financial reader narrowed to one phase of a project."""

    def test_the_unit_register_is_narrowed_as_before(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        second_phase: dict[str, str],
        phase_scoped_finance: User,
    ) -> None:
        del priced_pair
        version_id = create_version(finance_client, project_id)
        cover_required_pools(finance_client, project_id, version_id, hard="1000.00")
        del cfo_client, version_id

        scoped = client_for(phase_scoped_finance.email)
        response = scoped.get(f"{economics_url(project_id)}/units")
        assert response.status_code == 200, response.text
        references = {row["unit_reference"] for row in response.json()}
        assert "B2-201" not in references

    def test_the_hidden_phases_unit_is_not_found(
        self,
        project_id: str,
        priced_pair: tuple[str, str],
        second_phase: dict[str, str],
        phase_scoped_finance: User,
    ) -> None:
        del priced_pair
        scoped = client_for(phase_scoped_finance.email)
        response = scoped.get(f"{economics_url(project_id)}/units/{second_phase['unit']}")
        assert response.status_code == 404, response.text

    def test_the_version_endpoints_do_not_become_a_back_door(
        self,
        finance_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        phase_id: str,
        second_phase: dict[str, str],
        phase_scoped_finance: User,
    ) -> None:
        """Phase 1 sees 100. Phase 2's 900 must not arrive through the pool list.

        Filtering the version down to visible units and calling what is left
        "reconciled" would be worse than refusing: a subset does not equal a
        full pool, and the number would be neither the pool's total nor the
        phase's share.
        """
        del priced_pair
        version_id = create_version(finance_client, project_id)
        land = add_pool(
            finance_client,
            project_id,
            version_id,
            pool_number="LAND-01",
            category="land",
            source_kind="project_land",
            amount=None,
        )
        assert land.status_code == 201, land.text
        for number, scope, amount in (
            ("HARD-01", phase_id, "100.00"),
            ("HARD-02", second_phase["phase"], "900.00"),
        ):
            created = add_pool(
                finance_client,
                project_id,
                version_id,
                pool_number=number,
                category="hard",
                amount=amount,
                scope_kind="phase",
                phase_id=scope,
            )
            assert created.status_code == 201, created.text

        scoped = client_for(phase_scoped_finance.email)
        for path in ("", f"/{version_id}", f"/{version_id}/allocations"):
            response = scoped.get(f"{economics_url(project_id)}/allocation-versions{path}")
            assert response.status_code == 403, f"{path}: {response.text}"
            assert "900" not in response.text

    def test_a_finance_user_with_the_whole_project_still_reads_them(
        self, finance_client: TestClient, project_id: str, priced_pair: tuple[str, str]
    ) -> None:
        """The guard is about scope, not about role."""
        del priced_pair
        version_id = create_version(finance_client, project_id)
        assert finance_client.get(version_url(project_id, version_id)).status_code == 200


# --------------------------------------------------------------------------- #
# 8. Two denominations never make one number
# --------------------------------------------------------------------------- #


@pytest.fixture
def second_currency(admin_client: TestClient) -> str:
    """A second real currency, so a re-basing can actually happen."""
    response = admin_client.post(
        f"{SETTINGS}/currencies", json={"code": "USD", "name": "United States dollar"}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def rebase_project(
    admin_client: TestClient, db: Session, project_id: str, currency_id: str
) -> None:
    """Re-denominate the project, and record why it is done in the database.

    Projects allows a base currency change only while a project is still in
    ``setup``, and it refuses one once land or permit money exists. Unit
    economics needs approved prices, which need a project past setup. So *today*
    these two states cannot both be reached through the API, and the refusal
    below is proved against a state the database can hold but the current
    routes will not produce.

    That is deliberate rather than a shortcut. The unit cost table stores its
    own ``currency_id`` with no constraint tying it to the version's, so the
    mixture is one schema change or one new re-basing route away — and the read
    has to refuse it on its own terms, not because another domain happens to be
    guarding the door.
    """
    refused = admin_client.patch(f"{PROJECTS}/{project_id}", json={"base_currency_id": currency_id})
    assert refused.status_code == 409, refused.text
    assert "still in setup" in refused.json()["detail"]
    _stamp(db, "projects", project_id, "base_currency_id", currency_id)


class TestMixedUnitCostCurrencies:
    """Given unit costs recorded either side of a re-basing."""

    def test_they_are_never_added_together(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        admin_client: TestClient,
        db: Session,
        project_id: str,
        priced_pair: tuple[str, str],
        second_currency: str,
    ) -> None:
        """1,000 JOD and 500 USD do not make 1,500 of anything.

        A unit cost carries its own denomination. Aggregating without it
        produces a number in no currency, and every layer above would then treat
        that number as money — a margin, a project total, a board figure.
        """
        first, _second = priced_pair
        version_id = create_version(finance_client, project_id, effective_from="2026-01-01")
        cover_required_pools(finance_client, project_id, version_id, hard="100.00")
        assert govern(finance_client, cfo_client, project_id, version_id).status_code == 200

        before = finance_client.post(
            f"{economics_url(project_id)}/units/{first}/costs",
            json={
                "cost_type": "finishes",
                "basis": "forecast",
                "amount": "1000.00",
                "effective_date": "2026-02-01",
            },
        )
        assert before.status_code == 201, before.text
        assert unit_economics(finance_client, project_id, first)["direct_cost"] == "1000.00"

        rebase_project(admin_client, db, project_id, second_currency)

        after = finance_client.post(
            f"{economics_url(project_id)}/units/{first}/costs",
            json={
                "cost_type": "finishes",
                "basis": "forecast",
                "amount": "500.00",
                "effective_date": "2026-03-01",
            },
        )
        assert after.status_code == 201, after.text

        row = unit_economics(finance_client, project_id, first)
        assert row["profitability_status"] == "currency_mismatch"
        assert row["profit_after_finance"] is None
        assert row["margin_fraction"] is None
        assert row["return_on_cost_fraction"] is None

    def test_the_rows_themselves_stay_visible_with_their_own_currencies(
        self,
        finance_client: TestClient,
        admin_client: TestClient,
        db: Session,
        project_id: str,
        priced_pair: tuple[str, str],
        second_currency: str,
    ) -> None:
        """Refusing the total is not refusing the evidence.

        Finance has to be able to see which row caused it, so the rows keep
        their own ``currency_id`` and are still returned.
        """
        first, _second = priced_pair
        firstly = finance_client.post(
            f"{economics_url(project_id)}/units/{first}/costs",
            json={
                "cost_type": "finishes",
                "basis": "forecast",
                "amount": "1000.00",
                "effective_date": "2026-02-01",
            },
        )
        assert firstly.status_code == 201, firstly.text
        rebase_project(admin_client, db, project_id, second_currency)

        second = finance_client.post(
            f"{economics_url(project_id)}/units/{first}/costs",
            json={
                "cost_type": "finishes",
                "basis": "forecast",
                "amount": "500.00",
                "effective_date": "2026-03-01",
            },
        )
        assert second.status_code == 201, second.text

        detail = finance_client.get(f"{economics_url(project_id)}/units/{first}")
        assert detail.status_code == 200, detail.text
        currencies = {cost["currency_id"] for cost in detail.json()["unit_costs"]}
        assert len(currencies) == 2, currencies


class TestProjectTotalsAcrossCurrencies:
    """Given a project re-based after its economics were recorded."""

    def test_a_historical_currency_is_excluded_rather_than_converted(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        admin_client: TestClient,
        db: Session,
        project_id: str,
        priced_pair: tuple[str, str],
        second_currency: str,
    ) -> None:
        """A JOD profit plus a USD profit is not a project total.

        Both rows are internally valid, and that is exactly what makes this
        dangerous: nothing is broken, so nothing refuses — the totals just add
        two denominations and report the answer as money.
        """
        del priced_pair
        version_id = create_version(finance_client, project_id, effective_from="2026-01-01")
        cover_required_pools(finance_client, project_id, version_id, hard="1000.00")
        assert govern(finance_client, cfo_client, project_id, version_id).status_code == 200

        summary = finance_client.get(f"{economics_url(project_id)}/summary").json()
        assert summary["comparable_unit_count"] == 2
        assert summary["currency_mismatch_count"] == 0

        rebase_project(admin_client, db, project_id, second_currency)

        after = finance_client.get(f"{economics_url(project_id)}/summary").json()
        assert after["currency_id"] == second_currency
        assert after["comparable_unit_count"] == 0
        assert after["currency_mismatch_count"] == 2
        assert after["unit_count"] == 2
        assert after["revenue_total"] == "0.00"
        assert after["profit_total"] == "0.00"
        assert after["margin_fraction"] is None


# --------------------------------------------------------------------------- #
# 9. The drill-down explains the total it sits under
# --------------------------------------------------------------------------- #


class TestSaleDrillDownReconciles:
    """Given a sold unit whose costs were incurred across two deals and none."""

    def test_the_rows_shown_are_the_rows_counted(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        sales_ops_client: TestClient,
        project_id: str,
        active_sale: str,
        priced_pair: tuple[str, str],
    ) -> None:
        """6,700 of direct cost above a list showing 5,200 is not a drill-down.

        The detail used to filter to the current contract while the arithmetic
        read the unit's costs as well, so a pre-sale rectification counted
        towards the total and appeared nowhere beneath it.
        """
        del priced_pair
        sale = sales_ops_client.get(f"{sales_url(project_id)}/contracts/{active_sale}").json()
        unit_id = sale["sale"]["unit_id"]

        version_id = create_version(finance_client, project_id, effective_from="2026-01-01")
        cover_required_pools(finance_client, project_id, version_id, hard="120000.00")
        assert govern(finance_client, cfo_client, project_id, version_id).status_code == 200

        for body in (
            {
                "cost_type": "rectification",
                "basis": "actual",
                "amount": "1500.00",
                "effective_date": "2026-02-01",
            },
            {
                "cost_type": "unit_upgrade",
                "basis": "actual",
                "amount": "5200.00",
                "effective_date": "2026-03-01",
                "sale_contract_id": active_sale,
            },
            {
                "cost_type": "sales_commission",
                "basis": "actual",
                "amount": "800.00",
                "effective_date": "2026-03-02",
                "sale_contract_id": active_sale,
            },
        ):
            response = finance_client.post(
                f"{economics_url(project_id)}/units/{unit_id}/costs", json=body
            )
            assert response.status_code == 201, response.text

        detail = finance_client.get(f"{economics_url(project_id)}/sales/{active_sale}")
        assert detail.status_code == 200, detail.text
        payload = detail.json()
        economics = payload["economics"]
        assert economics["direct_cost"] == "6700.00"
        assert economics["variable_selling_cost"] == "800.00"

        amounts = {cost["amount"] for cost in payload["unit_costs"]}
        assert amounts == {"1500.00", "5200.00", "800.00"}

        # And the rows add up to the figures above them, by cost class.
        direct = sum(
            Decimal(cost["amount"])
            for cost in payload["unit_costs"]
            if cost["cost_type"] in {"rectification", "unit_upgrade"} and cost["status"] == "active"
        )
        assert direct == Decimal("6700.00")

    def test_another_deals_commission_is_neither_shown_nor_counted(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        sales_ops_client: TestClient,
        admin_client: TestClient,
        db: Session,
        project_id: str,
        active_sale: str,
        priced_pair: tuple[str, str],
        buyer_id: str,
    ) -> None:
        """A commission earned winning a different buyer belongs to that deal.

        A real second contract is created on the other unit, because the whole
        point of the foreign key is that a cost names a contract that exists.
        The row is then re-pointed at it in the database: recording it there
        through the API is refused, since that contract is not this unit's —
        which is precisely why this state is only reachable through an older,
        cancelled deal on the same unit.
        """
        _first, second_unit = priced_pair
        sale = sales_ops_client.get(f"{sales_url(project_id)}/contracts/{active_sale}").json()
        unit_id = sale["sale"]["unit_id"]

        other_sale = _draft_second_contract(
            admin_client, sales_ops_client, project_id, second_unit, buyer_id
        )

        version_id = create_version(finance_client, project_id, effective_from="2026-01-01")
        cover_required_pools(finance_client, project_id, version_id, hard="100.00")
        assert govern(finance_client, cfo_client, project_id, version_id).status_code == 200

        recorded = finance_client.post(
            f"{economics_url(project_id)}/units/{unit_id}/costs",
            json={
                "cost_type": "sales_commission",
                "basis": "actual",
                "amount": "900.00",
                "effective_date": "2026-03-05",
                "sale_contract_id": active_sale,
            },
        )
        assert recorded.status_code == 201, recorded.text
        _stamp(
            db,
            "unit_economics_unit_costs",
            recorded.json()["id"],
            "sale_contract_id",
            other_sale,
        )

        detail = finance_client.get(f"{economics_url(project_id)}/sales/{active_sale}")
        assert detail.status_code == 200, detail.text
        payload = detail.json()
        assert payload["economics"]["variable_selling_cost"] == "0.00"
        assert "900.00" not in {cost["amount"] for cost in payload["unit_costs"]}


def _draft_second_contract(
    admin_client: TestClient,
    sales_ops_client: TestClient,
    project_id: str,
    unit_id: str,
    buyer_id: str,
) -> str:
    """A real, drafted contract on another unit of the same project."""
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
    base = f"{sales_url(project_id)}/reservations/{reservation_id}"
    confirmed = sales_ops_client.post(
        f"{base}/confirm-deposit", json={"evidence_reference": "BANK-REF-2"}
    )
    assert confirmed.status_code == 200, confirmed.text
    assert sales_ops_client.post(f"{base}/activate", json={}).status_code == 200

    contract = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts",
        json={"reservation_id": reservation_id, "spa_number": "SPA-0002"},
    )
    assert contract.status_code == 201, contract.text
    return str(contract.json()["sale"]["id"])
