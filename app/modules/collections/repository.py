"""
collections.repository

Data access layer for PaymentReceipt and receivables aggregation.

Responsibilities:
  - CRUD operations on receipts
  - Aggregate received amounts by schedule line
  - No business logic; callers are responsible for validation
"""

from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.collections.models import PaymentReceipt
from app.modules.collections.schemas import PaymentReceiptCreate
from app.modules.payment_plans.models import PaymentSchedule


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
                PaymentReceipt.status == "recorded",
            )
            .scalar()
        )
        return float(result)


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
