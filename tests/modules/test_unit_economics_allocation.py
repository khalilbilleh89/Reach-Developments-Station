"""Building a cost basis: pools, drivers, reconciliation and the lifecycle.

The discipline this file exists to hold is that a shared cost becomes a unit
cost only through a version somebody approved, that the division loses nothing,
and that an approved division cannot quietly start describing a project that has
since changed underneath it.

Every history here is arranged through the real routes. What is simulated is
never a figure.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.modules.conftest import (
    PROJECTS,
    add_pool,
    approve_areas,
    cover_required_pools,
    create_version,
    economics_url,
    govern,
    inventory_url,
    parcel_payload,
    pricing_url,
    unit_payload,
)


def version_url(project_id: str, version_id: str) -> str:
    return f"{economics_url(project_id)}/allocation-versions/{version_id}"


def calculate(client: TestClient, project_id: str, version_id: str) -> dict:
    response = client.post(f"{version_url(project_id, version_id)}/calculate", json={})
    assert response.status_code == 200, response.text
    return response.json()


def pool_id_of(client: TestClient, project_id: str, version_id: str, number: str) -> str:
    detail = client.get(version_url(project_id, version_id)).json()
    return next(pool["id"] for pool in detail["pools"] if pool["pool_number"] == number)


def allocations(
    client: TestClient, project_id: str, version_id: str, *, pool: str | None = None
) -> list[dict]:
    """The allocation rows of one version, optionally narrowed to one pool.

    Narrowing matters: a version has several pools and every unit appears in
    each of them, so a dict keyed by unit over the whole version silently keeps
    whichever pool came last.
    """
    params = {}
    if pool is not None:
        params["pool_id"] = pool_id_of(client, project_id, version_id, pool)
    response = client.get(f"{version_url(project_id, version_id)}/allocations", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def allocated_by_unit(
    client: TestClient, project_id: str, version_id: str, pool: str
) -> dict[str, dict]:
    return {row["unit_id"]: row for row in allocations(client, project_id, version_id, pool=pool)}


class TestOpeningACostBasis:
    """Given a project, when Finance opens its first allocation version."""

    def test_the_version_is_denominated_in_the_project_base_currency(
        self,
        finance_client: TestClient,
        admin_client: TestClient,
        project_id: str,
        operational_project: str,
    ) -> None:
        """Not a choice. There is no exchange rate to make it one."""
        del operational_project
        version_id = create_version(finance_client, project_id)
        project = admin_client.get(f"{PROJECTS}/{project_id}").json()
        detail = finance_client.get(version_url(project_id, version_id)).json()
        assert detail["version"]["currency_id"] == project["base_currency_id"]
        assert detail["version"]["status"] == "draft"
        assert detail["version"]["version_number"] == 1

    def test_a_reason_is_required(
        self, finance_client: TestClient, project_id: str, operational_project: str
    ) -> None:
        del operational_project
        response = finance_client.post(
            f"{economics_url(project_id)}/allocation-versions",
            json={"effective_from": "2026-01-01", "change_reason": "   "},
        )
        assert response.status_code == 422


class TestTheAllocationMethods:
    """Given two priced units, when each of the five methods divides a pool."""

    def test_weighted_area_uses_inventorys_own_weighting(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
    ) -> None:
        """110 and 64 weighted metres: 100 internal + half of 20, and 60 + half of 8."""
        first, second = priced_pair
        version_id = create_version(finance_client, project_id)
        cover_required_pools(finance_client, project_id, version_id)
        response = add_pool(
            finance_client,
            project_id,
            version_id,
            pool_number="HARD-02",
            category="hard",
            allocation_method="weighted_area",
            amount="174000.00",
        )
        assert response.status_code == 201, response.text

        preview = calculate(finance_client, project_id, version_id)
        pool = next(row for row in preview["pools"] if row["pool_number"] == "HARD-02")
        assert pool["driver_total"] == "174.0000"
        assert pool["allocated_total"] == "174000.00"
        assert pool["variance"] == "0.00"

        rows = allocated_by_unit(finance_client, project_id, version_id, "HARD-02")
        assert rows[first]["driver_value"] == "110.0000"
        assert rows[second]["driver_value"] == "64.0000"
        assert rows[first]["allocated_amount"] == "110000.00"
        assert rows[second]["allocated_amount"] == "64000.00"
        del cfo_client

    def test_raw_area_divides_on_one_named_area_type(
        self,
        finance_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        area_types: dict[str, str],
    ) -> None:
        """Internal area only: 100 and 60, never 120 and 68."""
        first, second = priced_pair
        version_id = create_version(finance_client, project_id)
        cover_required_pools(finance_client, project_id, version_id)
        response = add_pool(
            finance_client,
            project_id,
            version_id,
            pool_number="SOFT-02",
            category="soft",
            allocation_method="raw_area",
            amount="160000.00",
            area_type_id=area_types["INTERNAL"],
        )
        assert response.status_code == 201, response.text

        calculate(finance_client, project_id, version_id)
        rows = allocated_by_unit(finance_client, project_id, version_id, "SOFT-02")
        assert rows[first]["driver_value"] == "100.0000"
        assert rows[second]["driver_value"] == "60.0000"
        assert rows[first]["allocated_amount"] == "100000.00"
        assert rows[second]["allocated_amount"] == "60000.00"

    def test_a_raw_area_pool_must_name_its_area_type(
        self, finance_client: TestClient, project_id: str, priced_pair: tuple[str, str]
    ) -> None:
        del priced_pair
        version_id = create_version(finance_client, project_id)
        response = add_pool(
            finance_client,
            project_id,
            version_id,
            pool_number="SOFT-03",
            category="soft",
            allocation_method="raw_area",
            amount="100.00",
        )
        assert response.status_code == 422
        assert "area type" in response.json()["detail"]

    def test_unit_count_gives_every_unit_one(
        self, finance_client: TestClient, project_id: str, priced_pair: tuple[str, str]
    ) -> None:
        del priced_pair
        version_id = create_version(finance_client, project_id)
        cover_required_pools(finance_client, project_id, version_id, soft="100.00")
        calculate(finance_client, project_id, version_id)
        rows = allocations(finance_client, project_id, version_id)
        assert len(rows) == 6, "three pools across two units"
        assert {row["driver_value"] for row in rows} == {"1.0000"}
        soft = allocated_by_unit(finance_client, project_id, version_id, "SOFT-01")
        assert sorted(row["allocated_amount"] for row in soft.values()) == ["50.00", "50.00"]

    def test_revenue_value_divides_on_the_current_approved_price(
        self,
        finance_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
    ) -> None:
        first, second = priced_pair
        version_id = create_version(finance_client, project_id)
        cover_required_pools(finance_client, project_id, version_id)
        response = add_pool(
            finance_client,
            project_id,
            version_id,
            pool_number="SOFT-04",
            category="soft",
            allocation_method="revenue_value",
            amount="1000.00",
        )
        assert response.status_code == 201, response.text
        calculate(finance_client, project_id, version_id)

        rows = allocated_by_unit(finance_client, project_id, version_id, "SOFT-04")
        assert set(rows) == {first, second}
        assert all(row["source_price_version_id"] is not None for row in rows.values())
        assert sum(Decimal(row["allocated_amount"]) for row in rows.values()) == Decimal("1000.00")
        # The two list prices, and the pool split in their proportion.
        assert rows[first]["driver_value"] == "165000.0000"
        assert rows[second]["driver_value"] == "96000.0000"
        assert rows[first]["allocated_amount"] == "632.18"
        assert rows[second]["allocated_amount"] == "367.82"

    def test_a_custom_driver_is_entered_per_unit_then_calculated(
        self, finance_client: TestClient, project_id: str, priced_pair: tuple[str, str]
    ) -> None:
        """Parking bays, a plot area, a surveyor's factor. One number, no formula."""
        first, second = priced_pair
        version_id = create_version(finance_client, project_id)
        cover_required_pools(finance_client, project_id, version_id)
        created = add_pool(
            finance_client,
            project_id,
            version_id,
            pool_number="HARD-03",
            category="hard",
            allocation_method="custom_driver",
            amount="120000.00",
        )
        assert created.status_code == 201, created.text
        pool_id = created.json()["id"]

        drivers = finance_client.put(
            f"{version_url(project_id, version_id)}/pools/{pool_id}/drivers",
            json={
                "drivers": [
                    {"unit_id": first, "driver_value": "2.0000"},
                    {"unit_id": second, "driver_value": "1.0000"},
                ]
            },
        )
        assert drivers.status_code == 200, drivers.text

        calculate(finance_client, project_id, version_id)
        rows = allocated_by_unit(finance_client, project_id, version_id, "HARD-03")
        assert rows[first]["allocated_amount"] == "80000.00"
        assert rows[second]["allocated_amount"] == "40000.00"

    def test_a_custom_driver_pool_refuses_to_calculate_without_every_driver(
        self, finance_client: TestClient, project_id: str, priced_pair: tuple[str, str]
    ) -> None:
        first, _second = priced_pair
        version_id = create_version(finance_client, project_id)
        cover_required_pools(finance_client, project_id, version_id)
        created = add_pool(
            finance_client,
            project_id,
            version_id,
            pool_number="HARD-04",
            category="hard",
            allocation_method="custom_driver",
            amount="100.00",
        )
        pool_id = created.json()["id"]
        finance_client.put(
            f"{version_url(project_id, version_id)}/pools/{pool_id}/drivers",
            json={"drivers": [{"unit_id": first, "driver_value": "1.0000"}]},
        )
        response = finance_client.post(f"{version_url(project_id, version_id)}/calculate", json={})
        assert response.status_code == 422
        assert "no driver value" in response.json()["detail"]


