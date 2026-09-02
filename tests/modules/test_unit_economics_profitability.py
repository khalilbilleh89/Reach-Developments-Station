"""What a unit earns, on the basis its commercial state calls for.

The distinction this file exists to hold is the one the whole module is built
around: an unsold unit is analysed on today's approved price and today's cost
basis, and a sold one on the terms it was actually sold at and the cost basis
that governed then. Activating a new basis tomorrow moves the first and must
never move the second.

Everything else here follows from refusing to fabricate. A unit with no price,
no cost basis or a revenue in another currency reports why it has no margin
rather than reporting a margin of zero, because zero is a number people act on.

Histories are arranged by moving lifecycle dates the way the collections suite
does. What is simulated is the passage of time, never a figure.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.modules.conftest import (
    add_pool,
    cover_required_pools,
    create_version,
    economics_url,
    govern,
    pricing_url,
    sales_url,
    today,
    unit_economics,
)


def _stamp(db: Session, table: str, row_id: str, column: str, value: object) -> None:
    """Move one business date so a test has a history to read.

    A contract signed today cannot be made to sit inside a historical cost
    window by driving the API — contract dates are stamped when the contract is
    drafted. So the date is moved here, against the same PostgreSQL the code
    reads, and every assertion afterwards goes through the ordinary route.
    """
    db.execute(
        text(f"UPDATE {table} SET {column} = :value WHERE id = :row_id"),
        {"value": value, "row_id": row_id},
    )
    db.commit()


@pytest.fixture
def governed_basis(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    priced_pair: tuple[str, str],
) -> str:
    """One active cost basis: 100,000 of hard cost split evenly across two units."""
    del priced_pair
    version_id = create_version(finance_client, project_id, effective_from="2026-01-01")
    cover_required_pools(finance_client, project_id, version_id, hard="100000.00")
    assert govern(finance_client, cfo_client, project_id, version_id).status_code == 200
    return version_id


class TestAnUnsoldUnit:
    """Given a unit nobody has bought, when its economics are read."""

    def test_it_uses_the_current_approved_price(
        self,
        finance_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        governed_basis: str,
    ) -> None:
        del governed_basis
        first, _second = priced_pair
        row = unit_economics(finance_client, project_id, first)
        assert row["basis"] == "forecast"
        assert row["revenue_source"] == "approved_price"
        assert row["revenue"] == "165000.00"
        assert row["hard_cost"] == "50000.00"
        assert row["profitability_status"] == "ready"

    def test_a_new_approved_price_moves_its_economics(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        admin_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        governed_basis: str,
        area_types: dict[str, str],
    ) -> None:
        """An unsold unit is a forecast, so a repricing is supposed to move it."""
        del governed_basis, admin_client, area_types
        first, _second = priced_pair
        before = unit_economics(finance_client, project_id, first)

        draft = finance_client.post(
            f"{pricing_url(project_id)}/units/{first}/price-versions",
            json={
                "internal_rate_override": "1800.00",
                "override_reason": "Market rate reviewed upward",
            },
        )
        assert draft.status_code == 201, draft.text
        base = f"{pricing_url(project_id)}/price-versions/{draft.json()['id']}"
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200
        assert (
            cfo_client.post(f"{base}/approve", json={"reason": "Upgrade added"}).status_code == 200
        )
        assert cfo_client.post(f"{base}/activate").status_code == 200

        after = unit_economics(finance_client, project_id, first)
        assert Decimal(after["revenue"]) > Decimal(before["revenue"])
        assert after["revenue_source_id"] != before["revenue_source_id"]

    def test_a_unit_with_no_price_reports_why_rather_than_zero(
        self,
        finance_client: TestClient,
        admin_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        governed_basis: str,
        floor_id: str,
    ) -> None:
        del priced_pair, governed_basis
        from tests.modules.conftest import inventory_url, unit_payload

        created = admin_client.post(
            f"{inventory_url(project_id)}/units",
            json=unit_payload(floor_id, unit_number="199", unit_reference="B1-199", sequence=19),
        )
        assert created.status_code == 201, created.text
        row = unit_economics(finance_client, project_id, created.json()["id"])
        assert row["profitability_status"] == "missing_revenue"
        assert row["revenue"] is None
        assert row["margin_fraction"] is None
        assert row["profit_after_finance"] is None


class TestASoldUnit:
    """Given a live contract, when the unit's economics are read."""

    def test_it_uses_the_frozen_contract_price_not_the_list_price(
        self,
        finance_client: TestClient,
        sales_ops_client: TestClient,
        project_id: str,
        active_sale: str,
        priced_pair: tuple[str, str],
        governed_basis: str,
    ) -> None:
        del governed_basis, priced_pair
        sale = sales_ops_client.get(f"{sales_url(project_id)}/contracts/{active_sale}").json()
        unit_id = sale["sale"]["unit_id"]
        row = unit_economics(finance_client, project_id, unit_id)
        assert row["basis"] == "sold"
        assert row["revenue_source"] == "sale_contract"
        assert row["revenue_source_id"] == active_sale
        assert row["revenue"] == sale["sale"]["net_contract_price_ex_tax"]

    def test_a_later_list_price_rise_does_not_move_it(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        sales_ops_client: TestClient,
        project_id: str,
        active_sale: str,
        priced_pair: tuple[str, str],
        governed_basis: str,
    ) -> None:
        """Sold at 165,000 stays 165,000 even when the list says 210,000."""
        del governed_basis, priced_pair
        sale = sales_ops_client.get(f"{sales_url(project_id)}/contracts/{active_sale}").json()
        unit_id = sale["sale"]["unit_id"]
        before = unit_economics(finance_client, project_id, unit_id)

        draft = finance_client.post(
            f"{pricing_url(project_id)}/units/{unit_id}/price-versions",
            json={
                "internal_rate_override": "2100.00",
                "override_reason": "Market rate reviewed upward",
            },
        )
        assert draft.status_code == 201, draft.text
        base = f"{pricing_url(project_id)}/price-versions/{draft.json()['id']}"
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200
        assert (
            cfo_client.post(f"{base}/approve", json={"reason": "Market moved"}).status_code == 200
        )
        assert cfo_client.post(f"{base}/activate").status_code == 200

        after = unit_economics(finance_client, project_id, unit_id)
        assert after["revenue"] == before["revenue"]
        assert after["revenue_source"] == "sale_contract"


