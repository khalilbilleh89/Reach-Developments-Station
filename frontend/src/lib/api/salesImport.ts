import { download, postBinary } from "./client";
export type ImportKind = "buyers" | "agents" | "faqs" | "sales-drafts";
export interface SalesImportReport {
  total_rows: number; created_count: number; applied: boolean; error_count: number;
  issues: { row: number; column: string | null; message: string }[];
  issues_truncated: boolean;
  new_count?: number | null; duplicate_count?: number;
  duplicates?: { row: number; source: "existing" | "file" }[];
  duplicates_truncated?: boolean;
}
const root = (projectId: string, kind: ImportKind) => kind === "sales-drafts" ? `/projects/${projectId}/sales/import-drafts` : kind === "faqs" ? `/projects/${projectId}/faqs/import` : `/projects/${projectId}/sales/import/${kind}`;
export const salesImport = {
  template: (projectId: string, kind: ImportKind) => download(`${root(projectId, kind)}/template`, `${kind}-template.xlsx`),
  run: (projectId: string, kind: ImportKind, operation: "validate" | "apply", bytes: ArrayBuffer) =>
    postBinary<SalesImportReport>(`${root(projectId, kind)}/${kind === "sales-drafts" ? "workbook/" : ""}${operation}`, bytes),
};
