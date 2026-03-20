"""
registry.repository

Data access layer for RegistrationCase, RegistrationMilestone, and
RegistrationDocument entities.

This module is pure database access — no business logic lives here.
"""

from typing import List, Optional

from sqlalchemy.orm import Session, selectinload

from app.modules.registry.models import (
    RegistrationCase,
    RegistrationDocument,
    RegistrationMilestone,
)
from app.shared.enums.registration import CaseStatus, MilestoneStatus

# Default milestone template applied to every new registry case.
_DEFAULT_MILESTONES = [
    ("spa_signed", "SPA Signed / Contract Executed", 1),
    ("due_diligence", "Due Diligence & Title Search", 2),
    ("noc_clearance", "NOC / Authority Clearance", 3),
    ("transfer_preparation", "Transfer Deed Preparation", 4),
    ("registration_submitted", "Submission to Land Registry", 5),
    ("title_issued", "Title Deed Issued", 6),
]

# Default required documents for every new registry case.
_DEFAULT_DOCUMENTS = [
    "Sale & Purchase Agreement (SPA)",
    "Buyer Passport / ID",
    "Seller Title Deed",
    "NOC from Developer",
    "Transfer Application Form",
    "Payment Clearance Certificate",
]


class RegistrationCaseRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, case: RegistrationCase) -> RegistrationCase:
        self.db.add(case)
        self.db.flush()
        return case

    def get_by_id(self, case_id: str) -> Optional[RegistrationCase]:
        return (
            self.db.query(RegistrationCase)
            .filter(RegistrationCase.id == case_id)
            .first()
        )

    def get_by_sale_contract_id(
        self, sale_contract_id: str
    ) -> Optional[RegistrationCase]:
        return (
            self.db.query(RegistrationCase)
            .filter(RegistrationCase.sale_contract_id == sale_contract_id)
            .first()
        )

    def get_active_by_unit(self, unit_id: str) -> Optional[RegistrationCase]:
        """Return any non-cancelled case for the given unit."""
        return (
            self.db.query(RegistrationCase)
            .filter(
                RegistrationCase.unit_id == unit_id,
                RegistrationCase.status != CaseStatus.CANCELLED.value,
            )
            .first()
        )

    def list_by_project(
        self, project_id: str, skip: int = 0, limit: int = 100
    ) -> List[RegistrationCase]:
        return (
            self.db.query(RegistrationCase)
            .options(
                selectinload(RegistrationCase.milestones),
                selectinload(RegistrationCase.documents),
            )
            .filter(RegistrationCase.project_id == project_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_by_project(self, project_id: str) -> int:
        return (
            self.db.query(RegistrationCase)
            .filter(RegistrationCase.project_id == project_id)
            .count()
        )

    def count_completed_by_project(self, project_id: str) -> int:
        return (
            self.db.query(RegistrationCase)
            .filter(
                RegistrationCase.project_id == project_id,
                RegistrationCase.status == CaseStatus.COMPLETED.value,
            )
            .count()
        )

    def count_open_by_project(self, project_id: str) -> int:
        """Count non-completed, non-cancelled cases."""
        return (
            self.db.query(RegistrationCase)
            .filter(
                RegistrationCase.project_id == project_id,
                RegistrationCase.status.notin_(
                    [CaseStatus.COMPLETED.value, CaseStatus.CANCELLED.value]
                ),
            )
            .count()
        )

    def save(self, case: RegistrationCase) -> RegistrationCase:
        self.db.commit()
        self.db.refresh(case)
        return case


class RegistrationMilestoneRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_defaults(self, case_id: str) -> List[RegistrationMilestone]:
        """Insert the standard milestone template for a new registry case."""
        milestones = [
            RegistrationMilestone(
                registration_case_id=case_id,
                step_code=code,
                step_name=name,
                sequence=seq,
                status=MilestoneStatus.PENDING.value,
            )
            for code, name, seq in _DEFAULT_MILESTONES
        ]
        self.db.add_all(milestones)
        return milestones

    def list_by_case(self, case_id: str) -> List[RegistrationMilestone]:
        return (
            self.db.query(RegistrationMilestone)
            .filter(RegistrationMilestone.registration_case_id == case_id)
            .order_by(RegistrationMilestone.sequence)
            .all()
        )

    def get_by_id(self, milestone_id: str) -> Optional[RegistrationMilestone]:
        return (
            self.db.query(RegistrationMilestone)
            .filter(RegistrationMilestone.id == milestone_id)
            .first()
        )

    def save(self, milestone: RegistrationMilestone) -> RegistrationMilestone:
        self.db.commit()
        self.db.refresh(milestone)
        return milestone

    def all_required_completed(self, case_id: str) -> bool:
        """Return True when every non-skipped milestone for the case is completed."""
        pending_count = (
            self.db.query(RegistrationMilestone)
            .filter(
                RegistrationMilestone.registration_case_id == case_id,
                RegistrationMilestone.status == MilestoneStatus.PENDING.value,
            )
            .count()
        )
        in_progress_count = (
            self.db.query(RegistrationMilestone)
            .filter(
                RegistrationMilestone.registration_case_id == case_id,
                RegistrationMilestone.status == MilestoneStatus.IN_PROGRESS.value,
            )
            .count()
        )
        return pending_count == 0 and in_progress_count == 0


class RegistrationDocumentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_defaults(self, case_id: str) -> List[RegistrationDocument]:
        """Insert the standard required document checklist for a new case."""
        docs = [
            RegistrationDocument(
                registration_case_id=case_id,
                document_type=doc_type,
                is_required=True,
                is_received=False,
            )
            for doc_type in _DEFAULT_DOCUMENTS
        ]
        self.db.add_all(docs)
        return docs

    def list_by_case(self, case_id: str) -> List[RegistrationDocument]:
        return (
            self.db.query(RegistrationDocument)
            .filter(RegistrationDocument.registration_case_id == case_id)
            .all()
        )

    def get_by_id(self, document_id: str) -> Optional[RegistrationDocument]:
        return (
            self.db.query(RegistrationDocument)
            .filter(RegistrationDocument.id == document_id)
            .first()
        )

    def save(self, document: RegistrationDocument) -> RegistrationDocument:
        self.db.commit()
        self.db.refresh(document)
        return document
