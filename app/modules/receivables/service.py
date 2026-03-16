"""
receivables.service

Business logic for receivable creation and lifecycle management.

Business rules enforced here:
  - Receivables are generated from payment installments (PaymentSchedule rows)
  - One receivable per installment — duplicate generation is blocked
  - Status is derived from due date and payment state:
      pending       → due date in the future, unpaid
      due           → due date is today, unpaid
      overdue       → due date passed, balance_due > 0
      partially_paid → amount_paid > 0 and balance_due > 0
      paid          → balance_due == 0
      cancelled     → set explicitly (contract/plan cancellation)
  - balance_due = amount_due - amount_paid (maintained by service)

No collections engine, no cash receipt ledger, no cashflow forecast updates.
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.receivables.models import Receivable
from app.modules.receivables.repository import ReceivableRepository
from app.modules.receivables.schemas import (
    GenerateReceivablesResponse,
    ReceivableListResponse,
    ReceivablePaymentUpdate,
    ReceivableResponse,
    ReceivableStatusUpdate,
)
from app.modules.payment_plans.models import PaymentSchedule
from app.modules.sales.models import SalesContract
from app.shared.enums.finance import ReceivableStatus

_VALID_STATUSES = frozenset(s.value for s in ReceivableStatus)


class ReceivableService:
    def __init__(self, db: Session) -> None:
        self.repo = ReceivableRepository(db)
        self.db = db

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate_for_contract(self, contract_id: str) -> GenerateReceivablesResponse:
        """Generate one receivable per installment for a contract.

        Raises 404 if the contract does not exist.
        Raises 404 if the contract has no payment installments.
        Raises 409 if receivables already exist for this contract.
        """
        contract = self._require_contract(contract_id)

        # Fetch installment schedule for the contract
        installments = (
            self.db.query(PaymentSchedule)
            .filter(PaymentSchedule.contract_id == contract_id)
            .order_by(PaymentSchedule.installment_number)
            .all()
        )
        if not installments:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Contract {contract_id!r} has no payment installments. "
                    "Create a payment plan before generating receivables."
                ),
            )

        # Guard: block duplicate generation
        existing = self.repo.list_by_contract(contract_id)
        if existing:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Receivables already exist for contract {contract_id!r} "
                    f"({len(existing)} records). Duplicate generation is not allowed."
                ),
            )

        today = date.today()
        new_receivables: List[Receivable] = []
        for inst in installments:
            amount_due = float(inst.due_amount)
            balance_due = amount_due  # amount_paid starts at 0
            status = self._derive_status(inst.due_date, 0.0, amount_due, today)
            r = Receivable(
                contract_id=contract.id,
                payment_plan_id=inst.template_id,
                installment_id=inst.id,
                receivable_number=inst.installment_number,
                due_date=inst.due_date,
                amount_due=amount_due,
                amount_paid=0.0,
                balance_due=balance_due,
                currency="AED",
                status=status,
            )
            new_receivables.append(r)

        persisted = self.repo.bulk_create(new_receivables)
        items = [ReceivableResponse.model_validate(r) for r in persisted]
        return GenerateReceivablesResponse(
            contract_id=contract_id,
            generated=len(items),
            items=items,
        )

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get_receivable(self, receivable_id: str) -> ReceivableResponse:
        r = self.repo.get_by_id(receivable_id)
        if not r:
            raise HTTPException(
                status_code=404,
                detail=f"Receivable {receivable_id!r} not found.",
            )
        return ReceivableResponse.model_validate(r)

    def list_contract_receivables(self, contract_id: str) -> ReceivableListResponse:
        self._require_contract(contract_id)
        rows = self.repo.list_by_contract(contract_id)
        return self._build_list_response(rows)

    def list_project_receivables(self, project_id: str) -> ReceivableListResponse:
        rows = self.repo.list_by_project(project_id)
        return self._build_list_response(rows)

    # ------------------------------------------------------------------
    # Status refresh
    # ------------------------------------------------------------------

    def refresh_statuses(self, today: Optional[date] = None) -> int:
        """Re-derive and persist the status for every non-cancelled, non-paid receivable.

        Returns the number of records whose status was updated.
        """
        effective_today = today or date.today()
        candidates = (
            self.db.query(Receivable)
            .filter(
                Receivable.status.notin_(
                    [ReceivableStatus.PAID.value, ReceivableStatus.CANCELLED.value]
                )
            )
            .all()
        )
        updated = 0
        for r in candidates:
            new_status = self._derive_status(
                r.due_date,
                float(r.amount_paid),
                float(r.amount_due),
                effective_today,
            )
            if new_status != r.status:
                r.status = new_status
                updated += 1
        if updated:
            self.db.commit()
        return updated

    # ------------------------------------------------------------------
    # Updates
    # ------------------------------------------------------------------

    def apply_payment_update(
        self, receivable_id: str, payload: ReceivablePaymentUpdate
    ) -> ReceivableResponse:
        """Record a manual payment amount and recalculate balance/status."""
        r = self.repo.get_by_id(receivable_id)
        if not r:
            raise HTTPException(
                status_code=404,
                detail=f"Receivable {receivable_id!r} not found.",
            )
        amount_due = float(r.amount_due)
        new_paid = payload.amount_paid
        if new_paid > amount_due:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"amount_paid ({new_paid}) exceeds amount_due ({amount_due}). "
                    "Overpayment is not supported."
                ),
            )
        r.amount_paid = new_paid
        r.balance_due = round(amount_due - new_paid, 2)
        r.status = self._derive_status(
            r.due_date, new_paid, amount_due, date.today()
        )
        if payload.notes is not None:
            r.notes = payload.notes
        saved = self.repo.save(r)
        return ReceivableResponse.model_validate(saved)

    def apply_status_update(
        self, receivable_id: str, payload: ReceivableStatusUpdate
    ) -> ReceivableResponse:
        """Manually override the status of a receivable."""
        r = self.repo.get_by_id(receivable_id)
        if not r:
            raise HTTPException(
                status_code=404,
                detail=f"Receivable {receivable_id!r} not found.",
            )
        if payload.status not in _VALID_STATUSES:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Invalid status {payload.status!r}. "
                    f"Valid values: {sorted(_VALID_STATUSES)}."
                ),
            )
        r.status = payload.status
        if payload.notes is not None:
            r.notes = payload.notes
        saved = self.repo.save(r)
        return ReceivableResponse.model_validate(saved)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_contract(self, contract_id: str) -> SalesContract:
        contract = (
            self.db.query(SalesContract)
            .filter(SalesContract.id == contract_id)
            .first()
        )
        if not contract:
            raise HTTPException(
                status_code=404,
                detail=f"Contract {contract_id!r} not found.",
            )
        return contract

    @staticmethod
    def _derive_status(
        due_date: date,
        amount_paid: float,
        amount_due: float,
        today: date,
    ) -> str:
        """Derive receivable status from payment state and due date.

        Status logic:
          paid          → balance_due == 0 (regardless of date)
          partially_paid → amount_paid > 0 and balance_due > 0
          overdue       → due date passed (today > due_date) and balance > 0
          due           → due date is today and unpaid
          pending       → due date in future and unpaid
        """
        balance = round(amount_due - amount_paid, 2)
        if balance <= 0:
            return ReceivableStatus.PAID.value
        if amount_paid > 0:
            # Partially paid — still overdue if past due
            if today > due_date:
                return ReceivableStatus.OVERDUE.value
            return ReceivableStatus.PARTIALLY_PAID.value
        # Unpaid
        if today > due_date:
            return ReceivableStatus.OVERDUE.value
        if today == due_date:
            return ReceivableStatus.DUE.value
        return ReceivableStatus.PENDING.value

    @staticmethod
    def _build_list_response(rows: List[Receivable]) -> ReceivableListResponse:
        items = [ReceivableResponse.model_validate(r) for r in rows]
        total_amount_due = round(sum(i.amount_due for i in items), 2)
        total_amount_paid = round(sum(i.amount_paid for i in items), 2)
        total_balance_due = round(sum(i.balance_due for i in items), 2)
        return ReceivableListResponse(
            items=items,
            total=len(items),
            total_amount_due=total_amount_due,
            total_amount_paid=total_amount_paid,
            total_balance_due=total_balance_due,
        )
