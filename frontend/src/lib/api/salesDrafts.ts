import { download, get, post, put, remove } from "./client";
export type DraftPayload = Record<string, Record<string, unknown>[]>;
export interface SalesDraft { id: string; source_key: string; unit_id: string; version: number; status: "draft" | "added"; payload: DraftPayload; reservation_id: string | null; created_at: string }
const root = (project: string) => `/projects/${project}/sales/import-drafts`;
export const salesDrafts = {
  forReservation: (project: string, id: string) => get<SalesDraft | null>(`${root(project)}/by-reservation/${id}`),
  list: (project: string, offset: number) => get<SalesDraft[]>(`${root(project)}?offset=${offset}`),
  read: (project: string, id: string) => get<SalesDraft>(`${root(project)}/${id}`),
  fields: (project: string) => get<Record<string,string[]>>(`${root(project)}/fields`),
  save: (project: string, row: SalesDraft, payload: DraftPayload, reason: string) => put<SalesDraft>(`${root(project)}/${row.id}`, {version:row.version,payload,reason}),
  add: (project: string, row: SalesDraft, reason: string) => post<SalesDraft>(`${root(project)}/${row.id}/add`,{version:row.version,reason}),
  delete: (project: string, row: SalesDraft, reason: string) => remove(`${root(project)}/${row.id}?${new URLSearchParams({version:String(row.version),reason})}`),
  export: (project: string, id: string) => download(`${root(project)}/${id}/workbook`,"sales-draft.xlsx"),
};