class TestTheAllocationFreeze:
    """Given a sale under one basis, when a later basis is activated."""

    @pytest.fixture
    def two_bases(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        active_sale: str,
        priced_pair: tuple[str, str],
    ) -> tuple[str, str]:
        """V1 from January at 100,000; the sale signed in February; V2 today at 200,000.

        The sale's dates are the ``active_sale`` fixture's own: buyer signed
        3 February, seller 4 February. Nothing here stamps ``contract_date``,
        because that is not the date the freeze turns on.
        """
        del priced_pair
        first = create_version(finance_client, project_id, effective_from="2026-01-01")
        cover_required_pools(finance_client, project_id, first, hard="100000.00")
        assert govern(finance_client, cfo_client, project_id, first).status_code == 200

        second = create_version(
            finance_client,
            project_id,
            effective_from=today(),
            reason="Construction forecast raised",
        )
        cover_required_pools(finance_client, project_id, second, hard="200000.00")
        assert govern(finance_client, cfo_client, project_id, second).status_code == 200
        return first, second

    def test_the_sold_unit_keeps_the_basis_that_governed_its_contract(
        self,
        finance_client: TestClient,
        sales_ops_client: TestClient,
        project_id: str,
        active_sale: str,
        two_bases: tuple[str, str],
    ) -> None:
        first, _second = two_bases
        sale = sales_ops_client.get(f"{sales_url(project_id)}/contracts/{active_sale}").json()
        row = unit_economics(finance_client, project_id, sale["sale"]["unit_id"])
        assert row["allocation_version_id"] == first
        assert row["allocation_version_number"] == 1
        assert row["allocation_effective_from"] == "2026-01-01"
        assert row["hard_cost"] == "50000.00"

    def test_the_unsold_unit_moves_to_the_new_basis(
        self,
        finance_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        two_bases: tuple[str, str],
    ) -> None:
        _first, second = two_bases
        _one, unsold = priced_pair
        row = unit_economics(finance_client, project_id, unsold)
        assert row["allocation_version_id"] == second
        assert row["allocation_effective_from"] == today()
        assert row["hard_cost"] == "100000.00"

    def test_the_two_units_therefore_disagree_and_should(
        self,
        finance_client: TestClient,
        sales_ops_client: TestClient,
        project_id: str,
        active_sale: str,
        priced_pair: tuple[str, str],
        two_bases: tuple[str, str],
    ) -> None:
        """Different cost bases, different hard cost. That is the feature."""
        del two_bases
        _one, unsold = priced_pair
        sale = sales_ops_client.get(f"{sales_url(project_id)}/contracts/{active_sale}").json()
        sold_row = unit_economics(finance_client, project_id, sale["sale"]["unit_id"])
        unsold_row = unit_economics(finance_client, project_id, unsold)
        assert sold_row["hard_cost"] != unsold_row["hard_cost"]


