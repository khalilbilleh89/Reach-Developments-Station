/**
 * project-structure-types.ts — TypeScript types for the Project Structure Viewer.
 *
 * Mirrors the backend ProjectStructureResponse schema.
 * Project → Phase → Building → Floor → Unit
 *
 * Status and type literals mirror the backend shared enums so that
 * the TypeScript compiler catches mismatches at build time.
 *
 * Forbidden: no `any` types; field names must match backend contract exactly.
 */

// ---------------------------------------------------------------------------
// Shared status / type literals (mirror app/shared/enums/project.py)
// ---------------------------------------------------------------------------

export type UnitStatus = "available" | "reserved" | "under_contract" | "registered";

export type UnitType =
  | "studio"
  | "one_bedroom"
  | "two_bedroom"
  | "three_bedroom"
  | "four_bedroom"
  | "villa"
  | "townhouse"
  | "retail"
  | "office"
  | "penthouse";

export type FloorStatus = "planned" | "active" | "completed" | "on_hold";

export type BuildingStatus = "planned" | "under_construction" | "completed" | "on_hold";

export type PhaseStatus = "planned" | "active" | "completed";

export type PhaseType =
  | "concept"
  | "design"
  | "approvals"
  | "construction"
  | "sales"
  | "handover";

export type ProjectStatus = "pipeline" | "active" | "completed" | "on_hold";

// ---------------------------------------------------------------------------
// Unit node (leaf)
// ---------------------------------------------------------------------------

export interface ProjectStructureUnitNode {
  id: string;
  unit_number: string;
  unit_type: UnitType;
  status: UnitStatus;
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
  status: FloorStatus;
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
  status: BuildingStatus;
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
  phase_type: PhaseType | null;
  status: PhaseStatus;
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
  project_status: ProjectStatus;
  phase_count: number;
  building_count: number;
  floor_count: number;
  unit_count: number;
  phases: ProjectStructurePhaseNode[];
}
