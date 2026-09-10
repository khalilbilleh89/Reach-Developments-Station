import { get, post } from "./client";
import type { Overview, ProjectSummary, Risk } from "./portfolio";
import type { Identity, Outlook } from "./management";

export type SnapshotHeader = {
  id: string; scope_type: "portfolio" | "project"; project_id: string | null; label: string | null;
  as_of_date: string; captured_at: string; created_by_user_id: string; creator_display_name: string;
  schema_version: number; project_count: number; incomplete_project_count: number; content_hash: string;
};
export type CapturedAction = { id: string; project_id: string; title: string; owner: Identity; due_date: string; status: string; source_type: string; source_code: string | null; created_at: string; updated_at: string; version: number };
export type Snapshot = SnapshotHeader & { payload: { overview: Overview; projects: ProjectSummary[]; outlooks: Outlook[]; actions: CapturedAction[]; development: { project_id: string; source_id: string; kind: string; label: string; status: string; due_date: string | null; blocking: boolean | null; planned_date: string | null; forecast_date: string | null; actual_date: string | null }[]; action_frontier: { id: string; project_id: string; version: number }[]; action_counts: { open: number; in_progress: number; overdue: number; completed: number; cancelled: number } } };
export type SnapshotPage = { items: SnapshotHeader[]; total: number; limit: number; offset: number };
export type Movement = { section: string; metric: string; project_id: string | null; project_code: string | null; currency: string | null; prior_currency: string | null; current_currency: string | null; unit: string; prior: string | null; current: string | null; delta: string | null; prior_availability: string; current_availability: string; comparable: boolean; reason: string | null; basis: string };
export type Comparison = {
  prior: SnapshotHeader; current: SnapshotHeader; composition_changed: boolean;
  added_projects: { project_id: string; code: string; name: string }[];
  removed_projects: { project_id: string; code: string; name: string }[];
  common_projects: { project_id: string; code: string; name: string }[];
  movements: Movement[];
  facts: { section: string; project_id: string; project_code: string; fact: string; prior: string | null; current: string | null }[];
  risks: { classification: string; prior: Risk | null; current: Risk | null; reason: string | null }[];
  execution: { created: number; started: number; completed: number; reopened: number; cancelled: number; prior_overdue: number; current_overdue: number; basis: string };
};
export type BoardPack = { snapshot: Snapshot; comparison: Comparison | null; historical_notice: string; section_order: string[] };
function query(values: Record<string, string | number | undefined>) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) if (value !== undefined && value !== "") params.set(key, String(value));
  return params.toString();
}
export const reporting = {
  list: (filters: Record<string, string | number | undefined>) => get<SnapshotPage>(`/portfolio/reporting/snapshots?${query(filters)}`),
  capture: (payload: { scope: "portfolio" | "project"; project_id?: string; label?: string }) => post<Snapshot>("/portfolio/reporting/snapshots", payload),
  detail: (id: string) => get<Snapshot>(`/portfolio/reporting/snapshots/${encodeURIComponent(id)}`),
  compare: (prior: string, current: string) => get<Comparison>(`/portfolio/reporting/comparisons?${query({ from_snapshot_id: prior, to_snapshot_id: current })}`),
  board: (id: string, prior?: string) => get<BoardPack>(`/portfolio/reporting/snapshots/${encodeURIComponent(id)}/board-pack?${query({ compare_to_snapshot_id: prior })}`),
};