class TestMissingCostBasis:
    """Given a sale that predates every cost basis, when its economics are read."""

    def test_it_refuses_to_apply_a_later_basis_retrospectively(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        sales_ops_client: TestClient,
        db: Session,
        project_id: str,
        active_sale: str,
        priced_pair: tuple[str, str],
    ) -> None:
        """A basis starting after the signatures is not what the contract was signed against.

        The ``active_sale`` fixture signs on 3 and 4 February, so a basis
        effective 1 March covers no part of this deal's life.
        """
        del priced_pair, db
        version_id = create_version(finance_client, project_id, effective_from="2026-03-01")
        cover_required_pools(finance_client, project_id, version_id, hard="100000.00")
        assert govern(finance_client, cfo_client, project_id, version_id).status_code == 200

        sale = sales_ops_client.get(f"{sales_url(project_id)}/contracts/{active_sale}").json()
        row = unit_economics(finance_client, project_id, sale["sale"]["unit_id"])
        assert row["profitability_status"] == "missing_cost_basis"
        assert row["allocation_version_id"] is None
        assert row["hard_cost"] == "0.00"
        assert row["margin_fraction"] is None

    def test_an_opening_baseline_gives_an_existing_sale_a_cost_basis(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        sales_ops_client: TestClient,
        db: Session,
        project_id: str,
        active_sale: str,
        priced_pair: tuple[str, str],
    ) -> None:
        """The reason the first version may be back-dated at all."""
        del priced_pair, db
        version_id = create_version(
            finance_client,
            project_id,
            effective_from="2025-01-01",
            reason="Opening baseline for contracts signed before this module existed",
        )
        cover_required_pools(finance_client, project_id, version_id, hard="100000.00")
        assert govern(finance_client, cfo_client, project_id, version_id).status_code == 200

        sale = sales_ops_client.get(f"{sales_url(project_id)}/contracts/{active_sale}").json()
        row = unit_economics(finance_client, project_id, sale["sale"]["unit_id"])
        assert row["profitability_status"] == "ready"
        assert row["allocation_version_number"] == 1
        assert row["hard_cost"] == "50000.00"