class TestReconciliation:
    """Given a calculated basis, when its pools are added back up."""

    def test_every_pool_equals_the_sum_of_its_allocations(
        self, finance_client: TestClient, project_id: str, priced_pair: tuple[str, str]
    ) -> None:
        """Land 100, hard 300, soft 50, finance 25. Source 475, allocated 475."""
        del priced_pair
        version_id = create_version(finance_client, project_id, finance_treatment="allocated")
        cover_required_pools(
            finance_client, project_id, version_id, land="100.00", hard="300.00", soft="50.00"
        )
        assert (
            add_pool(
                finance_client,
                project_id,
                version_id,
                pool_number="FIN-01",
                category="finance",
                amount="25.00",
            ).status_code
            == 201
        )
        preview = calculate(finance_client, project_id, version_id)
        assert preview["source_cost_total"] == "475.00"
        assert preview["allocated_cost_total"] == "475.00"
        assert preview["variance"] == "0.00"
        assert preview["reconciled"] is True

    def test_an_odd_division_still_reconciles_to_the_penny(
        self,
        finance_client: TestClient,
        admin_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        floor_id: str,
        area_types: dict[str, str],
    ) -> None:
        """Three units and a pool that does not divide by three."""
        del priced_pair
        third = admin_client.post(
            f"{inventory_url(project_id)}/units",
            json=unit_payload(floor_id, unit_number="103", unit_reference="B1-103", sequence=3),
        )
        assert third.status_code == 201, third.text
        approve_areas(admin_client, project_id, third.json()["id"], area_types)

        version_id = create_version(finance_client, project_id)
        cover_required_pools(finance_client, project_id, version_id, hard="100.00")
        preview = calculate(finance_client, project_id, version_id)
        assert preview["allocated_cost_total"] == "100.00"
        assert preview["reconciled"] is True


