/**
 * phases-types.ts — TypeScript types for the Phases domain.
 *
 * Mirrors the backend PhaseResponse schema.
 */

export type PhaseStatus = "planned" | "active" | "completed";

export interface Phase {
  id: string;
  project_id: string;
  name: string;
  code: string | null;
  sequence: number;
  status: PhaseStatus;
  start_date: string | null;
  end_date: string | null;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface PhaseListResponse {
  items: Phase[];
  total: number;
}

export interface PhaseCreate {
  name: string;
  code?: string | null;
  sequence: number;
  status?: PhaseStatus;
  start_date?: string | null;
  end_date?: string | null;
  description?: string | null;
}

export interface PhaseUpdate {
  name?: string;
  code?: string | null;
  sequence?: number;
  status?: PhaseStatus;
  start_date?: string | null;
  end_date?: string | null;
  description?: string | null;
}