class TestUnitCosts:
    """Given costs attributable to one unit, when they are recorded and read."""

    def test_a_forecast_cost_reduces_an_unsold_unit(
        self,
        finance_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        governed_basis: str,
    ) -> None:
        del governed_basis
        first, _second = priced_pair
        before = unit_economics(finance_client, project_id, first)
        response = finance_client.post(
            f"{economics_url(project_id)}/units/{first}/costs",
            json={
                "cost_type": "furniture_appliance",
                "basis": "forecast",
                "amount": "8000.00",
                "effective_date": "2026-04-01",
            },
        )
        assert response.status_code == 201, response.text
        assert response.json()["cost_class"] == "direct"

        after = unit_economics(finance_client, project_id, first)
        assert after["direct_cost"] == "8000.00"
        assert Decimal(after["profit_after_finance"]) == Decimal(
            before["profit_after_finance"]
        ) - Decimal("8000.00")

    def test_a_selling_cost_lands_below_gross_profit(
        self,
        finance_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        governed_basis: str,
    ) -> None:
        """A commission does not change what the building cost to build."""
        del governed_basis
        first, _second = priced_pair
        before = unit_economics(finance_client, project_id, first)
        response = finance_client.post(
            f"{economics_url(project_id)}/units/{first}/costs",
            json={
                "cost_type": "sales_commission",
                "basis": "forecast",
                "amount": "3000.00",
                "effective_date": "2026-04-01",
            },
        )
        assert response.status_code == 201, response.text
        assert response.json()["cost_class"] == "variable_selling"

        after = unit_economics(finance_client, project_id, first)
        assert after["gross_profit"] == before["gross_profit"]
        assert after["variable_selling_cost"] == "3000.00"
        assert Decimal(after["contribution_profit"]) == Decimal(
            before["contribution_profit"]
        ) - Decimal("3000.00")

    def test_a_reversed_cost_stops_counting_and_stays_on_the_record(
        self,
        finance_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        governed_basis: str,
    ) -> None:
        del governed_basis
        first, _second = priced_pair
        created = finance_client.post(
            f"{economics_url(project_id)}/units/{first}/costs",
            json={
                "cost_type": "finishes",
                "basis": "forecast",
                "amount": "2500.00",
                "effective_date": "2026-04-01",
            },
        )
        assert created.status_code == 201, created.text
        cost_id = created.json()["id"]
        assert unit_economics(finance_client, project_id, first)["direct_cost"] == "2500.00"

        reversed_cost = finance_client.post(
            f"{economics_url(project_id)}/unit-costs/{cost_id}/reverse",
            json={"reason": "Recorded against the wrong unit"},
        )
        assert reversed_cost.status_code == 200, reversed_cost.text
        assert reversed_cost.json()["status"] == "reversed"
        assert unit_economics(finance_client, project_id, first)["direct_cost"] == "0.00"

        listed = finance_client.get(
            f"{economics_url(project_id)}/unit-costs", params={"unit_id": first}
        ).json()
        assert [row["id"] for row in listed] == [cost_id]

    def test_a_reversal_needs_a_reason_and_there_is_no_delete(
        self,
        finance_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        governed_basis: str,
    ) -> None:
        del governed_basis
        first, _second = priced_pair
        created = finance_client.post(
            f"{economics_url(project_id)}/units/{first}/costs",
            json={
                "cost_type": "marketing",
                "basis": "forecast",
                "amount": "500.00",
                "effective_date": "2026-04-01",
            },
        ).json()
        blank = finance_client.post(
            f"{economics_url(project_id)}/unit-costs/{created['id']}/reverse",
            json={"reason": "   "},
        )
        assert blank.status_code == 422
        assert (
            finance_client.delete(
                f"{economics_url(project_id)}/unit-costs/{created['id']}"
            ).status_code
            == 404
        )

    def test_an_actual_cost_must_name_the_sale_it_was_incurred_on(
        self,
        finance_client: TestClient,
        project_id: str,
        active_sale: str,
        priced_pair: tuple[str, str],
        governed_basis: str,
        sales_ops_client: TestClient,
    ) -> None:
        del governed_basis, priced_pair
        sale = sales_ops_client.get(f"{sales_url(project_id)}/contracts/{active_sale}").json()
        unit_id = sale["sale"]["unit_id"]
        response = finance_client.post(
            f"{economics_url(project_id)}/units/{unit_id}/costs",
            json={
                "cost_type": "sales_commission",
                "basis": "actual",
                "amount": "4000.00",
                "effective_date": "2026-04-01",
            },
        )
        assert response.status_code == 422
        assert "which contract" in response.json()["detail"]

    def test_a_sold_unit_counts_its_actual_costs_and_ignores_the_forecast(
        self,
        finance_client: TestClient,
        sales_ops_client: TestClient,
        project_id: str,
        active_sale: str,
        priced_pair: tuple[str, str],
        governed_basis: str,
    ) -> None:
        """8,000 forecast and 9,500 actual is 9,500, never 17,500."""
        del governed_basis, priced_pair
        sale = sales_ops_client.get(f"{sales_url(project_id)}/contracts/{active_sale}").json()
        unit_id = sale["sale"]["unit_id"]
        base = f"{economics_url(project_id)}/units/{unit_id}/costs"
        assert (
            finance_client.post(
                base,
                json={
                    "cost_type": "finishes",
                    "basis": "forecast",
                    "amount": "8000.00",
                    "effective_date": "2026-03-01",
                },
            ).status_code
            == 201
        )
        actual = finance_client.post(
            base,
            json={
                "cost_type": "finishes",
                "basis": "actual",
                "amount": "9500.00",
                "effective_date": "2026-04-01",
                "sale_contract_id": active_sale,
            },
        )
        assert actual.status_code == 201, actual.text
        row = unit_economics(finance_client, project_id, unit_id)
        assert row["direct_cost"] == "9500.00"


