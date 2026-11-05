import { download, get, post, postBinary, put } from "./client";

export type AssetKind = "video" | "document";
export type AssetMetadata = { title: string; category: string; description: string; execution_date: string };
export type AssetInput = AssetMetadata & { kind: AssetKind; external_url: string | null };
export type TrainingMaterial = AssetInput & { id: string; version: number; filename: string | null; media_type: string | null; byte_count: number; created_at: string };
export type AssetRegister = { total: number; items: TrainingMaterial[]; categories: string[] };
const root = (id: string) => `/projects/${id}/training`;
export const training = {
  list: (id: string, search: string, category: string, kind: string, offset: number) => get<AssetRegister>(`${root(id)}?${new URLSearchParams({ search, category, offset: String(offset), limit: "25", ...(kind ? { kind } : {}) })}`),
  createLink: (id: string, body: AssetInput) => post<TrainingMaterial>(`${root(id)}/links`, body),
  upload: async (id: string, body: AssetInput, file: File) => postBinary<TrainingMaterial>(`${root(id)}/upload?${new URLSearchParams({ title: body.title, category: body.category, description: body.description, execution_date: body.execution_date, kind: body.kind, filename: file.name })}`, await file.arrayBuffer()),
  update: (id: string, row: TrainingMaterial, body: AssetMetadata) => put<TrainingMaterial>(`${root(id)}/${row.id}`, { ...body, expected_version: row.version }),
  remove: (id: string, row: TrainingMaterial, reason: string) => post<void>(`${root(id)}/${row.id}/delete`, { expected_version: row.version, reason }),
  fileUrl: (id: string, row: TrainingMaterial) => `/api/v1${root(id)}/${row.id}/file`,
  download: (id: string, row: TrainingMaterial) => download(`${root(id)}/${row.id}/file?download=true`, row.filename ?? row.title),
};