class TestLandComesFromTheLandRegister:
    """Given a project that bought land, when a land pool is sourced from it."""

    def test_the_pool_amount_is_derived_not_typed(
        self,
        finance_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        land_cost: str,
    ) -> None:
        """800,000 of consideration plus 40,000 of fees."""
        del priced_pair, land_cost
        version_id = create_version(finance_client, project_id)
        response = add_pool(
            finance_client,
            project_id,
            version_id,
            pool_number="LAND-01",
            category="land",
            source_kind="project_land",
            amount=None,
        )
        assert response.status_code == 201, response.text
        assert response.json()["amount"] == "840000.00"

    def test_only_a_land_pool_may_claim_the_land_register(
        self, finance_client: TestClient, project_id: str, priced_pair: tuple[str, str]
    ) -> None:
        del priced_pair
        version_id = create_version(finance_client, project_id)
        response = add_pool(
            finance_client,
            project_id,
            version_id,
            pool_number="HARD-09",
            category="hard",
            source_kind="project_land",
            amount=None,
        )
        assert response.status_code == 422

    def test_a_derived_amount_cannot_be_overtyped(
        self,
        finance_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        land_cost: str,
    ) -> None:
        """Correct the land record, not the pool. Two land costs is one too many."""
        del priced_pair, land_cost
        version_id = create_version(finance_client, project_id)
        created = add_pool(
            finance_client,
            project_id,
            version_id,
            pool_number="LAND-01",
            category="land",
            source_kind="project_land",
            amount=None,
        )
        pool_id = created.json()["id"]
        response = finance_client.patch(
            f"{version_url(project_id, version_id)}/pools/{pool_id}",
            json={"amount": "1.00"},
        )
        assert response.status_code == 409
        assert "land register" in response.json()["detail"]

    def test_activation_refuses_when_the_land_register_moved_after_approval(
        self,
        finance_client: TestClient,
        admin_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        land_cost: str,
    ) -> None:
        """An approved land allocation must still describe the land that was bought."""
        del priced_pair
        version_id = create_version(finance_client, project_id)
        assert (
            add_pool(
                finance_client,
                project_id,
                version_id,
                pool_number="LAND-01",
                category="land",
                source_kind="project_land",
                amount=None,
            ).status_code
            == 201
        )
        for number, category in (("HARD-01", "hard"), ("SOFT-01", "soft")):
            assert (
                add_pool(
                    finance_client,
                    project_id,
                    version_id,
                    pool_number=number,
                    category=category,
                    amount="0.00",
                ).status_code
                == 201
            )
        base = version_url(project_id, version_id)
        calculate(finance_client, project_id, version_id)
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200
        assert cfo_client.post(f"{base}/approve", json={"reason": "Reviewed"}).status_code == 200

        bought_more = admin_client.post(
            f"{PROJECTS}/{project_id}/parcels",
            json=parcel_payload(plot_number="PLOT-2", purchase_price="10000.00"),
        )
        assert bought_more.status_code == 201, bought_more.text

        response = finance_client.post(f"{base}/activate", json={})
        assert response.status_code == 409
        assert "land register total changed" in response.json()["detail"]
        del land_cost