class TestFrozenSellerCosts:
    """Given a contract with seller-borne costs, when profit is layered."""

    @pytest.fixture
    def discounted_sale(
        self,
        sales_ops_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        reservation_id: str,
        legal_client: TestClient,
    ) -> str:
        """A deal carrying a package cost and a financing subsidy.

        Both are seller costs in PR-MVP-05's mapping, and they land on different
        layers here: a furniture package is a commercial cost, a subsidised rate
        is a finance cost.
        """
        for adjustment_type, amount in (
            ("package_cost", "6000.00"),
            ("financing_subsidy", "4000.00"),
        ):
            response = sales_ops_client.post(
                f"{sales_url(project_id)}/reservations/{reservation_id}/adjustments",
                json={"adjustment_type": adjustment_type, "amount": amount, "reason": "Agreed"},
            )
            assert response.status_code == 201, response.text
        base = f"{sales_url(project_id)}/reservations/{reservation_id}"
        assert (
            sales_ops_client.post(
                f"{base}/confirm-deposit", json={"evidence_reference": "BANK-REF-9"}
            ).status_code
            == 200
        )
        assert sales_ops_client.post(f"{base}/activate", json={}).status_code == 200
        created = sales_ops_client.post(
            f"{sales_url(project_id)}/contracts",
            json={"reservation_id": reservation_id, "spa_number": "SPA-0009"},
        )
        assert created.status_code == 201, created.text
        sale_id = created.json()["sale"]["id"]
        assert (
            sales_ops_client.post(
                f"{sales_url(project_id)}/contracts/{sale_id}/submit", json={}
            ).status_code
            == 200
        )
        from tests.modules.conftest import record_legal

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
        del cfo_client
        return sale_id

    def test_the_two_kinds_of_seller_cost_land_on_different_layers(
        self,
        finance_client: TestClient,
        sales_ops_client: TestClient,
        project_id: str,
        discounted_sale: str,
        priced_pair: tuple[str, str],
        governed_basis: str,
    ) -> None:
        del governed_basis, priced_pair
        sale = sales_ops_client.get(f"{sales_url(project_id)}/contracts/{discounted_sale}").json()
        row = unit_economics(finance_client, project_id, sale["sale"]["unit_id"])
        assert row["seller_cost"] == "6000.00"
        assert row["deal_finance_cost"] == "4000.00"
        assert row["commercial_cost"] == "6000.00"
        assert row["finance_cost"] == "4000.00"

    def test_a_seller_cost_is_not_subtracted_twice(
        self,
        finance_client: TestClient,
        sales_ops_client: TestClient,
        project_id: str,
        discounted_sale: str,
        priced_pair: tuple[str, str],
        governed_basis: str,
    ) -> None:
        """Revenue is the net contract price. The contract's own effective net
        revenue has already had these costs taken off, so using it here and
        subtracting them again would understate the margin and look consistent.
        """
        del governed_basis, priced_pair
        sale = sales_ops_client.get(f"{sales_url(project_id)}/contracts/{discounted_sale}").json()[
            "sale"
        ]
        row = unit_economics(finance_client, project_id, sale["unit_id"])
        assert row["revenue"] == sale["net_contract_price_ex_tax"]
        assert Decimal(row["revenue"]) - Decimal(row["seller_cost"]) - Decimal(
            row["deal_finance_cost"]
        ) == Decimal(sale["effective_net_revenue_snapshot"])


