"""
phases.service

Business logic for the Phase entity.
Enforces: phase must belong to a valid project; sequence must be unique per project.
Lifecycle rules:
  - A phase cannot become active if the previous phase (lower sequence) is not completed.
  - A completed phase cannot regress to an earlier status (planned/active) unless reopened.
  - Lifecycle advancement follows sequence order and cannot skip steps.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.phases.repository import PhaseRepository
from app.modules.phases.schemas import (
    LifecyclePhaseItem,
    PhaseCreate,
    PhaseCreateForProject,
    PhaseList,
    PhaseResponse,
    PhaseUpdate,
    ProjectLifecycle,
)
from app.modules.projects.repository import ProjectRepository
from app.shared.enums.project import PhaseStatus


class PhaseService:
    def __init__(self, db: Session) -> None:
        self.repo = PhaseRepository(db)
        self.project_repo = ProjectRepository(db)

    def create_phase(self, data: PhaseCreate) -> PhaseResponse:
        project = self.project_repo.get_by_id(data.project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{data.project_id}' not found.",
            )
        existing = self.repo.get_by_project_and_sequence(data.project_id, data.sequence)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Phase with sequence {data.sequence} already exists in project '{data.project_id}'.",
            )
        phase = self.repo.create(data)
        return PhaseResponse.model_validate(phase)

    def create_phase_for_project(self, project_id: str, data: PhaseCreateForProject) -> PhaseResponse:
        project = self.project_repo.get_by_id(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{project_id}' not found.",
            )
        existing = self.repo.get_by_project_and_sequence(project_id, data.sequence)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Phase with sequence {data.sequence} already exists in project '{project_id}'.",
            )
        full_data = PhaseCreate(project_id=project_id, **data.model_dump())
        phase = self.repo.create(full_data)
        return PhaseResponse.model_validate(phase)

    def get_phase(self, phase_id: str) -> PhaseResponse:
        phase = self.repo.get_by_id(phase_id)
        if not phase:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Phase '{phase_id}' not found.",
            )
        return PhaseResponse.model_validate(phase)

    def list_phases(self, project_id: str | None = None, skip: int = 0, limit: int = 100) -> PhaseList:
        phases = self.repo.list(project_id=project_id, skip=skip, limit=limit)
        total = self.repo.count(project_id=project_id)
        return PhaseList(
            items=[PhaseResponse.model_validate(p) for p in phases],
            total=total,
        )

    def list_phases_by_project(self, project_id: str, skip: int = 0, limit: int = 100) -> PhaseList:
        project = self.project_repo.get_by_id(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{project_id}' not found.",
            )
        return self.list_phases(project_id=project_id, skip=skip, limit=limit)

    def update_phase(self, phase_id: str, data: PhaseUpdate) -> PhaseResponse:
        phase = self.repo.get_by_id(phase_id)
        if not phase:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Phase '{phase_id}' not found.",
            )
        if data.sequence is not None and data.sequence != phase.sequence:
            existing = self.repo.get_by_project_and_sequence(phase.project_id, data.sequence)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Phase with sequence {data.sequence} already exists in the project.",
                )
        # Lifecycle rule: cannot regress a completed phase to planned or active
        if data.status is not None:
            current_status = PhaseStatus(phase.status)
            new_status = data.status
            if current_status == PhaseStatus.COMPLETED and new_status != PhaseStatus.COMPLETED:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        "Cannot revert a completed phase. "
                        "Use the reopen endpoint to explicitly reopen a phase."
                    ),
                )
            # Lifecycle rule: cannot activate a phase if a prior phase is not completed
            if new_status == PhaseStatus.ACTIVE and current_status == PhaseStatus.PLANNED:
                target_seq = data.sequence if data.sequence is not None else phase.sequence
                prior = self.repo.get_prior_phase(phase.project_id, target_seq)
                if prior and PhaseStatus(prior.status) != PhaseStatus.COMPLETED:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=(
                            f"Cannot activate phase '{phase.name}' (sequence {target_seq}): "
                            f"the preceding phase '{prior.name}' (sequence {prior.sequence}) "
                            "must be completed first."
                        ),
                    )
        updated = self.repo.update(phase, data)
        return PhaseResponse.model_validate(updated)

    def reopen_phase(self, phase_id: str) -> PhaseResponse:
        """Explicitly reopen a completed phase back to active status."""
        phase = self.repo.get_by_id(phase_id)
        if not phase:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Phase '{phase_id}' not found.",
            )
        if PhaseStatus(phase.status) != PhaseStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Only completed phases can be reopened.",
            )
        reopen_data = PhaseUpdate(status=PhaseStatus.ACTIVE)
        updated = self.repo.update(phase, reopen_data)
        return PhaseResponse.model_validate(updated)

    def advance_project_phase(self, phase_id: str) -> PhaseResponse:
        """Mark a phase as completed and activate the next phase in sequence."""
        phase = self.repo.get_by_id(phase_id)
        if not phase:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Phase '{phase_id}' not found.",
            )
        if PhaseStatus(phase.status) != PhaseStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Phase '{phase.name}' (sequence {phase.sequence}) must be active to advance. "
                    f"Current status: {phase.status}."
                ),
            )
        # Mark current phase as completed
        complete_data = PhaseUpdate(status=PhaseStatus.COMPLETED)
        self.repo.update(phase, complete_data)

        # Activate the next phase in sequence if one exists
        next_phase = self.repo.get_next_phase(phase.project_id, phase.sequence)
        if next_phase:
            activate_data = PhaseUpdate(status=PhaseStatus.ACTIVE)
            self.repo.update(next_phase, activate_data)

        updated = self.repo.get_by_id(phase_id)
        return PhaseResponse.model_validate(updated)

    def get_project_lifecycle(self, project_id: str) -> ProjectLifecycle:
        """Return the ordered lifecycle view for a project."""
        project = self.project_repo.get_by_id(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{project_id}' not found.",
            )
        phases = self.repo.list(project_id=project_id, skip=0, limit=1000)

        current_phase = next(
            (p for p in phases if PhaseStatus(p.status) == PhaseStatus.ACTIVE),
            None,
        )

        lifecycle_items = [
            LifecyclePhaseItem(
                id=p.id,
                project_id=p.project_id,
                name=p.name,
                code=p.code,
                sequence=p.sequence,
                phase_type=p.phase_type,
                status=PhaseStatus(p.status),
                start_date=p.start_date,
                end_date=p.end_date,
                description=p.description,
                is_current=(current_phase is not None and p.id == current_phase.id),
            )
            for p in phases
        ]

        return ProjectLifecycle(
            project_id=project_id,
            phases=lifecycle_items,
            current_phase_type=current_phase.phase_type if current_phase else None,
            current_sequence=current_phase.sequence if current_phase else None,
        )

    def delete_phase(self, phase_id: str) -> None:
        phase = self.repo.get_by_id(phase_id)
        if not phase:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Phase '{phase_id}' not found.",
            )
        self.repo.delete(phase)
