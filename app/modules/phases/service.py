"""
phases.service

Business logic for the Phase entity.
Enforces: phase must belong to a valid project; sequence must be unique per project.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.phases.repository import PhaseRepository
from app.modules.phases.schemas import PhaseCreate, PhaseCreateForProject, PhaseList, PhaseResponse, PhaseUpdate
from app.modules.projects.repository import ProjectRepository


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
        updated = self.repo.update(phase, data)
        return PhaseResponse.model_validate(updated)

    def delete_phase(self, phase_id: str) -> None:
        phase = self.repo.get_by_id(phase_id)
        if not phase:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Phase '{phase_id}' not found.",
            )
        self.repo.delete(phase)
