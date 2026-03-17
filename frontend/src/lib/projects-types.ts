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
