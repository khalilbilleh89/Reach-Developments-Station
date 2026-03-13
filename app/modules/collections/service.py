"""
collections.service

Service-layer orchestration for receipt recording and receivables retrieval.

Business rules enforced here:
  - Contract must exist
  - Payment schedule line must exist
  - Schedule line must belong to the same contract
  - Receipt amount must be positive (enforced by schema)
  - Total receipts on a line cannot exceed the due amount (overpayment forbidden)
  - Receivable status is derived from due amount, total received, and due date:
      pending        → no receipts yet and not past due date
      partially_paid → some received but outstanding > 0
      paid           → total_received >= due_amount
      overdue        → outstanding > 0 and due date is in the past
"""

from __future__ import annotations

from datetime import date
from typing import List

from fastapi import HTTPException
from sqlalchemy.orm import Session

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


class CollectionsService:
    def __init__(self, db: Session) -> None:
        self.receipt_repo = PaymentReceiptRepository(db)
        self.receivable_repo = ReceivableRepository(db)
        self.db = db

    # ------------------------------------------------------------------
    # Receipt recording
    # ------------------------------------------------------------------

    def record_receipt(self, data: PaymentReceiptCreate) -> PaymentReceiptResponse:
        """Validate inputs and persist a payment receipt."""
        contract = self._require_contract(data.contract_id)
        schedule_line = self._require_schedule_line(data.payment_schedule_id)
        self._require_schedule_belongs_to_contract(schedule_line, contract.id)
        self._require_no_overpayment(schedule_line, data.amount_received)

        receipt = self.receipt_repo.create(data)
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
        """Derive receivable status for each schedule line of a contract."""
        self._require_contract(contract_id)
        schedule_lines = self.receivable_repo.list_schedule_lines_by_contract(
            contract_id
        )

        today = date.today()
        receivable_lines: List[ReceivableLineResponse] = []

        for line in schedule_lines:
            due_amount = float(line.due_amount)
            total_received = self.receipt_repo.total_received_for_schedule_line(line.id)
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

    def _require_schedule_line(self, payment_schedule_id: str) -> PaymentSchedule:
        line = (
            self.db.query(PaymentSchedule)
            .filter(PaymentSchedule.id == payment_schedule_id)
            .first()
        )
        if not line:
            raise HTTPException(
                status_code=404,
                detail=f"Payment schedule line {payment_schedule_id!r} not found.",
            )
        return line

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

    def _require_no_overpayment(self, line: PaymentSchedule, new_amount: float) -> None:
        due_amount = float(line.due_amount)
        already_received = self.receipt_repo.total_received_for_schedule_line(line.id)
        if already_received + new_amount > due_amount:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Receipt of {new_amount:.2f} would cause total received "
                    f"({already_received + new_amount:.2f}) to exceed due amount "
                    f"({due_amount:.2f}) for schedule line {line.id!r}."
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
