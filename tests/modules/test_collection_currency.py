"""Money of different denominations is never added together.

A project can sell in more than one currency. The moment a screen shows one
"outstanding" figure for such a project, that figure was produced by adding
unlike numbers and labelling the result with whichever currency happened to
come first — and it will be wrong by however much the exchange rate is, on a
strip an executive reads at a glance.

Converting instead would need an FX model: rates, as-at dates, which rate for a
receivable and which for cash already received, and what happens when the rate
moves between the two. PR-MVP-07 deliberately does not invent that. So the
project strip groups by ``currency_id`` and offers no total across them, and
these tests hold that line at the contract, not only in the arithmetic.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.modules.conftest import (
    SETTINGS,
    allocate,
    collections_url,
    confirm_receipt,
    governing_installments,
    record_receipt,
)


@pytest.fixture
def dollar_id(admin_client: TestClient) -> str:
    """A second currency on the same project."""
    response = admin_client.post(
        f"{SETTINGS}/currencies", json={"code": "USD", "name": "United States dollar"}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.fixture
def two_currencies(
    collections_client: TestClient,
    finance_client: TestClient,
    db: Session,
    project_id: str,
    collecting_sale: str,
    other_phase_plan: dict[str, str],
    dollar_id: str,
    currency_id: str,
) -> dict[str, str]:
    """Two live accounts on one project, billed in different denominations.

    The second contract's frozen currency is moved directly, because there is
    no route that re-denominates a signed contract and there should not be —
    what is being arranged here is a project that sells in two currencies,
    which is an ordinary thing for a developer to do and an awkward thing to
    build twice through pricing.

    Then 100 of the first and 50 of the second are collected, so the strip has
    the two numbers the report must keep apart.
    """
    second = other_phase_plan["sale_id"]
    db.execute(
        text("UPDATE sale_contracts SET currency_id = :c WHERE id = :s"),
        {"c": dollar_id, "s": second},
    )
    db.commit()

    for sale_id, amount in ((collecting_sale, "100.00"), (second, "50.00")):
        rows = governing_installments(collections_client, project_id, sale_id)
        receipt = record_receipt(collections_client, project_id, sale_id, amount).json()
        assert confirm_receipt(finance_client, project_id, receipt["id"]).status_code == 200
        assert (
            allocate(
                collections_client, project_id, receipt["id"], rows[0]["installment_id"], amount
            ).status_code
            == 201
        )
    return {
        "dinar_sale": collecting_sale,
        "dollar_sale": second,
        "dinar": currency_id,
        "dollar": dollar_id,
    }


class TestTheProjectStrip:
    """Given a project selling in two currencies, when the strip is read."""

    def _strip(self, client: TestClient, project_id: str) -> dict:
        response = client.get(f"{collections_url(project_id)}/summary")
        assert response.status_code == 200, response.text
        return response.json()

    def test_there_is_no_project_wide_money_field_at_all(
        self,
        collections_client: TestClient,
        project_id: str,
        two_currencies: dict[str, str],
    ) -> None:
        """The strongest form of the guarantee: the field does not exist.

        A total that is merely *documented* as single-currency is one refactor
        away from being wrong. Absent from the contract, it cannot be read by a
        screen, a script or a spreadsheet.
        """
        del two_currencies
        strip = self._strip(collections_client, project_id)
        for banned in (
            "outstanding_total",
            "due_total",
            "overdue_total",
            "unapplied_cash",
            "confirmed_receipts_total",
            "buckets",
        ):
            assert banned not in strip, banned
        assert set(strip) == {
            "as_of",
            "accounts",
            "accounts_overdue",
            "accounts_disputed",
            "accounts_cleared",
            "currencies",
        }

    def test_a_hundred_dinars_and_fifty_dollars_stay_apart(
        self,
        collections_client: TestClient,
        project_id: str,
        two_currencies: dict[str, str],
    ) -> None:
        """Never one figure of 150, whatever the two amounts happen to be."""
        strip = self._strip(collections_client, project_id)
        by_currency = {c["currency_id"]: c for c in strip["currencies"]}
        assert set(by_currency) == {two_currencies["dinar"], two_currencies["dollar"]}

        dinars = by_currency[two_currencies["dinar"]]
        dollars = by_currency[two_currencies["dollar"]]
        assert Decimal(dinars["confirmed_receipts_total"]) == Decimal("100.00")
        assert Decimal(dollars["confirmed_receipts_total"]) == Decimal("50.00")
        assert dinars["accounts"] == 1
        assert dollars["accounts"] == 1

        combined = Decimal(dinars["confirmed_receipts_total"]) + Decimal(
            dollars["confirmed_receipts_total"]
        )
        assert combined == Decimal("150.00")
        assert not any(
            Decimal(c["confirmed_receipts_total"]) == combined for c in strip["currencies"]
        )

    def test_the_counts_are_project_wide_because_they_are_not_money(
        self,
        collections_client: TestClient,
        project_id: str,
        two_currencies: dict[str, str],
    ) -> None:
        """Four overdue accounts are four, whatever they are billed in."""
        del two_currencies
        strip = self._strip(collections_client, project_id)
        assert strip["accounts"] == 2
        assert sum(c["accounts"] for c in strip["currencies"]) == strip["accounts"]

    def test_each_denominations_bands_partition_its_own_outstanding(
        self,
        collections_client: TestClient,
        project_id: str,
        two_currencies: dict[str, str],
    ) -> None:
        """A band that mixed currencies would be the same bug, hidden lower down."""
        del two_currencies
        strip = self._strip(collections_client, project_id)
        assert len(strip["currencies"]) == 2
        for totals in strip["currencies"]:
            banded = sum(Decimal(v) for v in totals["buckets"].values())
            assert banded == Decimal(totals["outstanding_total"])

    def test_one_currency_projects_still_read_naturally(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
    ) -> None:
        """The common case is one denomination, and it is one row."""
        del collecting_sale
        strip = self._strip(collections_client, project_id)
        assert len(strip["currencies"]) == 1
        assert strip["currencies"][0]["accounts"] == strip["accounts"]
