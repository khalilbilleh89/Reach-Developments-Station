import { download, get, post, postBinary, put } from "./client";

export interface SiteReportFields {
  title: string;
  report_date: string;
  notes: string;
}
export interface SiteReport extends SiteReportFields { id: string; filename: string | null; source_url: string | null; version: number; created_at: string }
export interface SiteReportPreview { page_count: number; image: string }
const base = (projectId: string) => `/projects/${projectId}/technical-reports`;
export const siteReports = {
  list: (projectId: string) => get<SiteReport[]>(base(projectId)),
  create: async (projectId: string, fields: SiteReportFields, file: File) => {
    if (!file.size || file.size > 50 * 1024 * 1024 || !file.name.toLowerCase().endsWith(".pdf")) throw new Error("Choose a PDF up to 50 MB.");
    return postBinary<SiteReport>(`${base(projectId)}?${new URLSearchParams({ ...fields, filename: file.name })}`, await file.arrayBuffer());
  },
  createLink: (projectId: string, fields: SiteReportFields, sourceUrl: string) => post<SiteReport>(`${base(projectId)}/links`, { ...fields, source_url: sourceUrl }),
  update: (projectId: string, row: SiteReport, fields: SiteReportFields) => put<SiteReport>(`${base(projectId)}/${row.id}`, { ...fields, expected_version: row.version }),
  preview: (projectId: string, row: SiteReport, page: number) => get<SiteReportPreview>(`${base(projectId)}/${row.id}/preview?page=${page}`),
  download: (projectId: string, row: SiteReport) => download(`${base(projectId)}/${row.id}/document`, row.filename ?? "report.pdf"),
  remove: (projectId: string, row: SiteReport, reason: string) => post<void>(`${base(projectId)}/${row.id}/delete`, { reason, expected_version: row.version }),
};
