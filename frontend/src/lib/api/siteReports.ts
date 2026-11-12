import { download, get, post, postBinary, put } from "./client";

export type ReportKind = "site_report" | "architect_certificate" | "client_charter";
export const reportSections = {
  site_report: { label: "Site reports", singular: "report", add: "Add report", title: "Report title", description: "Site engineer reports in one place: the latest visit first, earlier reports beneath." },
  architect_certificate: { label: "Completion certificates", singular: "certificate", add: "Add certificate", title: "Certificate name", description: "Completion certificates issued by the main architect, linked to a building or selected units. Contractor payment certificates remain in Construction." },
  client_charter: { label: "Client charters", singular: "charter", add: "Add client charter", title: "Charter title", description: "Client charters linked to individual units, with the original PDF or Google Drive source." },
} as const;
export const applicabilityOf = (row: SiteReport) => row.building_label ?? row.unit_labels?.join(", ") ?? "";
export interface ReportTargets { buildings: { id: string; label: string }[]; units: { id: string; label: string; building_id: string }[] }
export interface SiteReportFields {
  kind?: ReportKind;
  building_id?: string | null;
  unit_ids?: string[];
  title: string;
  report_date: string | null;
  notes: string;
}
export interface SiteReport extends SiteReportFields { id: string; building_label?: string | null; unit_labels?: string[]; filename: string | null; source_url: string | null; version: number; created_at: string }
export interface SiteReportPreview { page_count: number; image: string }
const base = (projectId: string) => `/projects/${projectId}/technical-reports`;
export const siteReports = {
  list: (projectId: string, kind: ReportKind = "site_report") => get<SiteReport[]>(`${base(projectId)}?kind=${kind}`),
  targets: (projectId: string) => get<ReportTargets>(`${base(projectId)}/targets`),
  create: async (projectId: string, fields: SiteReportFields, file: File) => {
    if (!file.size || file.size > 50 * 1024 * 1024 || !file.name.toLowerCase().endsWith(".pdf")) throw new Error("Choose a PDF up to 50 MB.");
    const query = new URLSearchParams({ title: fields.title, notes: fields.notes, kind: fields.kind ?? "site_report", filename: file.name });
    if (fields.report_date) query.set("report_date", fields.report_date);
    if (fields.building_id) query.set("building_id", fields.building_id);
    fields.unit_ids?.forEach(id => query.append("unit_ids", id));
    return postBinary<SiteReport>(`${base(projectId)}?${query}`, await file.arrayBuffer());
  },
  createLink: (projectId: string, fields: SiteReportFields, sourceUrl: string) => post<SiteReport>(`${base(projectId)}/links`, { ...fields, source_url: sourceUrl }),
  update: (projectId: string, row: SiteReport, fields: SiteReportFields) => put<SiteReport>(`${base(projectId)}/${row.id}`, { ...fields, expected_version: row.version }),
  preview: (projectId: string, row: SiteReport, page: number) => get<SiteReportPreview>(`${base(projectId)}/${row.id}/preview?page=${page}`),
  download: (projectId: string, row: SiteReport) => download(`${base(projectId)}/${row.id}/document`, row.filename ?? "report.pdf"),
  remove: (projectId: string, row: SiteReport, reason: string) => post<void>(`${base(projectId)}/${row.id}/delete`, { reason, expected_version: row.version }),
};
