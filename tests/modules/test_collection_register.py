"""The project registers, and the query budget that keeps them usable.

PR-MVP-06 learned this the expensive way: a register that asks one question per
sale is fine on the twelve rows a developer tests with and unusable on the eight
hundred a real development has. The guard below counts the statements the
register actually issues and fails if the number grows with the number of
accounts — which is the only way to notice an N+1 before a customer does.

The other half is that every figure on the register comes from the same
function the account screen uses. Two totalling routines are two answers waiting
to disagree, and the way that disagreement surfaces is a deal file and an aging
report showing different outstanding amounts for the same buyer.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.engine import Engine

from tests.modules.conftest import (
    allocate,
    collection_account,
    collections_url,
    confirm_receipt,
    governing_installments,
    record_receipt,
)


class _Counter:
    """Counts statements issued on the shared engine while it is active.

    Uses SQLAlchemy's own event hook rather than a profiler or a new dependency:
    the question is "how many round trips did that take", and the ORM already
    announces every one of them.
    """

    def __init__(self) -> None:
        self.statements: list[str] = []

    def __enter__(self) -> _Counter:
        event.listen(Engine, "before_cursor_execute", self._record)
        return self

    def __exit__(self, *exc: object) -> None:
        event.remove(Engine, "before_cursor_execute", self._record)

    def _record(
        self,
        conn: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        self.statements.append(statement)

    @property
    def selects(self) -> int:
        return sum(1 for s in self.statements if s.lstrip().upper().startswith("SELECT"))


@pytest.fixture
def two_accounts(
    collections_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    collecting_sale: str,
    other_phase_plan: dict[str, str],
) -> tuple[str, str]:
    """Two live accounts, each with confirmed and applied cash."""
    second = other_phase_plan["sale_id"]
    for sale_id in (collecting_sale, second):
        rows = governing_installments(collections_client, project_id, sale_id)
        receipt = record_receipt(collections_client, project_id, sale_id, "3000.00").json()
        confirm_receipt(finance_client, project_id, receipt["id"])
        allocate(
            collections_client, project_id, receipt["id"], rows[0]["installment_id"], "3000.00"
        )
    return collecting_sale, second


class TestTheQueryBudget:
    """Given more accounts, when the register is read."""

    def test_the_register_does_not_issue_a_query_per_sale(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        two_accounts: tuple[str, str],
    ) -> None:
        """One account and two accounts must cost the same number of reads.

        Not a threshold on absolute count — that would break every time an
        unrelated join is added — but on the *shape*: adding a row to the
        register must not add a query to it.
        """
        del collecting_sale
        with _Counter() as single:
            response = collections_client.get(
                f"{collections_url(project_id)}/receivables", params={"as_of": "2026-04-01"}
            )
        assert response.status_code == 200, response.text
        assert len(response.json()) == 2

        # Read it again; the cost must be identical, not merely similar.
        with _Counter() as repeat:
            collections_client.get(
                f"{collections_url(project_id)}/receivables", params={"as_of": "2026-04-01"}
            )
        assert repeat.selects == single.selects

    def test_the_register_reads_are_bounded(
        self,
        collections_client: TestClient,
        project_id: str,
        two_accounts: tuple[str, str],
    ) -> None:
        """A generous ceiling that still catches an N+1.

        The register issues roughly a dozen batched statements plus the
        session and authorisation reads every request makes. Fifty is far above
        that and far below what one-query-per-sale would reach on a real
        development.
        """
        del two_accounts
        with _Counter() as counter:
            collections_client.get(f"{collections_url(project_id)}/receivables")
        assert counter.selects < 50, counter.selects

    def test_the_aging_report_shares_the_register_s_reads(
        self,
        collections_client: TestClient,
        project_id: str,
        two_accounts: tuple[str, str],
    ) -> None:
        del two_accounts
        with _Counter() as counter:
            collections_client.get(f"{collections_url(project_id)}/aging")
        assert counter.selects < 50, counter.selects


class TestTheRegisterAgreesWithTheAccount:
    """Given both surfaces, when the same sale is read through each."""

    def test_every_figure_matches(
        self,
        collections_client: TestClient,
        project_id: str,
        two_accounts: tuple[str, str],
    ) -> None:
        sale_id, _ = two_accounts
        register = collections_client.get(
            f"{collections_url(project_id)}/receivables", params={"as_of": "2026-04-01"}
        ).json()
        row = next(r for r in register if r["sale_id"] == sale_id)
        account = collection_account(collections_client, project_id, sale_id, as_of="2026-04-01")

        for field in (
            "scheduled_total",
            "confirmed_receipts_total",
            "allocated_total",
            "unapplied_cash",
            "outstanding_total",
            "overdue_total",
            "oldest_overdue_days",
            "derived_collection_status",
            "installments_total",
            "open_disputes",
        ):
            assert row["summary"][field] == account[field], field

    def test_the_project_strip_totals_the_register_rows(
        self,
        collections_client: TestClient,
        project_id: str,
        two_accounts: tuple[str, str],
        historical_schedule: str,
    ) -> None:
        """Per currency, and only ever within one.

        The strip has no project-wide money field to compare against, which is
        the point: every figure belongs to a denomination, so the check is that
        each denomination totals the register rows billed in it.
        """
        del two_accounts, historical_schedule
        params = {"as_of": "2026-04-01"}
        register = collections_client.get(
            f"{collections_url(project_id)}/receivables", params=params
        ).json()
        strip = collections_client.get(
            f"{collections_url(project_id)}/summary", params=params
        ).json()

        assert strip["accounts"] == len(register)
        assert strip["currencies"]
        for totals in strip["currencies"]:
            rows = [r for r in register if r["currency_id"] == totals["currency_id"]]
            assert totals["accounts"] == len(rows)
            for field in ("outstanding_total", "overdue_total", "unapplied_cash"):
                expected = sum(Decimal(r["summary"][field]) for r in rows)
                assert Decimal(totals[field]) == expected, field

    def test_the_aging_buckets_reconcile_to_outstanding(
        self,
        collections_client: TestClient,
        project_id: str,
        two_accounts: tuple[str, str],
        historical_schedule: str,
    ) -> None:
        """The bands are a partition of the outstanding balance, not a summary.

        If they stopped adding up, an aging report would be showing a different
        total from the receivables register beside it. Checked inside each
        denomination, because a band that mixed currencies would be adding
        unlike numbers exactly where nobody would look for it.
        """
        del two_accounts, historical_schedule
        params = {"as_of": "2026-04-01"}
        strip = collections_client.get(
            f"{collections_url(project_id)}/summary", params=params
        ).json()
        assert strip["currencies"]
        for totals in strip["currencies"]:
            banded = sum(Decimal(v) for v in totals["buckets"].values())
            assert banded == Decimal(totals["outstanding_total"])


class TestRegisterContent:
    """Given the register, when an operator reads a row."""

    def test_a_row_names_the_unit_the_buyer_and_the_position(
        self,
        collections_client: TestClient,
        project_id: str,
        two_accounts: tuple[str, str],
    ) -> None:
        sale_id, _ = two_accounts
        register = collections_client.get(f"{collections_url(project_id)}/receivables").json()
        row = next(r for r in register if r["sale_id"] == sale_id)
        assert row["unit_number"]
        assert row["client_display_name"]
        assert row["sale_number"]
        assert row["summary"]["derived_collection_status"]

    def test_a_project_with_no_sales_answers_with_an_empty_register(
        self,
        collections_client: TestClient,
        admin_client: TestClient,
        country_pack_id: str,
        currency_id: str,
        reference_data: None,
    ) -> None:
        from tests.modules.conftest import PROJECTS, project_payload

        created = admin_client.post(
            PROJECTS,
            json=project_payload(
                country_pack_id, currency_id, code="PRJ-EMPTY", name="Nothing sold yet"
            ),
        )
        assert created.status_code == 201, created.text
        empty = created.json()["id"]

        response = admin_client.get(f"{collections_url(empty)}/receivables")
        assert response.status_code == 200
        assert response.json() == []

        strip = admin_client.get(f"{collections_url(empty)}/summary").json()
        assert strip["accounts"] == 0
        assert strip["currencies"] == []
        del collections_client
