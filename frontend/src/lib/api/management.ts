import { get, patch, post } from "./client";
import type { Fundamental } from "./analysis";

export type ActionStatus = "open" | "in_progress" | "completed" | "cancelled";
export type Identity = { user_id: string; display_name: string };
export type ActionSource = { source_type: "manual" | "portfolio_risk" | "portfolio_outlook"; source_code?: string | null; source_key?: string | null; source_observation_date?: string | null };
export type ManagementAction = ActionSource & {
  id: string; project_id: string; project_code: string; project_name: string; title: string; description: string | null;
  owner: Identity; created_by: Identity; due_date: string; due_state: string; status: ActionStatus;
  created_at: string; updated_at: string; completed_at: string | null; cancelled_at: string | null; version: number;
};
export type ActionPage = { as_of: string; due_soon_days: number; items: ManagementAction[]; total: number; offset: number; limit: number };
export type HistoryPage = { items: { id: string; version: number; actor: Identity; occurred_at: string; event_type: string; reason: string | null; changes: Record<string, { old: string | null; new: string | null }> }[]; total: number; offset: number; limit: number };
export type ActionSummary = { open_count: number; overdue_count: number; next_due_date: string | null; source_linked_open_count: number };
export type OutlookItem = {
  source_key: string; item_type: string; project_id: string; project_code: string; project_name: string; title: string;
  due_date: string | null; observation_date: string; availability: string; reason: string | null; basis: string;
  currency: string | null; amount: string | null; source_version_id: string | null; source_as_of: string | null;
  status: string | null; blocking: boolean | null; planned_date: string | null; forecast_date: string | null; actual_date: string | null;
  lowpoint_month: string | null; first_deficit_month: string | null; peak_deficit: string | null; forecast_end_month: string | null;
  control_budget: string | null; budget_version_id: string | null; commercial: Fundamental["forecast"] | null;
  owner_user_id: string | null; owner_display_name: string | null; drilldown: string;
};
export type Outlook = {
  as_of: string; horizon_days: number; horizon_end: string; date_basis: string; cashflow_basis: string; authorized_project_count: number;
  summary_counts: Record<string, number>; currency_buckets: { currency: string; scheduled_outstanding_due: string; contributing_project_count: number; unavailable_project_count: number }[];
  coverage: { source: string; unavailable_project_count: number; undated_item_count: number; reason: string }[];
  items: OutlookItem[]; total: number; offset: number; limit: number;
};
function query(values: Record<string, string | number | undefined>) {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => { if (value !== undefined && value !== "") params.set(key, String(value)); });
  return params.toString();
}
export const management = {
  list: (filters: Record<string, string | number | undefined>) => get<ActionPage>(`/portfolio/actions?${query(filters)}`),
  detail: (id: string) => get<ManagementAction>(`/portfolio/actions/${encodeURIComponent(id)}`),
  history: (id: string, offset: number) => get<HistoryPage>(`/portfolio/actions/${encodeURIComponent(id)}/history?limit=20&offset=${offset}`),
  source: (id: string) => get<{ state: string; title: string; drilldown: string | null }>(`/portfolio/actions/${encodeURIComponent(id)}/source`),
  assignees: (project: string) => get<Identity[]>(`/portfolio/actions/assignees?project_id=${encodeURIComponent(project)}`),
  owners: (project?: string) => get<Identity[]>(`/portfolio/actions/owners?${query({ project_id: project })}`),
  projects: (offset: number) => get<{ items: { id: string; code: string; name: string }[]; total: number }>(`/portfolio/actions/projects?limit=100&offset=${offset}`),
  summary: (project?: string) => get<ActionSummary>(`/portfolio/actions/summary?${query({ project_id: project })}`),
  create: (payload: ActionSource & { project_id: string; title: string; description: string | null; owner_user_id: string; due_date: string }) => post<ManagementAction>("/portfolio/actions", payload),
  update: (id: string, payload: Record<string, unknown>) => patch<ManagementAction>(`/portfolio/actions/${encodeURIComponent(id)}`, payload),
  transition: (id: string, expected_version: number, status: ActionStatus, reason: string | null) => post<ManagementAction>(`/portfolio/actions/${encodeURIComponent(id)}/transitions`, { expected_version, status, reason }),
  outlook: (horizon: number, offset: number, kind?: string, project?: string) => get<Outlook>(`/portfolio/outlook?${query({ horizon_days: horizon, offset, limit: 20, item_type: kind, project_id: project })}`),
};
