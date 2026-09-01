"""The unit's collection dimension, and the clearance that depends on it.

Two integrations, both built the same way: Collections decides, another domain
owns the write.

Inventory owns ``Unit.collection_status`` — the column, the closed set and the
append-only event behind it. Collections works out which of the seven values
follows from receipts, allocations, disputes and cancellations, and asks
inventory to apply it. There is no route anywhere that sets the column directly.

Sales owns the handover clearance rows. What it no longer owns is the decision:
until this PR a collections officer could attest that an account was clear while
the ledger said forty thousand was outstanding, because there was no ledger to
check against. Now there is, so the generic route is closed for that one
clearance and the objective check happens here.

The strict part of ``cleared`` is deliberate. A buyer who owes nothing but has
an unresolved overpayment sitting unapplied is not a file to close.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.collections import ledger
from app.modules.inventory.models import DIMENSION_COLLECTION, Unit, UnitStatusEvent
from tests.modules.conftest import (
    allocate,
    collection_account,
    collections_url,
    confirm_receipt,
    governing_installments,
    record_receipt,
    sales_url,
)

ZERO = Decimal("0.00")


def _unit_status(db: Session, unit_id: str) -> str:
    return db.scalars(select(Unit).where(Unit.id == unit_id)).one().collection_status


def _collection_events(db: Session, unit_id: str) -> list[UnitStatusEvent]:
    return list(
        db.scalars(
            select(UnitStatusEvent)
            .where(
                UnitStatusEvent.unit_id == unit_id,
                UnitStatusEvent.dimension == DIMENSION_COLLECTION,
            )
            .order_by(UnitStatusEvent.changed_at)
        )
    )


def _settle_everything(
    collections_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    sale_id: str,
) -> None:
    """Pay the whole schedule off exactly, leaving nothing unapplied."""
    rows = governing_installments(collections_client, project_id, sale_id)
    for row in rows:
        receipt = record_receipt(collections_client, project_id, sale_id, row["outstanding"]).json()
        confirm_receipt(finance_client, project_id, receipt["id"])
        response = allocate(
            collections_client,
            project_id,
            receipt["id"],
            row["installment_id"],
            row["outstanding"],
        )
        assert response.status_code == 201, response.text


class TestTheDerivation:
    """The priority order, tested as pure arithmetic before it touches a unit."""

    def _rows(self, **overrides: object) -> list[ledger.InstallmentView]:
        import uuid
        from datetime import date

        base: dict[str, object] = {
            "installment_id": uuid.uuid4(),
            "sequence": 1,
            "label": "Instalment 1",
            "trigger_type": "fixed_date",
            "trigger_status": "scheduled",
            "date_based": True,
            "contractual_due_date": date(2026, 6, 1),
            "actual_due_date": date(2026, 6, 1),
            "triggered": False,
            "grace_days": 0,
            "principal": Decimal("5000.00"),
            "tax": ZERO,
            "fee": ZERO,
            "paid": ZERO,
            "as_of": date(2026, 1, 1),
            "disputed": False,
            "waived_until": None,
            "owner_user_id": None,
            "sale_cancelled": False,
        }
        base.update(overrides)
        return [ledger.installment_view(**base)]  # type: ignore[arg-type]

    def test_no_schedule_and_no_cash_means_collections_have_not_started(self) -> None:
        assert (
            ledger.unit_collection_status(
                sale_cancelled=False,
                has_active_schedule=False,
                rows=[],
                unapplied_cash=ZERO,
                allocated_cash=ZERO,
                confirmed_cash=ZERO,
                open_disputes=0,
            )
            == ledger.UNIT_NOT_STARTED
        )

    def test_no_schedule_but_confirmed_cash_is_not_not_started(self) -> None:
        """A deposit taken before the plan was activated is money we are holding.

        There is no schedule to age it against, so nothing can call it current
        or overdue — but ``not_started`` beside a confirmed receipt is the one
        reading that could persuade somebody the buyer has paid nothing.
        ``partially_paid`` is one of inventory's existing seven, not an eighth
        invented for this case.
        """
        assert (
            ledger.unit_collection_status(
                sale_cancelled=False,
                has_active_schedule=False,
                rows=[],
                unapplied_cash=Decimal("25000.00"),
                allocated_cash=ZERO,
                confirmed_cash=Decimal("25000.00"),
                open_disputes=0,
            )
            == ledger.UNIT_PARTIALLY_PAID
        )

    def test_a_clean_live_schedule_is_current(self) -> None:
        assert (
            ledger.unit_collection_status(
                sale_cancelled=False,
                has_active_schedule=True,
                rows=self._rows(),
                unapplied_cash=ZERO,
                allocated_cash=ZERO,
                confirmed_cash=ZERO,
                open_disputes=0,
            )
            == ledger.UNIT_CURRENT
        )

    def test_part_paid_outranks_current(self) -> None:
        assert (
            ledger.unit_collection_status(
                sale_cancelled=False,
                has_active_schedule=True,
                rows=self._rows(paid=Decimal("1000.00")),
                unapplied_cash=ZERO,
                allocated_cash=Decimal("1000.00"),
                confirmed_cash=Decimal("1000.00"),
                open_disputes=0,
            )
            == ledger.UNIT_PARTIALLY_PAID
        )

    def test_overdue_outranks_part_paid(self) -> None:
        from datetime import date

        assert (
            ledger.unit_collection_status(
                sale_cancelled=False,
                has_active_schedule=True,
                rows=self._rows(paid=Decimal("1000.00"), as_of=date(2026, 7, 1)),
                unapplied_cash=ZERO,
                allocated_cash=Decimal("1000.00"),
                confirmed_cash=Decimal("1000.00"),
                open_disputes=0,
            )
            == ledger.UNIT_OVERDUE
        )

    def test_disputed_outranks_overdue(self) -> None:
        from datetime import date

        assert (
            ledger.unit_collection_status(
                sale_cancelled=False,
                has_active_schedule=True,
                rows=self._rows(as_of=date(2026, 7, 1), disputed=True),
                unapplied_cash=ZERO,
                allocated_cash=ZERO,
                confirmed_cash=ZERO,
                open_disputes=1,
            )
            == ledger.UNIT_DISPUTED
        )

    def test_cancelled_outranks_everything(self) -> None:
        from datetime import date

        assert (
            ledger.unit_collection_status(
                sale_cancelled=True,
                has_active_schedule=True,
                rows=self._rows(as_of=date(2026, 7, 1), disputed=True, sale_cancelled=True),
                unapplied_cash=Decimal("999.00"),
                allocated_cash=ZERO,
                confirmed_cash=Decimal("999.00"),
                open_disputes=1,
            )
            == ledger.UNIT_CANCELLED
        )

    def test_everything_settled_and_nothing_unapplied_is_cleared(self) -> None:
        assert (
            ledger.unit_collection_status(
                sale_cancelled=False,
                has_active_schedule=True,
                rows=self._rows(paid=Decimal("5000.00")),
                unapplied_cash=ZERO,
                allocated_cash=Decimal("5000.00"),
                confirmed_cash=Decimal("5000.00"),
                open_disputes=0,
            )
            == ledger.UNIT_CLEARED
        )

    def test_everything_settled_but_cash_unapplied_is_not_cleared(self) -> None:
        """The overpayment case, and the reason ``cleared`` is strict.

        A buyer who owes nothing but is owed five thousand back is not a file
        anybody should be closing.
        """
        assert (
            ledger.unit_collection_status(
                sale_cancelled=False,
                has_active_schedule=True,
                rows=self._rows(paid=Decimal("5000.00")),
                unapplied_cash=Decimal("5000.00"),
                allocated_cash=Decimal("5000.00"),
                confirmed_cash=Decimal("5000.00") + Decimal("5000.00"),
                open_disputes=0,
            )
            == ledger.UNIT_PARTIALLY_PAID
        )


class TestTheUnitColumn:
    """Given a ledger movement, when the unit's collection status is pushed."""

    def test_it_moves_from_overdue_to_cleared_as_the_ledger_is_settled(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        collecting_sale: str,
        unit_id: str,
        db: Session,
    ) -> None:
        """The unit reads ``not_started`` until collections genuinely begin.

        That is the value's own meaning, and it is honest: the column is driven
        by this module and this module has not done anything yet. The first
        confirmed receipt moves it to the truth — which for this fixture is
        ``overdue``, because two instalments fell due before today.

        A part payment does not lift that. Delinquency is the more urgent fact
        and outranks it, and only settling the whole ledger with nothing left
        unapplied reaches ``cleared``.
        """
        assert _unit_status(db, unit_id) == "not_started"

        rows = governing_installments(collections_client, project_id, collecting_sale)
        receipt = record_receipt(collections_client, project_id, collecting_sale, "1000.00").json()
        confirm_receipt(finance_client, project_id, receipt["id"])
        allocate(
            collections_client, project_id, receipt["id"], rows[0]["installment_id"], "1000.00"
        )
        db.expire_all()
        assert _unit_status(db, unit_id) == "overdue"

        _settle_everything(collections_client, finance_client, project_id, collecting_sale)
        db.expire_all()
        assert _unit_status(db, unit_id) == "cleared"

    def test_unapplied_cash_alone_keeps_a_settled_account_out_of_cleared(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        collecting_sale: str,
        unit_id: str,
        db: Session,
    ) -> None:
        """The overpayment case, end to end.

        Nothing is owed, so the account looks finished — until you notice the
        company is holding five hundred of this buyer's money that nobody has
        decided what to do with.
        """
        _settle_everything(collections_client, finance_client, project_id, collecting_sale)
        db.expire_all()
        assert _unit_status(db, unit_id) == "cleared"

        spare = record_receipt(collections_client, project_id, collecting_sale, "500.00").json()
        confirm_receipt(finance_client, project_id, spare["id"])
        db.expire_all()
        assert _unit_status(db, unit_id) == "partially_paid"

    def test_a_dispute_moves_the_unit_and_resolving_it_moves_it_back(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        unit_id: str,
        db: Session,
    ) -> None:
        rows = governing_installments(collections_client, project_id, collecting_sale)
        dispute = collections_client.post(
            f"{collections_url(project_id)}/installments/{rows[0]['installment_id']}/disputes",
            json={"reason": "Contested"},
        ).json()
        db.expire_all()
        assert _unit_status(db, unit_id) == "disputed"

        collections_client.post(
            f"{collections_url(project_id)}/disputes/{dispute['id']}/resolve",
            json={"resolution": "Settled with the buyer"},
        )
        db.expire_all()
        # Back to what it was. The dispute never changed the balance, so closing
        # it cannot have changed it either.
        assert _unit_status(db, unit_id) == "overdue"

    def test_an_unchanged_status_writes_no_duplicate_event(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        collecting_sale: str,
        unit_id: str,
        db: Session,
    ) -> None:
        """Collections recalculates after every write; most change nothing.

        Three receipts arrive. The first moves the unit off ``not_started`` and
        writes one event; the second and third leave it exactly where it is and
        write none. Without the no-op guard there would be three, and the
        transition that means something would be buried under the two that do
        not.
        """
        rows = governing_installments(collections_client, project_id, collecting_sale)
        before = len(_collection_events(db, unit_id))

        for amount in ("100.00", "200.00", "300.00"):
            receipt = record_receipt(collections_client, project_id, collecting_sale, amount).json()
            confirm_receipt(finance_client, project_id, receipt["id"])
            allocate(
                collections_client, project_id, receipt["id"], rows[0]["installment_id"], amount
            )

        db.expire_all()
        events = _collection_events(db, unit_id)
        assert len(events) == before + 1
        assert events[-1].from_status == "not_started"
        assert events[-1].to_status == "overdue"
        assert _unit_status(db, unit_id) == "overdue"

    def test_there_is_no_route_that_sets_the_column_directly(
        self, collections_client: TestClient, project_id: str, unit_id: str
    ) -> None:
        response = collections_client.patch(
            f"/api/v1/projects/{project_id}/inventory/units/{unit_id}",
            json={"collection_status": "cleared"},
        )
        assert response.status_code in (403, 422)