class TestCurrencyMismatch:
    """Given revenue in one currency and cost in another, when profit is asked for."""

    def test_no_margin_is_produced_and_the_reason_is_stated(
        self,
        finance_client: TestClient,
        admin_client: TestClient,
        sales_ops_client: TestClient,
        db: Session,
        project_id: str,
        active_sale: str,
        priced_pair: tuple[str, str],
        governed_basis: str,
    ) -> None:
        """No route produces a cross-currency sale, and the guard must hold anyway.

        There is no exchange rate anywhere in this platform, so the only honest
        answer is both figures in their own denomination and no arithmetic
        joining them.
        """
        del governed_basis, priced_pair
        other = admin_client.post(
            "/api/v1/settings/currencies",
            json={"code": "USD", "name": "US dollar", "minor_units": 2},
        )
        assert other.status_code == 201, other.text
        _stamp(db, "sale_contracts", active_sale, "currency_id", other.json()["id"])

        sale = sales_ops_client.get(f"{sales_url(project_id)}/contracts/{active_sale}").json()
        row = unit_economics(finance_client, project_id, sale["sale"]["unit_id"])
        assert row["profitability_status"] == "currency_mismatch"
        assert row["revenue"] is not None, "the revenue is still shown, in its own currency"
        assert row["revenue_currency_id"] == other.json()["id"]
        assert row["cost_currency_id"] != other.json()["id"]
        assert row["hard_cost"] == "50000.00", "and so is the cost, in the project's"
        assert row["profit_after_finance"] is None
        assert row["margin_fraction"] is None
        assert row["return_on_cost_fraction"] is None

    def test_the_project_summary_reports_the_exclusion_rather_than_hiding_it(
        self,
        finance_client: TestClient,
        admin_client: TestClient,
        db: Session,
        project_id: str,
        active_sale: str,
        priced_pair: tuple[str, str],
        governed_basis: str,
    ) -> None:
        del governed_basis, priced_pair
        other = admin_client.post(
            "/api/v1/settings/currencies",
            json={"code": "USD", "name": "US dollar", "minor_units": 2},
        )
        _stamp(db, "sale_contracts", active_sale, "currency_id", other.json()["id"])

        summary = finance_client.get(f"{economics_url(project_id)}/summary").json()
        assert summary["currency_mismatch_count"] == 1
        assert summary["unit_count"] == 2
        assert summary["comparable_unit_count"] == 1


class TestTheProjectSummary:
    """Given a mixture of units, when the project totals are taken."""

    def test_the_totals_equal_the_rows_and_the_ratios_are_weighted(
        self,
        finance_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        governed_basis: str,
    ) -> None:
        del priced_pair, governed_basis
        rows = finance_client.get(f"{economics_url(project_id)}/units").json()
        summary = finance_client.get(f"{economics_url(project_id)}/summary").json()

        ready = [row for row in rows if row["profitability_status"] == "ready"]
        assert summary["comparable_unit_count"] == len(ready)
        assert Decimal(summary["revenue_total"]) == sum(Decimal(row["revenue"]) for row in ready)
        assert Decimal(summary["profit_total"]) == sum(
            Decimal(row["profit_after_finance"]) for row in ready
        )
        assert Decimal(summary["margin_fraction"]) == (
            Decimal(summary["profit_total"]) / Decimal(summary["revenue_total"])
        ).quantize(Decimal("0.000001"))

    def test_it_counts_sold_unsold_and_incomplete_units_separately(
        self,
        finance_client: TestClient,
        project_id: str,
        active_sale: str,
        priced_pair: tuple[str, str],
        governed_basis: str,
    ) -> None:
        del active_sale, priced_pair, governed_basis
        summary = finance_client.get(f"{economics_url(project_id)}/summary").json()
        assert summary["sold_count"] == 1
        assert summary["unsold_count"] == 1
        assert summary["incomplete_count"] == 0

    def test_a_loss_making_unit_is_counted_and_not_clamped(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
    ) -> None:
        """Hard cost of a million across two units nobody could sell for that."""
        first, _second = priced_pair
        version_id = create_version(finance_client, project_id, effective_from="2026-01-01")
        cover_required_pools(finance_client, project_id, version_id, hard="1000000.00")
        assert govern(finance_client, cfo_client, project_id, version_id).status_code == 200

        row = unit_economics(finance_client, project_id, first)
        assert Decimal(row["profit_after_finance"]) < 0
        assert Decimal(row["margin_fraction"]) < 0
        summary = finance_client.get(f"{economics_url(project_id)}/summary").json()
        assert summary["negative_profit_count"] == 2
        assert Decimal(summary["profit_total"]) < 0


