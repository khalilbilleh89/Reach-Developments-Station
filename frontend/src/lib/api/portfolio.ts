import { get } from "./client";
import type { Ratio, Fundamental } from "./analysis";

export type Coverage = "available" | "partial" | "unavailable";
export type MoneyMetric = {
  metric_code: string; currency: string; amount: string | null; availability: Coverage;
  reason: string | null; contributing_project_count: number; missing_project_count: number;
  source_basis: string; source_version_id: string | null; drilldown: string;
};
export type Risk = {
  risk_id: string; risk_code: string; category: string; severity: "high" | "attention";
  project_id: string; project_code: string; project_name: string; title: string; reason: string;
  source_metric: string; source_value: string; currency: string | null; basis: string;
  observation_date: string; availability: "available"; drilldown: string;
};
export type Evaluation = { risk_code: string; availability: Coverage; reason: string | null };
export type ProjectSummary = {
  project_id: string; code: string; name: string; status: string; currency: string; as_of: string;
  total_units: number; eligible_units: number; available_units: number; committed_units: number;
  active_sold_units: number; remaining_units: number; sales_penetration: Ratio;
  sales_run_rate: Fundamental["forecast"]; money: MoneyMetric[];
  cashflow_reason_code: string | null; cashflow_observed_currencies: string[]; permit_count: number;
  design: { availability: Coverage; reason: string | null; consultant_name: string | null;
    current_stage: string | null; planned_date: string | null; forecast_date: string | null;
    actual_date: string | null; stage_status: string | null; stage_count: number; deliverable_count: number };
  risks: Risk[]; risk_evaluations: Evaluation[]; risk_count: number;
  highest_risk: "high" | "attention" | null; coverage: Coverage; drilldown: string;
};
export type ProjectPage = { as_of: string; items: ProjectSummary[]; total: number; offset: number; limit: number };
export type RiskPage = { as_of: string; items: Risk[]; total: number; offset: number; limit: number; unavailable_project_count: number };
export type Overview = {
  as_of: string; project_count: number; projects_requiring_attention: number;
  projects_with_incomplete_coverage: number; eligible_units: number; committed_units: number;
  active_sold_units: number; sales_penetration: Ratio; money: MoneyMetric[]; risk_count: number;
  priority_risks: Risk[]; unavailable_risk_evaluations: Record<string, number>; source_basis: string;
};
export const portfolio = {
  overview: () => get<Overview>("/portfolio/overview"),
  projects: (offset: number) => get<ProjectPage>(`/portfolio/projects?limit=20&offset=${offset}`),
  risks: (offset: number) => get<RiskPage>(`/portfolio/risks?limit=20&offset=${offset}`),
  project: (id: string) => get<ProjectSummary>(`/portfolio/projects/${encodeURIComponent(id)}`),
};