class TestStaleSources:
    """Given an approved basis, when the facts it divided change underneath it."""

    def test_a_re_approved_area_schedule_blocks_activation(
        self,
        finance_client: TestClient,
        admin_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        area_types: dict[str, str],
    ) -> None:
        first, _second = priced_pair
        version_id = create_version(finance_client, project_id)
        cover_required_pools(finance_client, project_id, version_id)
        assert (
            add_pool(
                finance_client,
                project_id,
                version_id,
                pool_number="HARD-02",
                category="hard",
                allocation_method="weighted_area",
                amount="1000.00",
            ).status_code
            == 201
        )
        base = version_url(project_id, version_id)
        calculate(finance_client, project_id, version_id)
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200
        assert cfo_client.post(f"{base}/approve", json={"reason": "Reviewed"}).status_code == 200

        approve_areas(
            admin_client, project_id, first, area_types, internal="130.0000", revision="R1"
        )

        response = finance_client.post(f"{base}/activate", json={})
        assert response.status_code == 409
        assert "approved area schedule changed" in response.json()["detail"]

    def test_a_re_activated_price_blocks_activation(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
    ) -> None:
        first, _second = priced_pair
        version_id = create_version(finance_client, project_id)
        cover_required_pools(finance_client, project_id, version_id)
        assert (
            add_pool(
                finance_client,
                project_id,
                version_id,
                pool_number="SOFT-02",
                category="soft",
                allocation_method="revenue_value",
                amount="1000.00",
            ).status_code
            == 201
        )
        base = version_url(project_id, version_id)
        calculate(finance_client, project_id, version_id)
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200
        assert cfo_client.post(f"{base}/approve", json={"reason": "Reviewed"}).status_code == 200

        draft = finance_client.post(
            f"{pricing_url(project_id)}/units/{first}/price-versions", json={}
        )
        assert draft.status_code == 201, draft.text
        price = f"{pricing_url(project_id)}/price-versions/{draft.json()['id']}"
        assert finance_client.post(f"{price}/submit", json={}).status_code == 200
        assert cfo_client.post(f"{price}/approve", json={"reason": "Re-priced"}).status_code == 200
        assert cfo_client.post(f"{price}/activate").status_code == 200

        response = finance_client.post(f"{base}/activate", json={})
        assert response.status_code == 409
        assert "approved price changed" in response.json()["detail"]

    def test_a_unit_with_no_approved_price_refuses_a_revenue_pool(
        self,
        finance_client: TestClient,
        admin_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        floor_id: str,
    ) -> None:
        del priced_pair
        unpriced = admin_client.post(
            f"{inventory_url(project_id)}/units",
            json=unit_payload(floor_id, unit_number="104", unit_reference="B1-104", sequence=4),
        )
        assert unpriced.status_code == 201, unpriced.text
        version_id = create_version(finance_client, project_id)
        add_pool(
            finance_client,
            project_id,
            version_id,
            pool_number="SOFT-05",
            category="soft",
            allocation_method="revenue_value",
            amount="100.00",
        )
        response = finance_client.post(f"{version_url(project_id, version_id)}/calculate", json={})
        assert response.status_code == 422
        assert "B1-104" in response.json()["detail"]


