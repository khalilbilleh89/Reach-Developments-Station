import { get, post, put } from "./client";
export interface ProcedureStep { id: string; kind: "start" | "action" | "decision" | "end"; title: string; description: string; inputs: string; outputs: string; owner: string; next_id: string | null; yes_id: string | null; no_id: string | null }
export interface ProcedureFields { title: string; objective: string; sop: string; inputs: string; outputs: string; steps: ProcedureStep[] }
export interface ProcedureRecord extends ProcedureFields { id: string; project_id: string; version: number }
const root = (id: string) => `/projects/${id}/procedures`;
export const procedures = {
 list: (id: string) => get<{ procedures: ProcedureRecord[]; can_manage: boolean }>(root(id)),
 create: (id: string, body: ProcedureFields) => post<ProcedureRecord>(root(id), { ...body }),
 update: (id: string, row: ProcedureRecord, body: ProcedureFields) => put<ProcedureRecord>(`${root(id)}/${row.id}`, { ...body, version: row.version }),
 remove: (id: string, row: ProcedureRecord, reason: string) => post<void>(`${root(id)}/${row.id}/delete`, { version: row.version, reason }),
};
