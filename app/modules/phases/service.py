"""
phases.service

Business logic for the Phase entity.
Enforces: phase must belong to a valid project; sequence must be unique per project.
Lifecycle rules:
  - Only one ACTIVE phase is permitted per project at any time.
  - A phase cannot become active if the preceding phase (lower sequence) is not completed.
  - A completed phase cannot regress to an earlier status (planned/active) unless reopened.
  - Lifecycle advancement follows sequence order and cannot skip steps.
  - advance_project_phase() completes the current phase and activates the next in a single
    atomic transaction; the next phase must be PLANNED to be eligible for activation.
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

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _assert_no_other_active_phase(self, project_id: str, exclude_phase_id: str) -> None:
        """Raise 409 if any other phase in the project is already active."""
        others = self.repo.get_active_phases(project_id, exclude_id=exclude_phase_id)
        if others:
            names = ", ".join(f"'{p.name}' (seq {p.sequence})" for p in others)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Only one active phase is allowed per project. "
                    f"Already active: {names}."
                ),
            )

    # ── CRUD ─────────────────────────────────────────────────────────────────

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

        # Resolve the effective sequence after this update (used for ordering checks below).
        effective_seq = data.sequence if data.sequence is not None else phase.sequence

        if data.sequence is not None and data.sequence != phase.sequence:
            existing = self.repo.get_by_project_and_sequence(phase.project_id, data.sequence)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Phase with sequence {data.sequence} already exists in the project.",
                )

        # Resolve the effective status after this update.
        effective_status = data.status if data.status is not None else PhaseStatus(phase.status)

        # Lifecycle rule: cannot regress a completed phase to planned or active via PATCH.
        current_status = PhaseStatus(phase.status)
        if current_status == PhaseStatus.COMPLETED and effective_status != PhaseStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Cannot revert a completed phase. "
                    "Use the reopen endpoint to explicitly reopen a phase."
                ),
            )

        # Lifecycle rule: if the phase will be ACTIVE after the update, enforce ordering and
        # uniqueness. This covers both status changes (planned→active) AND sequence changes
        # where the phase is already active.
        if effective_status == PhaseStatus.ACTIVE:
            # Single active phase enforcement
            self._assert_no_other_active_phase(phase.project_id, exclude_phase_id=phase_id)

            # Prior phase must be completed (checked against the new sequence position).
            prior = self.repo.get_prior_phase(phase.project_id, effective_seq)
            if prior and PhaseStatus(prior.status) != PhaseStatus.COMPLETED:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Cannot have phase '{phase.name}' active at sequence {effective_seq}: "
                        f"the preceding phase '{prior.name}' (sequence {prior.sequence}) "
                        "must be completed first."
                    ),
                )

        updated = self.repo.update(phase, data)
        return PhaseResponse.model_validate(updated)

    # ── Lifecycle operations ──────────────────────────────────────────────────

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
        # Single active phase enforcement
        self._assert_no_other_active_phase(phase.project_id, exclude_phase_id=phase_id)

        reopen_data = PhaseUpdate(status=PhaseStatus.ACTIVE)
        updated = self.repo.update(phase, reopen_data)
        return PhaseResponse.model_validate(updated)

    def advance_project_phase(self, phase_id: str) -> PhaseResponse:
        """Mark a phase as completed and activate the next phase in sequence.

        Both operations (complete current + activate next) are performed in a
        single atomic transaction to prevent partial state on failure.
        """
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

        next_phase = self.repo.get_next_phase(phase.project_id, phase.sequence)
        if next_phase:
            next_status = PhaseStatus(next_phase.status)
            if next_status == PhaseStatus.ACTIVE:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Cannot advance phase '{phase.name}' (sequence {phase.sequence}): "
                        f"the next phase '{next_phase.name}' (sequence {next_phase.sequence}) "
                        "is already active."
                    ),
                )
            if next_status == PhaseStatus.COMPLETED:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Cannot activate next phase '{next_phase.name}' "
                        f"(sequence {next_phase.sequence}) because it is already completed. "
                        "Completed phases must be explicitly reopened."
                    ),
                )

        # Apply both changes in memory, then commit once (atomic).
        self.repo.apply_update(phase, PhaseUpdate(status=PhaseStatus.COMPLETED))
        if next_phase:
            self.repo.apply_update(next_phase, PhaseUpdate(status=PhaseStatus.ACTIVE))

        self.repo.db.commit()
        self.repo.db.refresh(phase)
        if next_phase:
            self.repo.db.refresh(next_phase)

        return PhaseResponse.model_validate(phase)

    def get_project_lifecycle(self, project_id: str) -> ProjectLifecycle:
        """Return the ordered lifecycle view for a project."""
        project = self.project_repo.get_by_id(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{project_id}' not found.",
            )
        phases = self.repo.list(project_id=project_id, skip=0, limit=1000)

        active_phases = [p for p in phases if PhaseStatus(p.status) == PhaseStatus.ACTIVE]
        # With single-active enforcement there should be at most one; pick the lowest
        # sequence for a deterministic result in edge-case legacy data.
        current_phase = active_phases[0] if active_phases else None

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