class TestSubmissionGates:
    """Given a draft, when Finance asks for a second signature."""

    def test_land_hard_and_soft_must_each_be_addressed(
        self, finance_client: TestClient, project_id: str, priced_pair: tuple[str, str]
    ) -> None:
        """Zero is allowed and explicit. Omission is not, because it reads as zero."""
        del priced_pair
        version_id = create_version(finance_client, project_id)
        assert (
            add_pool(
                finance_client,
                project_id,
                version_id,
                pool_number="LAND-01",
                category="land",
                amount="100.00",
            ).status_code
            == 201
        )
        calculate(finance_client, project_id, version_id)
        response = finance_client.post(f"{version_url(project_id, version_id)}/submit", json={})
        assert response.status_code == 409
        detail = response.json()["detail"]
        assert "hard" in detail and "soft" in detail

    def test_an_allocated_finance_treatment_needs_a_finance_pool(
        self, finance_client: TestClient, project_id: str, priced_pair: tuple[str, str]
    ) -> None:
        del priced_pair
        version_id = create_version(finance_client, project_id, finance_treatment="allocated")
        cover_required_pools(finance_client, project_id, version_id)
        calculate(finance_client, project_id, version_id)
        response = finance_client.post(f"{version_url(project_id, version_id)}/submit", json={})
        assert response.status_code == 409
        assert "no finance pool" in response.json()["detail"]

    def test_an_excluded_treatment_refuses_a_finance_pool(
        self, finance_client: TestClient, project_id: str, priced_pair: tuple[str, str]
    ) -> None:
        del priced_pair
        version_id = create_version(finance_client, project_id)
        response = add_pool(
            finance_client,
            project_id,
            version_id,
            pool_number="FIN-01",
            category="finance",
            amount="10.00",
        )
        assert response.status_code == 409
        assert "excluded" in response.json()["detail"]

    def test_an_uncalculated_draft_cannot_be_submitted(
        self, finance_client: TestClient, project_id: str, priced_pair: tuple[str, str]
    ) -> None:
        del priced_pair
        version_id = create_version(finance_client, project_id)
        cover_required_pools(finance_client, project_id, version_id)
        response = finance_client.post(f"{version_url(project_id, version_id)}/submit", json={})
        assert response.status_code == 409
        assert "not been calculated" in response.json()["detail"]

    def test_editing_a_pool_after_calculating_invalidates_the_calculation(
        self, finance_client: TestClient, project_id: str, priced_pair: tuple[str, str]
    ) -> None:
        """Otherwise a signature would sit on a division of a different number."""
        del priced_pair
        version_id = create_version(finance_client, project_id)
        cover_required_pools(finance_client, project_id, version_id, hard="100.00")
        calculate(finance_client, project_id, version_id)
        detail = finance_client.get(version_url(project_id, version_id)).json()
        pool_id = next(pool["id"] for pool in detail["pools"] if pool["category"] == "hard")

        changed = finance_client.patch(
            f"{version_url(project_id, version_id)}/pools/{pool_id}",
            json={"amount": "200.00"},
        )
        assert changed.status_code == 200, changed.text
        response = finance_client.post(f"{version_url(project_id, version_id)}/submit", json={})
        assert response.status_code == 409
        assert "not been calculated" in response.json()["detail"]


