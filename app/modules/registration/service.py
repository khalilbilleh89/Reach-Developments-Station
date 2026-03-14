"""
registration.service

Application-layer orchestration for the Registration/Conveyancing domain.

Business rules enforced here:
  - A registration case must be tied to a valid, existing sales contract.
  - A unit may not have more than one active (non-cancelled) registration case.
  - Completed cases are immutable except for notes / admin corrections.
  - Case completion requires all mandatory milestones to be completed.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.registration.models import (
    RegistrationCase,
    RegistrationDocument,
    RegistrationMilestone,
)
from app.modules.registration.repository import (
    RegistrationCaseRepository,
    RegistrationDocumentRepository,
    RegistrationMilestoneRepository,
)
from app.modules.registration.schemas import (
    RegistrationCaseCreate,
    RegistrationCaseListResponse,
    RegistrationCaseResponse,
    RegistrationCaseUpdate,
    RegistrationDocumentResponse,
    RegistrationDocumentUpdate,
    RegistrationMilestoneResponse,
    RegistrationMilestoneUpdate,
    RegistrationSummaryResponse,
)
from app.modules.sales.models import SalesContract
from app.modules.projects.models import Project
from app.modules.units.models import Unit
from app.modules.floors.models import Floor
from app.modules.buildings.models import Building
from app.modules.phases.models import Phase
from app.shared.enums.registration import CaseStatus


class RegistrationService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self.case_repo = RegistrationCaseRepository(db)
        self.milestone_repo = RegistrationMilestoneRepository(db)
        self.document_repo = RegistrationDocumentRepository(db)

    # ------------------------------------------------------------------
    # Case operations
    # ------------------------------------------------------------------

    def create_case(self, data: RegistrationCaseCreate) -> RegistrationCaseResponse:
        """Open a new registration case for a sold unit.

        Validates:
        - The referenced sales contract exists.
        - The unit does not already have an active registration case.
        """
        contract = self._require_contract(data.sale_contract_id)

        # Guard: prevent duplicate active cases on the same unit
        existing = self.case_repo.get_active_by_unit(data.unit_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Unit '{data.unit_id}' already has an active registration case "
                    f"(id='{existing.id}')."
                ),
            )

        # Guard: contract must belong to the supplied unit
        if contract.unit_id != data.unit_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="The sale contract does not belong to the specified unit.",
            )

        case = RegistrationCase(**data.model_dump())
        self.case_repo.create(case)

        # Initialise default milestones and document checklist atomically
        self.milestone_repo.create_defaults(case.id)
        self.document_repo.create_defaults(case.id)

        self._db.commit()
        self._db.refresh(case)
        return RegistrationCaseResponse.model_validate(case)

    def get_case(self, case_id: str) -> RegistrationCaseResponse:
        case = self._require_case(case_id)
        return RegistrationCaseResponse.model_validate(case)

    def get_case_by_sale_contract(
        self, sale_contract_id: str
    ) -> RegistrationCaseResponse:
        case = self.case_repo.get_by_sale_contract_id(sale_contract_id)
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No registration case found for contract '{sale_contract_id}'.",
            )
        return RegistrationCaseResponse.model_validate(case)

    def list_project_cases(
        self, project_id: str, skip: int = 0, limit: int = 100
    ) -> RegistrationCaseListResponse:
        self._require_project(project_id)
        cases = self.case_repo.list_by_project(project_id, skip=skip, limit=limit)
        total = self.case_repo.count_by_project(project_id)
        return RegistrationCaseListResponse(
            total=total,
            items=[RegistrationCaseResponse.model_validate(c) for c in cases],
        )

    def update_case(
        self, case_id: str, data: RegistrationCaseUpdate
    ) -> RegistrationCaseResponse:
        case = self._require_case(case_id)

        # Completed cases are immutable (only notes allowed)
        if case.status == CaseStatus.COMPLETED.value:
            allowed = {"notes"}
            requested = {k for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
            disallowed = requested - allowed
            if disallowed:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Completed registration cases are immutable. "
                        f"Cannot update: {sorted(disallowed)}."
                    ),
                )

        # If transitioning to COMPLETED, ensure all milestones are done
        if (
            data.status == CaseStatus.COMPLETED
            and case.status != CaseStatus.COMPLETED.value
        ):
            if not self.milestone_repo.all_required_completed(case_id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Cannot complete a registration case while milestones are "
                        "still pending or in progress."
                    ),
                )

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(case, field, value)

        self.case_repo.save(case)
        return RegistrationCaseResponse.model_validate(case)

    # ------------------------------------------------------------------
    # Milestone operations
    # ------------------------------------------------------------------

    def list_milestones(self, case_id: str) -> list[RegistrationMilestoneResponse]:
        self._require_case(case_id)
        milestones = self.milestone_repo.list_by_case(case_id)
        return [RegistrationMilestoneResponse.model_validate(m) for m in milestones]

    def update_milestone(
        self, case_id: str, milestone_id: str, data: RegistrationMilestoneUpdate
    ) -> RegistrationMilestoneResponse:
        self._require_case(case_id)
        milestone = self.milestone_repo.get_by_id(milestone_id)
        if not milestone or milestone.registration_case_id != case_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Milestone '{milestone_id}' not found for case '{case_id}'.",
            )
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(milestone, field, value)
        self.milestone_repo.save(milestone)
        return RegistrationMilestoneResponse.model_validate(milestone)

    # ------------------------------------------------------------------
    # Document operations
    # ------------------------------------------------------------------

    def list_documents(self, case_id: str) -> list[RegistrationDocumentResponse]:
        self._require_case(case_id)
        documents = self.document_repo.list_by_case(case_id)
        return [RegistrationDocumentResponse.model_validate(d) for d in documents]

    def update_document(
        self, case_id: str, document_id: str, data: RegistrationDocumentUpdate
    ) -> RegistrationDocumentResponse:
        self._require_case(case_id)
        document = self.document_repo.get_by_id(document_id)
        if not document or document.registration_case_id != case_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document '{document_id}' not found for case '{case_id}'.",
            )
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(document, field, value)
        self.document_repo.save(document)
        return RegistrationDocumentResponse.model_validate(document)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def get_project_summary(self, project_id: str) -> RegistrationSummaryResponse:
        """Return registration summary metrics for a project."""
        self._require_project(project_id)

        total_cases = self.case_repo.count_by_project(project_id)
        completed = self.case_repo.count_completed_by_project(project_id)
        open_cases = self.case_repo.count_open_by_project(project_id)

        # Count sold units in project via a sales contract count
        total_sold = (
            self._db.query(SalesContract)
            .join(Unit, SalesContract.unit_id == Unit.id)
            .join(Floor, Unit.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(Phase, Building.phase_id == Phase.id)
            .filter(Phase.project_id == project_id)
            .count()
        )

        # Units already in the registration pipeline (open or completed cases)
        # should not be counted as "sold but not registered".
        # open_cases excludes cancelled cases (see repository).
        active_pipeline = open_cases + completed
        sold_not_registered = max(0, total_sold - active_pipeline)
        ratio = round(completed / total_sold, 6) if total_sold > 0 else 0.0

        return RegistrationSummaryResponse(
            project_id=project_id,
            total_sold_units=total_sold,
            registration_cases_open=open_cases,
            registration_cases_completed=completed,
            sold_not_registered=sold_not_registered,
            registration_completion_ratio=ratio,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _require_case(self, case_id: str) -> RegistrationCase:
        case = self.case_repo.get_by_id(case_id)
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Registration case '{case_id}' not found.",
            )
        return case

    def _require_contract(self, contract_id: str) -> SalesContract:
        contract = (
            self._db.query(SalesContract)
            .filter(SalesContract.id == contract_id)
            .first()
        )
        if not contract:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sales contract '{contract_id}' not found.",
            )
        return contract

    def _require_project(self, project_id: str) -> Project:
        project = (
            self._db.query(Project).filter(Project.id == project_id).first()
        )
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{project_id}' not found.",
            )
        return project
