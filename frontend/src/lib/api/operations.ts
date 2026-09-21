import { get, put, remove } from "./client";

export type OperationSection = "property_purchase" | "golden_visa";
export type PurchasePurpose = "investment_only" | "golden_visa" | null;
export interface OperationStage {
  id: string; label: string; section: OperationSection; position: number;
  source: "manual" | "buyer_signed_spa"; is_active: boolean;
}
export interface OperationMilestone {
  stage_id: string; completed: boolean | null; completed_date: string | null;
  applicable: boolean | null; source: string; editable: boolean; signed_sales: number; total_sales: number;
}
export interface OperationBuyer {
  id: string; number: string; name: string; active: boolean; purpose: PurchasePurpose; version: number;
  purchases: {id: string; number: string; kind: "sale" | "reservation"; status: string}[];
  milestones: OperationMilestone[]; completed_count: number; applicable_count: number; next_stage: string | null;
}
export interface OperationsData {
  pipeline_version: number; stages: OperationStage[]; buyers: OperationBuyer[];
  summaries: {stage_id: string; yes: number; no: number; unrecorded: number; not_applicable: number; purpose_unknown: number; applicable: number; missing_dates: number}[];
  buyer_count: number; golden_visa_count: number; investment_count: number; purpose_unknown_count: number;
  can_configure: boolean; can_edit: boolean;
}
export interface StageDraft { id: string | null; label: string; section: OperationSection; is_active: boolean }
export interface ProgressDraft { stage_id: string; completed: boolean | null; completed_date: string | null }
const base = (project: string) => `/projects/${project}/operations`;
export const operations = {
  read: (project: string) => get<OperationsData>(base(project)),
  savePipeline: (project: string, expected_version: number, stages: StageDraft[]) => put<void>(`${base(project)}/pipeline`, {expected_version, stages}),
  saveBuyer: (project: string, id: string, expected_version: number, pipeline_version: number, purpose: PurchasePurpose, progress: ProgressDraft[], reason: string) => put<void>(`${base(project)}/buyers/${id}`, {expected_version, pipeline_version, purpose, progress, reason}),
  deleteStage: (project: string, id: string, version: number, reason: string) => remove(`${base(project)}/stages/${id}?${new URLSearchParams({version: String(version), reason})}`),
  deleteProgress: (project: string, id: string, version: number, reason: string) => remove(`${base(project)}/buyers/${id}?${new URLSearchParams({version: String(version), reason})}`),
};
