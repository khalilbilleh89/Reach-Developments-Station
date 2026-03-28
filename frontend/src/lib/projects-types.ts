/**
 * projects-types.ts — TypeScript types for the Projects domain.
 *
 * Mirrors the backend ProjectResponse schema and project attribute definition schemas.
 */

export type ProjectStatus = "pipeline" | "active" | "completed" | "on_hold";

export interface Project {
  id: string;
  name: string;
  code: string;
  developer_name: string | null;
  location: string | null;
  start_date: string | null;
  target_end_date: string | null;
  status: ProjectStatus;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectListResponse {
  items: Project[];
  total: number;
}

export interface ProjectCreate {
  name: string;
  code: string;
  developer_name?: string | null;
  location?: string | null;
  start_date?: string | null;
  target_end_date?: string | null;
  status?: ProjectStatus;
  description?: string | null;
}

export interface ProjectUpdate {
  name?: string;
  developer_name?: string | null;
  location?: string | null;
  start_date?: string | null;
  target_end_date?: string | null;
  status?: ProjectStatus;
  description?: string | null;
}

export interface ProjectSummary {
  project_id: string;
  total_phases: number;
  active_phases: number;
  planned_phases: number;
  completed_phases: number;
  earliest_start_date: string | null;
  latest_target_completion: string | null;
}

/**
 * Cross-module lifecycle readiness summary for a project.
 *
 * Mirrors backend ProjectLifecycleSummaryResponse.
 * All stage values are derived from real module records by the backend.
 */
export type ProjectLifecycleStage =
  | "land_defined"
  | "scenario_defined"
  | "feasibility_ready"
  | "feasibility_calculated"
  | "structure_ready"
  | "construction_baseline_pending"
  | "construction_monitored"
  | "portfolio_visible";

export interface ProjectLifecycleSummary {
  project_id: string;
  // Presence flags
  has_scenarios: boolean;
  has_active_scenario: boolean;
  has_feasibility_runs: boolean;
  has_calculated_feasibility: boolean;
  has_phases: boolean;
  has_construction_records: boolean;
  has_approved_tender_baseline: boolean;
  // Counts
  scenario_count: number;
  feasibility_run_count: number;
  construction_record_count: number;
  // Derived lifecycle state
  current_stage: ProjectLifecycleStage;
  recommended_next_step: string;
  next_step_route: string | null;
  blocked_reason: string | null;
  last_updated_at: string;
}

// ---------------------------------------------------------------------------
// Project Attribute Definitions & Options
// ---------------------------------------------------------------------------

/** Currently supported attribute definition keys. */
export type AttributeDefinitionKey = "view_type";

export interface ProjectAttributeOption {
  id: string;
  definition_id: string;
  value: string;
  label: string;
  sort_order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProjectAttributeDefinition {
  id: string;
  project_id: string;
  key: AttributeDefinitionKey;
  label: string;
  input_type: string;
  is_active: boolean;
  options: ProjectAttributeOption[];
  created_at: string;
  updated_at: string;
}

export interface AttributeDefinitionListResponse {
  items: ProjectAttributeDefinition[];
  total: number;
}

export interface AttributeDefinitionCreate {
  key: AttributeDefinitionKey;
  label: string;
  input_type?: string;
}

export interface AttributeDefinitionUpdate {
  label?: string;
  is_active?: boolean;
}

export interface AttributeOptionCreate {
  value: string;
  label: string;
  sort_order?: number;
}

export interface AttributeOptionUpdate {
  label?: string;
  sort_order?: number;
  is_active?: boolean;
}