class TestTheSaleSpecificRead:
    """Given a cancelled contract, when somebody asks what it earned."""

    def test_a_cancelled_sale_keeps_its_economics(
        self,
        finance_client: TestClient,
        sales_ops_client: TestClient,
        project_id: str,
        active_sale: str,
        priced_pair: tuple[str, str],
        governed_basis: str,
    ) -> None:
        """Deleting the economics of a failed deal is how a business stops learning."""
        del governed_basis, priced_pair
        opened = sales_ops_client.post(
            f"{sales_url(project_id)}/contracts/{active_sale}/cancellation",
            json={
                "initiated_by_party": "buyer",
                "initiation_date": "2026-05-01",
                "reason": "Buyer withdrew",
            },
        )
        assert opened.status_code == 201, opened.text

        response = finance_client.get(f"{economics_url(project_id)}/sales/{active_sale}")
        assert response.status_code == 200, response.text
        economics = response.json()["economics"]
        assert economics["basis"] == "sold"
        assert economics["revenue_source_id"] == active_sale
        assert economics["profitability_status"] == "ready"

    def test_the_waterfall_is_returned_in_the_order_it_is_subtracted(
        self,
        finance_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        governed_basis: str,
    ) -> None:
        del governed_basis
        first, _second = priced_pair
        detail = finance_client.get(f"{economics_url(project_id)}/units/{first}").json()
        keys = [step["key"] for step in detail["waterfall"]]
        assert keys == [
            "revenue",
            "land_cost",
            "hard_cost",
            "soft_cost",
            "direct_cost",
            "gross_profit",
            "variable_selling_cost",
            "seller_cost",
            "contribution_profit",
            "finance_cost",
            "profit_after_finance",
        ]
        amounts = {step["key"]: Decimal(step["amount"]) for step in detail["waterfall"]}
        assert (
            amounts["revenue"]
            - amounts["land_cost"]
            - amounts["hard_cost"]
            - amounts["soft_cost"]
            - amounts["direct_cost"]
            == amounts["gross_profit"]
        )


class TestFinanceTreatment:
    """Given a basis that excludes finance cost, when a unit is read."""

    def test_an_allocated_finance_pool_reaches_the_finance_layer(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
    ) -> None:
        first, _second = priced_pair
        version_id = create_version(
            finance_client, project_id, effective_from="2026-01-01", finance_treatment="allocated"
        )
        cover_required_pools(finance_client, project_id, version_id, hard="100000.00")
        assert (
            add_pool(
                finance_client,
                project_id,
                version_id,
                pool_number="FIN-01",
                category="finance",
                amount="20000.00",
            ).status_code
            == 201
        )
        assert govern(finance_client, cfo_client, project_id, version_id).status_code == 200

        row = unit_economics(finance_client, project_id, first)
        assert row["allocated_finance_cost"] == "10000.00"
        assert row["finance_cost"] == "10000.00"
        assert Decimal(row["contribution_profit"]) - Decimal("10000.00") == Decimal(
            row["profit_after_finance"]
        )

    def test_an_excluded_treatment_reports_no_finance_cost_at_all(
        self,
        finance_client: TestClient,
        project_id: str,
        priced_pair: tuple[str, str],
        governed_basis: str,
    ) -> None:
        del governed_basis
        first, _second = priced_pair
        row = unit_economics(finance_client, project_id, first)
        assert row["allocated_finance_cost"] == "0.00"
        assert row["contribution_profit"] == row["profit_after_finance"]
