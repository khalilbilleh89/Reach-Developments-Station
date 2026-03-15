/**
 * floors-types.ts — TypeScript types for the Floors domain.
 *
 * Mirrors the backend FloorResponse schema.
 */

export type FloorStatus = "planned" | "active" | "completed" | "on_hold";

export interface Floor {
  id: string;
  building_id: string;
  name: string;
  code: string;
  sequence_number: number;
  level_number: number | null;
  status: FloorStatus;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface FloorListResponse {
  items: Floor[];
  total: number;
}

export interface FloorCreate {
  name: string;
  code: string;
  sequence_number: number;
  level_number?: number | null;
  status?: FloorStatus;
  description?: string | null;
}

export interface FloorUpdate {
  name?: string;
  level_number?: number | null;
  status?: FloorStatus;
  description?: string | null;
}
