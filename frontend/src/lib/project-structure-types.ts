/**
 * project-structure-types.ts — TypeScript types for the Project Structure Viewer.
 *
 * Mirrors the backend ProjectStructureResponse schema.
 * Project → Phase → Building → Floor → Unit
 *
 * Forbidden: no `any` types; field names must match backend contract exactly.
 */

// ---------------------------------------------------------------------------
// Unit node (leaf)
// ---------------------------------------------------------------------------

export interface ProjectStructureUnitNode {
  id: string;
  unit_number: string;
  unit_type: string;
  status: string;
}

// ---------------------------------------------------------------------------
// Floor node
// ---------------------------------------------------------------------------

export interface ProjectStructureFloorNode {
  id: string;
  name: string;
  code: string;
  sequence_number: number;
  level_number: number | null;
  status: string;
  unit_count: number;
  units: ProjectStructureUnitNode[];
}

// ---------------------------------------------------------------------------
// Building node
// ---------------------------------------------------------------------------

export interface ProjectStructureBuildingNode {
  id: string;
  name: string;
  code: string;
  status: string;
  floor_count: number;
  unit_count: number;
  floors: ProjectStructureFloorNode[];
}

// ---------------------------------------------------------------------------
// Phase node
// ---------------------------------------------------------------------------

export interface ProjectStructurePhaseNode {
  id: string;
  name: string;
  code: string | null;
  sequence: number;
  phase_type: string | null;
  status: string;
  building_count: number;
  floor_count: number;
  unit_count: number;
  buildings: ProjectStructureBuildingNode[];
}

// ---------------------------------------------------------------------------
// Top-level structure response
// ---------------------------------------------------------------------------

export interface ProjectStructureResponse {
  project_id: string;
  project_name: string;
  project_code: string;
  project_status: string;
  phase_count: number;
  building_count: number;
  floor_count: number;
  unit_count: number;
  phases: ProjectStructurePhaseNode[];
}