class TestImmutabilityAfterSubmission:
    """Given a submitted basis, when somebody tries to change what it says."""

    def test_pools_cannot_be_added_changed_or_removed(
        self, finance_client: TestClient, project_id: str, priced_pair: tuple[str, str]
    ) -> None:
        del priced_pair
        version_id = create_version(finance_client, project_id)
        cover_required_pools(finance_client, project_id, version_id, hard="100.00")
        calculate(finance_client, project_id, version_id)
        base = version_url(project_id, version_id)
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200

        detail = finance_client.get(base).json()
        pool_id = next(pool["id"] for pool in detail["pools"] if pool["category"] == "hard")

        assert (
            add_pool(
                finance_client,
                project_id,
                version_id,
                pool_number="SOFT-09",
                category="soft",
                amount="1.00",
            ).status_code
            == 409
        )
        assert (
            finance_client.patch(f"{base}/pools/{pool_id}", json={"amount": "5.00"}).status_code
            == 409
        )
        assert finance_client.delete(f"{base}/pools/{pool_id}").status_code == 409
        assert finance_client.post(f"{base}/calculate", json={}).status_code == 409


class TestApprovalAndActivation:
    """Given a submitted basis, when a second person decides it."""

    def test_the_submitter_cannot_approve_their_own_basis(
        self, finance_client: TestClient, project_id: str, priced_pair: tuple[str, str]
    ) -> None:
        del priced_pair
        version_id = create_version(finance_client, project_id)
        cover_required_pools(finance_client, project_id, version_id, hard="100.00")
        calculate(finance_client, project_id, version_id)
        base = version_url(project_id, version_id)
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200
        response = finance_client.post(f"{base}/approve", json={"reason": "Mine"})
        assert response.status_code == 403
        assert "may not approve" in response.json()["detail"]

    def test_a_second_finance_user_may_approve(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
    ) -> None:
        del priced_pair
        version_id = create_version(finance_client, project_id)
        cover_required_pools(finance_client, project_id, version_id, hard="100.00")
        calculate(finance_client, project_id, version_id)
        base = version_url(project_id, version_id)
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200
        response = second_finance_client.post(f"{base}/approve", json={"reason": "Checked"})
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "approved"

    def test_a_rejection_records_its_reason_and_leaves_the_version_readable(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
    ) -> None:
        del priced_pair
        version_id = create_version(finance_client, project_id)
        cover_required_pools(finance_client, project_id, version_id, hard="100.00")
        calculate(finance_client, project_id, version_id)
        base = version_url(project_id, version_id)
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200
        response = cfo_client.post(f"{base}/reject", json={"reason": "Soft cost understated"})
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "rejected"
        assert response.json()["rejection_reason"] == "Soft cost understated"
        assert finance_client.get(base).status_code == 200

    def test_activation_supersedes_the_old_basis_and_closes_its_window(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
    ) -> None:
        del priced_pair
        first = create_version(finance_client, project_id, effective_from="2026-01-01")
        cover_required_pools(finance_client, project_id, first, hard="100.00")
        assert govern(finance_client, cfo_client, project_id, first).status_code == 200

        second = create_version(
            finance_client, project_id, effective_from="2026-06-01", reason="Revised hard cost"
        )
        cover_required_pools(finance_client, project_id, second, hard="200.00")
        assert govern(finance_client, cfo_client, project_id, second).status_code == 200

        versions = finance_client.get(f"{economics_url(project_id)}/allocation-versions").json()
        by_number = {row["version_number"]: row for row in versions}
        assert by_number[1]["status"] == "superseded"
        assert by_number[1]["effective_to"] == "2026-06-01"
        assert by_number[2]["status"] == "active"
        assert by_number[2]["effective_to"] is None

    def test_a_later_basis_cannot_start_inside_a_governed_period(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
    ) -> None:
        """Version 4 must not slide into version 1's window and restate a sold unit."""
        del priced_pair
        first = create_version(finance_client, project_id, effective_from="2026-05-01")
        cover_required_pools(finance_client, project_id, first, hard="100.00")
        assert govern(finance_client, cfo_client, project_id, first).status_code == 200

        response = finance_client.post(
            f"{economics_url(project_id)}/allocation-versions",
            json={
                "effective_from": "2026-02-01",
                "change_reason": "Trying to rewrite history",
                "finance_treatment": "excluded",
            },
        )
        assert response.status_code == 409
        assert "already been governed" in response.json()["detail"]

    def test_the_first_basis_may_be_back_dated_to_cover_existing_sales(
        self, finance_client: TestClient, project_id: str, priced_pair: tuple[str, str]
    ) -> None:
        """PR-MVP-08 arrives after sales exist, so an opening baseline is allowed."""
        del priced_pair
        response = finance_client.post(
            f"{economics_url(project_id)}/allocation-versions",
            json={
                "effective_from": "2020-01-01",
                "change_reason": "Opening baseline for contracts signed before this module",
                "finance_treatment": "excluded",
            },
        )
        assert response.status_code == 201, response.text

    def test_a_basis_cannot_be_activated_before_it_takes_effect(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
    ) -> None:
        del priced_pair
        version_id = create_version(finance_client, project_id, effective_from="2099-01-01")
        cover_required_pools(finance_client, project_id, version_id, hard="100.00")
        base = version_url(project_id, version_id)
        calculate(finance_client, project_id, version_id)
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200
        assert cfo_client.post(f"{base}/approve", json={"reason": "Fine"}).status_code == 200
        response = finance_client.post(f"{base}/activate", json={})
        assert response.status_code == 409
        assert "cannot be made current before then" in response.json()["detail"]


