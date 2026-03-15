/**
 * buildings-types.ts — TypeScript types for the Buildings domain.
 *
 * Mirrors the backend BuildingResponse schema.
 */

export type BuildingStatus =
  | "planned"
  | "under_construction"
  | "completed"
  | "on_hold";

export interface Building {
  id: string;
  phase_id: string;
  name: string;
  code: string;
  floors_count: number | null;
  status: BuildingStatus;
  created_at: string;
  updated_at: string;
}

export interface BuildingListResponse {
  items: Building[];
  total: number;
}

export interface BuildingCreate {
  name: string;
  code: string;
  floors_count?: number | null;
  status?: BuildingStatus;
}

export interface BuildingUpdate {
  name?: string;
  floors_count?: number | null;
  status?: BuildingStatus;
}