class TestTheClearance:
    """Given the handover gate, when Collections signs off — or cannot."""

    def test_it_cannot_be_granted_while_anything_is_outstanding(
        self, collections_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        response = collections_client.post(
            f"{collections_url(project_id)}/sales/{collecting_sale}/collection-clearance",
            json={"evidence_reference": "LEDGER-2026-001"},
        )
        assert response.status_code == 409
        detail = response.json()["detail"]
        assert "remains outstanding" in detail

    def test_the_blockers_are_named_rather_than_hidden_behind_a_disabled_button(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        collecting_sale: str,
    ) -> None:
        _settle_everything(collections_client, finance_client, project_id, collecting_sale)
        spare = record_receipt(collections_client, project_id, collecting_sale, "500.00").json()
        confirm_receipt(finance_client, project_id, spare["id"])
        rows = governing_installments(collections_client, project_id, collecting_sale)
        collections_client.post(
            f"{collections_url(project_id)}/installments/{rows[0]['installment_id']}/disputes",
            json={"reason": "Contested after settlement"},
        )

        response = collections_client.get(
            f"{collections_url(project_id)}/sales/{collecting_sale}/collection-clearance"
        )
        assert response.status_code == 200, response.text
        blockers = response.json()["blockers"]
        assert any("500.00 of confirmed cash is unapplied" in b for b in blockers)
        assert any("dispute" in b for b in blockers)

    def test_the_generic_sales_route_can_no_longer_grant_it(
        self,
        collections_client: TestClient,
        sales_ops_client: TestClient,
        project_id: str,
        collecting_sale: str,
    ) -> None:
        """The one clearance that now has arithmetic behind it.

        Legal and delivery still go through the generic route, because their
        concerns are judgements this system holds no figures for.
        """
        handover = sales_ops_client.post(
            f"{sales_url(project_id)}/contracts/{collecting_sale}/handover", json={}
        )
        assert handover.status_code in (200, 201), handover.text
        handover_id = handover.json()["handover"]["id"]

        response = collections_client.post(
            f"{sales_url(project_id)}/handovers/{handover_id}/clearances/collection",
            json={"evidence_reference": "BYPASS"},
        )
        assert response.status_code in (404, 409)
        if response.status_code == 409:
            assert "Collections account" in response.json()["detail"]

    @pytest.mark.parametrize("client_name", ["legal_client", "sales_ops_client", "admin_client"])
    def test_nobody_else_may_grant_the_collection_clearance(
        self,
        request: pytest.FixtureRequest,
        client_name: str,
        project_id: str,
        collecting_sale: str,
    ) -> None:
        client: TestClient = request.getfixturevalue(client_name)
        response = client.post(
            f"{collections_url(project_id)}/sales/{collecting_sale}/collection-clearance",
            json={"evidence_reference": "NOT-MINE"},
        )
        assert response.status_code == 403


class TestClearanceRevocation:
    """Given a cleared account, when the ledger reopens underneath it."""

    def _clear(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        sales_ops_client: TestClient,
        project_id: str,
        sale_id: str,
    ) -> None:
        handover = sales_ops_client.post(
            f"{sales_url(project_id)}/contracts/{sale_id}/handover", json={}
        )
        assert handover.status_code in (200, 201), handover.text
        _settle_everything(collections_client, finance_client, project_id, sale_id)
        granted = collections_client.post(
            f"{collections_url(project_id)}/sales/{sale_id}/collection-clearance",
            json={"evidence_reference": "LEDGER-2026-001"},
        )
        assert granted.status_code == 200, granted.text
        assert granted.json()["status"] == "cleared"

    def test_a_settled_account_can_be_signed_off(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        sales_ops_client: TestClient,
        project_id: str,
        collecting_sale: str,
        unit_id: str,
        db: Session,
    ) -> None:
        self._clear(
            collections_client, finance_client, sales_ops_client, project_id, collecting_sale
        )
        db.expire_all()
        assert _unit_status(db, unit_id) == "cleared"
        account = collection_account(collections_client, project_id, collecting_sale)
        assert account["collection_clearance_status"] == "cleared"

    def test_reversing_a_receipt_withdraws_the_clearance_automatically(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        sales_ops_client: TestClient,
        project_id: str,
        collecting_sale: str,
        unit_id: str,
        db: Session,
    ) -> None:
        """The contradiction this integration exists to make impossible.

        A unit reading ``overdue`` beside a collection clearance reading
        ``cleared`` is exactly what happens when the gate is an attestation
        nobody re-checks.
        """
        self._clear(
            collections_client, finance_client, sales_ops_client, project_id, collecting_sale
        )
        receipts = collections_client.get(
            f"{collections_url(project_id)}/sales/{collecting_sale}/receipts"
        ).json()
        target = receipts[0]["id"]

        reversed_ = finance_client.post(
            f"{collections_url(project_id)}/receipts/{target}/reverse",
            json={"reason": "Cheque returned unpaid"},
        )
        assert reversed_.status_code == 200, reversed_.text

        account = collection_account(collections_client, project_id, collecting_sale)
        assert account["collection_clearance_status"] == "pending"
        assert account["derived_collection_status"] != "cleared"
        db.expire_all()
        assert _unit_status(db, unit_id) != "cleared"

    def test_reversing_an_allocation_withdraws_it_too(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        sales_ops_client: TestClient,
        project_id: str,
        collecting_sale: str,
    ) -> None:
        self._clear(
            collections_client, finance_client, sales_ops_client, project_id, collecting_sale
        )
        receipts = collections_client.get(
            f"{collections_url(project_id)}/sales/{collecting_sale}/receipts"
        ).json()
        allocation = receipts[0]["allocations"][0]["id"]

        response = collections_client.post(
            f"{collections_url(project_id)}/allocations/{allocation}/reverse",
            json={"reason": "Applied to the wrong instalment"},
        )
        assert response.status_code == 200, response.text

        account = collection_account(collections_client, project_id, collecting_sale)
        assert account["collection_clearance_status"] == "pending"
        # The cash is still confirmed; it is simply unapplied again, which is
        # itself enough to stop the account being clear.
        assert account["confirmed_receipts_total"] != "0.00"
        assert account["unapplied_cash"] != "0.00"


class TestCashBeforeAnySchedule:
    """Given a deposit taken before the plan was activated, when the unit is read.

    Developers take money before the schedule is agreed — that is what a
    reservation deposit is. Until a plan is activated there is nothing to age
    the cash against, so no honest reading calls the account current or overdue.

    But ``not_started`` beside a confirmed receipt is worse than either. It is
    the one screen that could persuade somebody the buyer has paid nothing, and
    it would be sitting on the unit record where the sales team looks first.
    """

    def _deposit(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        sale_id: str,
        amount: str = "25000.00",
    ) -> str:
        recorded = record_receipt(collections_client, project_id, sale_id, amount)
        assert recorded.status_code == 201, recorded.text
        receipt_id = recorded.json()["id"]
        assert confirm_receipt(finance_client, project_id, receipt_id).status_code == 200
        return receipt_id

    def test_a_sale_with_no_plan_and_no_cash_reads_not_started(
        self,
        collections_client: TestClient,
        project_id: str,
        active_sale: str,
        unit_id: str,
        db: Session,
    ) -> None:
        """The genuine case, and still the default."""
        account = collection_account(collections_client, project_id, active_sale)
        assert account["confirmed_receipts_total"] == "0.00"
        assert account["derived_collection_status"] == "not_started"
        db.expire_all()
        assert _unit_status(db, unit_id) == "not_started"

    def test_a_confirmed_deposit_before_the_first_plan_is_not_not_started(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        active_sale: str,
        unit_id: str,
        db: Session,
    ) -> None:
        """Cash is being held, so the unit says so."""
        self._deposit(collections_client, finance_client, project_id, active_sale)

        account = collection_account(collections_client, project_id, active_sale)
        assert account["active_payment_plan_version_id"] is None
        assert account["confirmed_receipts_total"] == "25000.00"
        assert account["unapplied_cash"] == "25000.00"
        assert account["allocated_total"] == "0.00"
        assert account["derived_collection_status"] == "partially_paid"

        db.expire_all()
        assert _unit_status(db, unit_id) == "partially_paid"

    def test_a_recorded_but_unconfirmed_deposit_leaves_it_not_started(
        self,
        collections_client: TestClient,
        project_id: str,
        active_sale: str,
        unit_id: str,
        db: Session,
    ) -> None:
        """A receipt in Finance's queue is not cash, here as everywhere else."""
        recorded = record_receipt(collections_client, project_id, active_sale, "25000.00")
        assert recorded.status_code == 201, recorded.text

        account = collection_account(collections_client, project_id, active_sale)
        assert account["confirmed_receipts_total"] == "0.00"
        assert account["derived_collection_status"] == "not_started"
        db.expire_all()
        assert _unit_status(db, unit_id) == "not_started"

    def test_reversing_the_deposit_puts_it_back_to_not_started(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        active_sale: str,
        unit_id: str,
        db: Session,
    ) -> None:
        """The column follows the cash in both directions."""
        receipt_id = self._deposit(collections_client, finance_client, project_id, active_sale)
        reversed_receipt = finance_client.post(
            f"{collections_url(project_id)}/receipts/{receipt_id}/reverse",
            json={"reason": "Bank returned the transfer"},
        )
        assert reversed_receipt.status_code == 200, reversed_receipt.text

        account = collection_account(collections_client, project_id, active_sale)
        assert account["confirmed_receipts_total"] == "0.00"
        assert account["derived_collection_status"] == "not_started"
        db.expire_all()
        assert _unit_status(db, unit_id) == "not_started"