class TestCloning:
    """Given a governing basis, when Finance proposes a change to it."""

    def test_a_clone_copies_the_pools_and_starts_as_a_draft(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
    ) -> None:
        del priced_pair
        original = create_version(finance_client, project_id, effective_from="2026-01-01")
        cover_required_pools(finance_client, project_id, original, hard="100.00")
        assert govern(finance_client, cfo_client, project_id, original).status_code == 200

        response = finance_client.post(
            f"{version_url(project_id, original)}/clone",
            json={"effective_from": "2026-07-01", "change_reason": "Hard cost forecast raised"},
        )
        assert response.status_code == 201, response.text
        clone = response.json()
        assert clone["status"] == "draft"
        assert clone["source_version_id"] == original
        assert clone["calculated_at"] is None

        detail = finance_client.get(version_url(project_id, clone["id"])).json()
        assert {pool["pool_number"] for pool in detail["pools"]} == {
            "LAND-01",
            "HARD-01",
            "SOFT-01",
        }
        assert detail["reconciliation"]["allocation_count"] == 0


class TestScope:
    """Given phases and buildings, when a pool names one of them."""

    def test_a_project_pool_reaches_every_unit(
        self, finance_client: TestClient, project_id: str, priced_pair: tuple[str, str]
    ) -> None:
        del priced_pair
        version_id = create_version(finance_client, project_id)
        cover_required_pools(finance_client, project_id, version_id, hard="100.00")
        preview = calculate(finance_client, project_id, version_id)
        hard = next(row for row in preview["pools"] if row["category"] == "hard")
        assert hard["eligible_units"] == 2

    def test_a_building_pool_reaches_only_that_building(
        self,
        finance_client: TestClient,
        admin_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        phase_id: str,
        building_id: str,
        area_types: dict[str, str],
    ) -> None:
        del priced_pair
        other_building = admin_client.post(
            f"{inventory_url(project_id)}/buildings",
            json={"phase_id": phase_id, "code": "B2", "name": "Building two"},
        )
        assert other_building.status_code == 201, other_building.text
        other_floor = admin_client.post(
            f"{inventory_url(project_id)}/floors",
            json={"building_id": other_building.json()["id"], "code": "G", "label": "Ground"},
        )
        assert other_floor.status_code == 201, other_floor.text
        outsider = admin_client.post(
            f"{inventory_url(project_id)}/units",
            json=unit_payload(
                other_floor.json()["id"],
                unit_number="201",
                unit_reference="B2-201",
                sequence=9,
            ),
        )
        assert outsider.status_code == 201, outsider.text
        approve_areas(admin_client, project_id, outsider.json()["id"], area_types)

        version_id = create_version(finance_client, project_id)
        cover_required_pools(finance_client, project_id, version_id)
        assert (
            add_pool(
                finance_client,
                project_id,
                version_id,
                pool_number="HARD-02",
                category="hard",
                amount="90.00",
                scope_kind="building",
                building_id=building_id,
            ).status_code
            == 201
        )
        preview = calculate(finance_client, project_id, version_id)
        scoped = next(row for row in preview["pools"] if row["pool_number"] == "HARD-02")
        assert scoped["eligible_units"] == 2
        assert scoped["allocated_total"] == "90.00"

        scoped_rows = allocations(finance_client, project_id, version_id, pool="HARD-02")
        assert "B2-201" not in {row["unit_reference"] for row in scoped_rows}
        project_wide = allocations(finance_client, project_id, version_id, pool="LAND-01")
        assert "B2-201" in {row["unit_reference"] for row in project_wide}

    def test_a_phase_from_another_project_is_refused(
        self,
        finance_client: TestClient,
        admin_client: TestClient,
        db: Session,
        project_id: str,
        priced_pair: tuple[str, str],
    ) -> None:
        """Not merely filtered by identifier — the parentage is proved."""
        del priced_pair
        from app.modules.inventory.models import Phase

        version_id = create_version(finance_client, project_id)
        foreign = db.scalars(select(Phase.id).where(Phase.project_id != project_id)).first()
        response = add_pool(
            finance_client,
            project_id,
            version_id,
            pool_number="HARD-08",
            category="hard",
            amount="10.00",
            scope_kind="phase",
            phase_id=str(foreign) if foreign else "00000000-0000-0000-0000-000000000000",
        )
        assert response.status_code == 404
        del admin_client
