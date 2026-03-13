"""
collections.service

Service-layer orchestration for receipt recording and receivables retrieval.

Business rules enforced here:
  - Contract must exist
  - Payment schedule line must exist
  - Schedule line must belong to the same contract
  - Receipt amount must be positive (enforced by schema)
  - Total receipts on a line cannot exceed the due amount (overpayment forbidden)
  - Overpayment check is concurrency-safe: the schedule row is locked with
    SELECT FOR UPDATE before the sum is computed and the receipt is inserted,
    all within one transaction.
  - Monetary comparisons are done in integer cents to avoid floating-point drift.
  - Receivable status is derived from due amount, total received, and due date:
      pending        → no receipts yet and not past due date
      partially_paid → some received but outstanding > 0
      paid           → total_received >= due_amount
      overdue        → outstanding > 0 and due date is in the past
  - Receivables retrieval fetches all receipt totals in a single grouped query
    (no N+1 per schedule line).
"""

from __future__ import annotations

from datetime import date
from typing import List

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.collections.models import PaymentReceipt
from app.modules.collections.repository import (
    PaymentReceiptRepository,
    ReceivableRepository,
)
from app.modules.collections.schemas import (
    ContractReceivablesResponse,
    PaymentReceiptCreate,
    PaymentReceiptListResponse,
    PaymentReceiptResponse,
    ReceivableLineResponse,
)
from app.modules.payment_plans.models import PaymentSchedule
from app.modules.sales.models import SalesContract
from app.shared.enums.finance import ReceivableStatus


def _to_cents(amount: float) -> int:
    """Convert a monetary amount to integer cents, rounding to 2dp first."""
    return round(round(amount, 2) * 100)


def _from_cents(cents: int) -> float:
    """Convert integer cents back to a float amount at 2dp."""
    return round(cents / 100, 2)


