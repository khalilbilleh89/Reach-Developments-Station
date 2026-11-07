import { get } from "./client";
import type { Context } from "./analysis";

export type ReportPoint = { label: string; value: string | null; scale_percentage: string; share_percentage: string | null };
export type ReportChart = { key: string; title: string; category: string; kind: "bars" | "columns" | "donut"; unit: string; points: ReportPoint[]; insight: string; source: string; note: string | null };
export type AnalyticsReport = { project_name: string; generated_at: string; context: Context; threshold: string; currency: string; metrics: { label: string; value: string | null; unit: string; note: string }[]; charts: ReportChart[]; notices: string[] };
export const analyticsReport = (projectId: string, query: string) => get<AnalyticsReport>(`/projects/${projectId}/analysis/report?${query}`);
