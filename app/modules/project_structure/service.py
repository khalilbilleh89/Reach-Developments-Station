"""
project_structure.service

Structure assembly and response shaping for the Project Structure Viewer.

Validates that the requested project exists, then traverses the eagerly loaded
ORM tree and assembles a typed ProjectStructureResponse with summary counts at
every level.

Forbidden: no business-rule calculations; no placeholder fabrication for missing
records; no hierarchy mutations.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.project_structure.repository import ProjectStructureRepository
from app.modules.project_structure.schemas import (
    ProjectStructureBuildingNode,
    ProjectStructureFloorNode,
    ProjectStructurePhaseNode,
    ProjectStructureResponse,
    ProjectStructureUnitNode,
)


class ProjectStructureService:
    def __init__(self, db: Session) -> None:
        self.repo = ProjectStructureRepository(db)

    def get_structure(self, project_id: str) -> ProjectStructureResponse:
        """Return the full typed structure response for a project.

        Raises HTTP 404 if the project does not exist.
        Returns empty child arrays where hierarchy levels are unpopulated.
        """
        project = self.repo.get_project_with_full_hierarchy(project_id)
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{project_id}' not found.",
            )

        phase_nodes: list[ProjectStructurePhaseNode] = []
        total_buildings = 0
        total_floors = 0
        total_units = 0

        for phase in sorted(project.phases, key=lambda p: p.sequence):
            building_nodes: list[ProjectStructureBuildingNode] = []
            phase_floors = 0
            phase_units = 0

            for building in sorted(phase.buildings, key=lambda b: b.name):
                floor_nodes: list[ProjectStructureFloorNode] = []
                building_units = 0

                for floor in sorted(building.floors, key=lambda f: f.sequence_number):
                    unit_nodes: list[ProjectStructureUnitNode] = [
                        ProjectStructureUnitNode(
                            id=unit.id,
                            unit_number=unit.unit_number,
                            unit_type=unit.unit_type,
                            status=unit.status,
                        )
                        for unit in floor.units
                    ]
                    floor_unit_count = len(unit_nodes)
                    building_units += floor_unit_count

                    floor_nodes.append(
                        ProjectStructureFloorNode(
                            id=floor.id,
                            name=floor.name,
                            code=floor.code,
                            sequence_number=floor.sequence_number,
                            level_number=floor.level_number,
                            status=floor.status,
                            unit_count=floor_unit_count,
                            units=unit_nodes,
                        )
                    )

                building_nodes.append(
                    ProjectStructureBuildingNode(
                        id=building.id,
                        name=building.name,
                        code=building.code,
                        status=building.status,
                        floor_count=len(floor_nodes),
                        unit_count=building_units,
                        floors=floor_nodes,
                    )
                )
                phase_floors += len(floor_nodes)
                phase_units += building_units

            phase_nodes.append(
                ProjectStructurePhaseNode(
                    id=phase.id,
                    name=phase.name,
                    code=phase.code,
                    sequence=phase.sequence,
                    phase_type=phase.phase_type if phase.phase_type else None,
                    status=phase.status,
                    building_count=len(building_nodes),
                    floor_count=phase_floors,
                    unit_count=phase_units,
                    buildings=building_nodes,
                )
            )
            total_buildings += len(building_nodes)
            total_floors += phase_floors
            total_units += phase_units

        return ProjectStructureResponse(
            project_id=project.id,
            project_name=project.name,
            project_code=project.code,
            project_status=project.status,
            phase_count=len(phase_nodes),
            building_count=total_buildings,
            floor_count=total_floors,
            unit_count=total_units,
            phases=phase_nodes,
        )
