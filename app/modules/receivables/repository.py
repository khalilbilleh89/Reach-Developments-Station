"""
receivables.repository

Persistence layer for the Receivable model.

Responsibilities:
  - CRUD / bulk operations on receivable records
  - No business logic; callers are responsible for validation and status derivation
"""

from typing import List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.receivables.models import Receivable


class ReceivableRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, receivable_id: str) -> Optional[Receivable]:
        return (
            self.db.query(Receivable)
            .filter(Receivable.id == receivable_id)
            .first()
        )

    def get_by_installment(self, installment_id: str) -> Optional[Receivable]:
        return (
            self.db.query(Receivable)
            .filter(Receivable.installment_id == installment_id)
            .first()
        )

    def list_by_contract(self, contract_id: str) -> List[Receivable]:
        return (
            self.db.query(Receivable)
            .filter(Receivable.contract_id == contract_id)
            .order_by(Receivable.receivable_number)
            .all()
        )

    def list_by_project(self, project_id: str) -> List[Receivable]:
        """Return all receivables for every contract in a project.

        Joins through the unit and sales_contract tables to scope by project.
        """
        from app.modules.sales.models import SalesContract
        from app.modules.units.models import Unit
        from app.modules.floors.models import Floor
        from app.modules.buildings.models import Building
        from app.modules.phases.models import Phase

        return (
            self.db.query(Receivable)
            .join(SalesContract, Receivable.contract_id == SalesContract.id)
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(Phase.project_id == project_id)
            .order_by(Receivable.due_date, Receivable.receivable_number)
            .all()
        )

    def list_by_status(self, status: str) -> List[Receivable]:
        return (
            self.db.query(Receivable)
            .filter(Receivable.status == status)
            .order_by(Receivable.due_date)
            .all()
        )

    def bulk_create(self, receivables: List[Receivable]) -> List[Receivable]:
        """Persist a list of new receivable records in a single transaction.

        Rolls back and re-raises ``IntegrityError`` so the service layer can
        translate it into a 409 response (e.g. concurrent duplicate generation).
        """
        try:
            for r in receivables:
                self.db.add(r)
            self.db.commit()
            for r in receivables:
                self.db.refresh(r)
            return receivables
        except IntegrityError:
            self.db.rollback()
            raise

    def save(self, receivable: Receivable) -> Receivable:
        """Persist changes to an existing receivable record."""
        self.db.add(receivable)
        self.db.commit()
        self.db.refresh(receivable)
        return receivable
