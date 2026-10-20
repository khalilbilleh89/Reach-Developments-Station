import { get, post, put } from "./client";
export type Framework = "swot" | "pestel" | "porter" | "bcg" | "ansoff" | "fishbone";
export interface MatrixItem { label: string; notes: string; category: string; growth_pct: string | null; relative_share: string | null }
export interface MatrixFields { title: string; framework: Framework; as_of: string; context: string; effect: string; growth_threshold_pct: string; items: MatrixItem[] }
export interface MatrixPoint { label: string; category: string; x: number; y: number }
export interface MatrixRecord extends MatrixFields { id: string; project_id: string; version: number; points: MatrixPoint[] }
const root = (id: string) => `/projects/${id}/matrices`;
export const matrices = {
 list: (id: string) => get<{ analyses: MatrixRecord[]; can_manage: boolean }>(root(id)),
 create: (id: string, body: MatrixFields) => post<MatrixRecord>(root(id), { ...body }),
 update: (id: string, row: MatrixRecord, body: MatrixFields) => put<MatrixRecord>(`${root(id)}/${row.id}`, { ...body, version: row.version }),
 preview: (id: string, body: MatrixFields) => post<MatrixPoint[]>(`${root(id)}/preview`, { ...body }),
 remove: (id: string, row: MatrixRecord, reason: string) => post<void>(`${root(id)}/${row.id}/delete`, { version: row.version, reason }),
};
