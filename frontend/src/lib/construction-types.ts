/**
 * construction-types.ts — TypeScript types for the Construction domain.
 *
 * Mirrors the backend ConstructionScopeResponse and ConstructionMilestoneResponse schemas.
 */

export type ConstructionStatus = "planned" | "in_progress" | "on_hold" | "completed";

export type MilestoneStatus = "pending" | "in_progress" | "completed" | "delayed";

export interface ConstructionScope {
  id: string;
  project_id: string | null;
  phase_id: string | null;
  building_id: string | null;
  name: string;
  description: string | null;
  status: ConstructionStatus;
  start_date: string | null;
  target_end_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConstructionScopeListResponse {
  items: ConstructionScope[];
  total: number;
}

export interface ConstructionScopeCreate {
  project_id?: string | null;
  phase_id?: string | null;
  building_id?: string | null;
  name: string;
  description?: string | null;
  status?: ConstructionStatus;
  start_date?: string | null;
  target_end_date?: string | null;
}

export interface ConstructionScopeUpdate {
  name?: string;
  description?: string | null;
  status?: ConstructionStatus;
  start_date?: string | null;
  target_end_date?: string | null;
}

export interface ConstructionMilestone {
  id: string;
  scope_id: string;
  name: string;
  description: string | null;
  sequence: number;
  status: MilestoneStatus;
  target_date: string | null;
  completion_date: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConstructionMilestoneListResponse {
  items: ConstructionMilestone[];
  total: number;
}

export interface ConstructionMilestoneCreate {
  scope_id: string;
  name: string;
  description?: string | null;
  sequence: number;
  status?: MilestoneStatus;
  target_date?: string | null;
  completion_date?: string | null;
  notes?: string | null;
}

export interface ConstructionMilestoneUpdate {
  name?: string;
  description?: string | null;
  sequence?: number;
  status?: MilestoneStatus;
  target_date?: string | null;
  completion_date?: string | null;
  notes?: string | null;
}
