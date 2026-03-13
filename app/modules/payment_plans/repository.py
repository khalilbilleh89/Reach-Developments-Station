"""
payment_plans.repository

Data access layer for PaymentPlanTemplate and PaymentSchedule.

Responsibilities:
  - CRUD operations on templates
  - Bulk create / list / delete operations on payment schedules
  - No business logic; callers are responsible for validation
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.modules.payment_plans.models import PaymentPlanTemplate, PaymentSchedule
from app.modules.payment_plans.schemas import (
    PaymentPlanTemplateCreate,
    PaymentPlanTemplateUpdate,
)


class PaymentPlanTemplateRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: PaymentPlanTemplateCreate) -> PaymentPlanTemplate:
        template = PaymentPlanTemplate(**data.model_dump())
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        return template

    def get_by_id(self, template_id: str) -> Optional[PaymentPlanTemplate]:
        return (
            self.db.query(PaymentPlanTemplate)
            .filter(PaymentPlanTemplate.id == template_id)
            .first()
        )

    def list(self, skip: int = 0, limit: int = 100) -> List[PaymentPlanTemplate]:
        return (
            self.db.query(PaymentPlanTemplate)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count(self) -> int:
        return self.db.query(PaymentPlanTemplate).count()

    def update(
        self, template: PaymentPlanTemplate, data: PaymentPlanTemplateUpdate
    ) -> PaymentPlanTemplate:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(template, field, value)
        self.db.commit()
        self.db.refresh(template)
        return template


class PaymentScheduleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def bulk_create(self, rows: List[dict]) -> List[PaymentSchedule]:
        """Insert multiple schedule rows in a single transaction."""
        schedules = [PaymentSchedule(**row) for row in rows]
        self.db.bulk_save_objects(schedules)
        self.db.commit()
        # Re-query to get ORM instances with auto-generated IDs and timestamps
        return (
            self.db.query(PaymentSchedule)
            .filter(PaymentSchedule.contract_id == rows[0]["contract_id"])
            .order_by(PaymentSchedule.installment_number)
            .all()
            if rows
            else []
        )

    def list_by_contract(self, contract_id: str) -> List[PaymentSchedule]:
        return (
            self.db.query(PaymentSchedule)
            .filter(PaymentSchedule.contract_id == contract_id)
            .order_by(PaymentSchedule.installment_number)
            .all()
        )

    def delete_by_contract(self, contract_id: str) -> None:
        """Remove all schedule rows for a contract (used during regeneration)."""
        self.db.query(PaymentSchedule).filter(
            PaymentSchedule.contract_id == contract_id
        ).delete()
        self.db.commit()
