/**
 * project-phases-types.ts — TypeScript types for the Project Lifecycle & Phase Management Engine.
 *
 * Mirrors the backend PhaseResponse and ProjectLifecycle schemas.
 * Extends the base Phase type with lifecycle-specific fields (phase_type, is_current).
 */

export type PhaseStatus = "planned" | "active" | "completed";

export type PhaseType =
  | "concept"
  | "design"
  | "approvals"
  | "construction"
  | "sales"
  | "handover";

export interface ProjectPhase {
  id: string;
  project_id: string;
  name: string;
  code: string | null;
  sequence: number;
  phase_type: PhaseType | null;
  status: PhaseStatus;
  start_date: string | null;
  end_date: string | null;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectPhaseListResponse {
  items: ProjectPhase[];
  total: number;
}

export interface LifecyclePhaseItem {
  id: string;
  project_id: string;
  name: string;
  code: string | null;
  sequence: number;
  phase_type: PhaseType | null;
  status: PhaseStatus;
  start_date: string | null;
  end_date: string | null;
  description: string | null;
  is_current: boolean;
}

export interface ProjectLifecycle {
  project_id: string;
  phases: LifecyclePhaseItem[];
  current_phase_type: PhaseType | null;
  current_sequence: number | null;
}

export interface ProjectPhaseCreate {
  name: string;
  code?: string | null;
  sequence: number;
  phase_type?: PhaseType | null;
  status?: PhaseStatus;
  start_date?: string | null;
  end_date?: string | null;
  description?: string | null;
}

export interface ProjectPhaseUpdate {
  name?: string;
  code?: string | null;
  sequence?: number;
  phase_type?: PhaseType | null;
  status?: PhaseStatus;
  start_date?: string | null;
  end_date?: string | null;
  description?: string | null;
}
