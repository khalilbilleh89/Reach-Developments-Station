/**
 * projects-types.ts — TypeScript types for the Projects domain.
 *
 * Mirrors the backend ProjectResponse schema.
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
