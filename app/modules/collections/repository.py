"""
collections.repository

Data access layer for PaymentReceipt and receivables aggregation.

Responsibilities:
  - CRUD operations on receipts
  - Aggregate received amounts by schedule line
  - No business logic; callers are responsible for validation
"""

from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.collections.models import PaymentReceipt
from app.modules.collections.schemas import PaymentReceiptCreate
from app.modules.payment_plans.models import PaymentSchedule
from app.shared.enums.finance import ReceiptStatus


class PaymentReceiptRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: PaymentReceiptCreate) -> PaymentReceipt:
        receipt = PaymentReceipt(**data.model_dump())
        self.db.add(receipt)
        self.db.commit()
        self.db.refresh(receipt)
        return receipt

    def get_by_id(self, receipt_id: str) -> Optional[PaymentReceipt]:
        return (
            self.db.query(PaymentReceipt)
            .filter(PaymentReceipt.id == receipt_id)
            .first()
        )

    def list_by_contract(self, contract_id: str) -> List[PaymentReceipt]:
        return (
            self.db.query(PaymentReceipt)
            .filter(PaymentReceipt.contract_id == contract_id)
            .order_by(PaymentReceipt.receipt_date)
            .all()
        )

    def list_by_schedule_line(self, payment_schedule_id: str) -> List[PaymentReceipt]:
        return (
            self.db.query(PaymentReceipt)
            .filter(PaymentReceipt.payment_schedule_id == payment_schedule_id)
            .order_by(PaymentReceipt.receipt_date)
            .all()
        )

    def total_received_for_schedule_line(self, payment_schedule_id: str) -> float:
        """Return the sum of all recorded (non-reversed) receipts for a schedule line."""
        result = (
            self.db.query(func.coalesce(func.sum(PaymentReceipt.amount_received), 0))
            .filter(
                PaymentReceipt.payment_schedule_id == payment_schedule_id,
                PaymentReceipt.status == ReceiptStatus.RECORDED.value,
            )
            .scalar()
        )
        return float(result)

    def totals_by_schedule_line_for_contract(
        self, contract_id: str
    ) -> Dict[str, float]:
        """Return {schedule_id: total_received} for all recorded receipts on a contract.

        Fetches all aggregated totals in a single GROUP BY query, avoiding N+1
        when building the receivables view for a contract.
        """
        rows = (
            self.db.query(
                PaymentReceipt.payment_schedule_id,
                func.sum(PaymentReceipt.amount_received),
            )
            .filter(
                PaymentReceipt.contract_id == contract_id,
                PaymentReceipt.status == ReceiptStatus.RECORDED.value,
            )
            .group_by(PaymentReceipt.payment_schedule_id)
            .all()
        )
        return {row[0]: float(row[1]) for row in rows}


class ReceivableRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_schedule_lines_by_contract(
        self, contract_id: str
    ) -> List[PaymentSchedule]:
        """Return all payment schedule lines for a contract, ordered by installment number."""
        return (
            self.db.query(PaymentSchedule)
            .filter(PaymentSchedule.contract_id == contract_id)
            .order_by(PaymentSchedule.installment_number)
            .all()
        )