class CollectionsService:
    def __init__(self, db: Session) -> None:
        self.receipt_repo = PaymentReceiptRepository(db)
        self.receivable_repo = ReceivableRepository(db)
        self.db = db

    # ------------------------------------------------------------------
    # Receipt recording
    # ------------------------------------------------------------------

    def record_receipt(self, data: PaymentReceiptCreate) -> PaymentReceiptResponse:
        """Validate inputs and persist a payment receipt in a single transaction.

        Concurrency safety: the payment schedule row is fetched with a row-level
        lock (SELECT FOR UPDATE) before the overpayment check and the insert.
        Both operations share the same transaction so that two concurrent
        requests cannot both pass the check and both commit.

        Monetary comparison is done in integer cents to prevent floating-point
        drift on 2dp money values.
        """
        # Validate contract first (read-only; no lock needed).
        contract = self._require_contract(data.contract_id)

        # Re-fetch schedule line with row-level lock to serialize concurrent writes.
        # with_for_update() is a no-op in SQLite (tests) but active in PostgreSQL (prod).
        line = (
            self.db.query(PaymentSchedule)
            .filter(PaymentSchedule.id == data.payment_schedule_id)
            .with_for_update()
            .first()
        )
        if not line:
            raise HTTPException(
                status_code=404,
                detail=f"Payment schedule line {data.payment_schedule_id!r} not found.",
            )
        self._require_schedule_belongs_to_contract(line, contract.id)

        # Normalize amounts to integer cents before comparison.
        due_cents = _to_cents(float(line.due_amount))
        already_received_cents = _to_cents(
            self.receipt_repo.total_received_for_schedule_line(line.id)
        )
        new_cents = _to_cents(data.amount_received)

        if already_received_cents + new_cents > due_cents:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Receipt of {_from_cents(new_cents):.2f} would cause total received "
                    f"({_from_cents(already_received_cents + new_cents):.2f}) to exceed "
                    f"due amount ({_from_cents(due_cents):.2f}) "
                    f"for schedule line {line.id!r}."
                ),
            )

        # Insert receipt within the same transaction and commit once.
        receipt = PaymentReceipt(**data.model_dump())
        self.db.add(receipt)
        self.db.commit()
        self.db.refresh(receipt)
        return PaymentReceiptResponse.model_validate(receipt)

    def get_receipt(self, receipt_id: str) -> PaymentReceiptResponse:
        receipt = self.receipt_repo.get_by_id(receipt_id)
        if not receipt:
            raise HTTPException(
                status_code=404, detail=f"Receipt {receipt_id!r} not found."
            )
        return PaymentReceiptResponse.model_validate(receipt)

    def get_receipts_for_contract(self, contract_id: str) -> PaymentReceiptListResponse:
        self._require_contract(contract_id)
        receipts = self.receipt_repo.list_by_contract(contract_id)
        items = [PaymentReceiptResponse.model_validate(r) for r in receipts]
        return PaymentReceiptListResponse(
            contract_id=contract_id,
            items=items,
            total=len(items),
            total_received=round(sum(i.amount_received for i in items), 2),
        )

    # ------------------------------------------------------------------
    # Receivables view
    # ------------------------------------------------------------------

    def get_receivables_for_contract(
        self, contract_id: str
    ) -> ContractReceivablesResponse:
        """Derive receivable status for each schedule line of a contract.

        All receipt totals are fetched in a single grouped query to avoid
        an N+1 pattern when a contract has many installment lines.
        """
        self._require_contract(contract_id)
        schedule_lines = self.receivable_repo.list_schedule_lines_by_contract(
            contract_id
        )

        # Single grouped query: {schedule_id → total_received}
        totals_by_line = self.receipt_repo.totals_by_schedule_line_for_contract(
            contract_id
        )

        today = date.today()
        receivable_lines: List[ReceivableLineResponse] = []

        for line in schedule_lines:
            due_amount = float(line.due_amount)
            total_received = totals_by_line.get(line.id, 0.0)
            outstanding = round(due_amount - total_received, 2)
            status = self._derive_receivable_status(
                due_amount=due_amount,
                total_received=total_received,
                due_date=line.due_date,
                today=today,
            )
            receivable_lines.append(
                ReceivableLineResponse(
                    schedule_id=line.id,
                    installment_number=line.installment_number,
                    due_date=line.due_date,
                    due_amount=due_amount,
                    total_received=round(total_received, 2),
                    outstanding_amount=outstanding,
                    receivable_status=status,
                )
            )

        total_due = round(sum(item.due_amount for item in receivable_lines), 2)
        total_received = round(sum(item.total_received for item in receivable_lines), 2)
        total_outstanding = round(
            sum(item.outstanding_amount for item in receivable_lines), 2
        )

        return ContractReceivablesResponse(
            contract_id=contract_id,
            items=receivable_lines,
            total_due=total_due,
            total_received=total_received,
            total_outstanding=total_outstanding,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_contract(self, contract_id: str) -> SalesContract:
        contract = (
            self.db.query(SalesContract).filter(SalesContract.id == contract_id).first()
        )
        if not contract:
            raise HTTPException(
                status_code=404, detail=f"Contract {contract_id!r} not found."
            )
        return contract

    @staticmethod
    def _require_schedule_belongs_to_contract(
        line: PaymentSchedule, contract_id: str
    ) -> None:
        if line.contract_id != contract_id:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Schedule line {line.id!r} does not belong to contract {contract_id!r}."
                ),
            )

    @staticmethod
    def _derive_receivable_status(
        due_amount: float,
        total_received: float,
        due_date: date,
        today: date,
    ) -> ReceivableStatus:
        if total_received >= due_amount:
            return ReceivableStatus.PAID
        outstanding = due_amount - total_received
        if outstanding > 0 and due_date < today:
            return ReceivableStatus.OVERDUE
        if total_received > 0:
            return ReceivableStatus.PARTIALLY_PAID
        return ReceivableStatus.PENDING
