"""
project_structure.schemas

Pydantic response schemas for the Project Structure Viewer.

These contracts expose the canonical hierarchy:
  Project → Phase → Building → Floor → Unit

Each node includes id, name/code, status, child collections and summary counts
so that the frontend can render the full structure without additional requests.

Forbidden: ORM objects must not be returned directly; all values must come
through these typed contracts.
"""

from typing import List, Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Unit node (leaf)
# ---------------------------------------------------------------------------


class ProjectStructureUnitNode(BaseModel):
    """Leaf node representing a single inventory unit."""

    id: str
    unit_number: str
    unit_type: str
    status: str

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Floor node
# ---------------------------------------------------------------------------


class ProjectStructureFloorNode(BaseModel):
    """Floor node containing unit inventory."""

    id: str
    name: str
    code: str
    sequence_number: int
    level_number: Optional[int]
    status: str
    unit_count: int
    units: List[ProjectStructureUnitNode]

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Building node
# ---------------------------------------------------------------------------


class ProjectStructureBuildingNode(BaseModel):
    """Building node containing floors."""

    id: str
    name: str
    code: str
    status: str
    floor_count: int
    unit_count: int
    floors: List[ProjectStructureFloorNode]

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Phase node
# ---------------------------------------------------------------------------


class ProjectStructurePhaseNode(BaseModel):
    """Phase node containing buildings."""

    id: str
    name: str
    code: Optional[str]
    sequence: int
    phase_type: Optional[str]
    status: str
    building_count: int
    floor_count: int
    unit_count: int
    buildings: List[ProjectStructureBuildingNode]

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Top-level structure response
# ---------------------------------------------------------------------------


class ProjectStructureResponse(BaseModel):
    """Full project structure response — root of the hierarchy tree."""

    project_id: str
    project_name: str
    project_code: str
    project_status: str
    phase_count: int
    building_count: int
    floor_count: int
    unit_count: int
    phases: List[ProjectStructurePhaseNode]

    model_config = {"from_attributes": True}
