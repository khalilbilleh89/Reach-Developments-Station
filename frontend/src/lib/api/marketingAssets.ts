import { download, get, post, postBinary, put } from "./client";

export type AssetKind = "image" | "video" | "document";
export type AssetPlacement = "logo" | "material";
export type AssetMetadata = { title: string; category: string; notes: string };
export type AssetInput = AssetMetadata & { placement: AssetPlacement; kind: AssetKind; external_url: string | null };
export type MarketingAsset = AssetInput & { id: string; version: number; filename: string | null; media_type: string | null; byte_count: number; created_at: string };
export type AssetRegister = { total: number; items: MarketingAsset[]; categories: string[] };
const root = (id: string) => `/projects/${id}/marketing/assets`;
export const marketingAssets = {
  list: (id: string, placement: AssetPlacement, search: string, category: string, kind: string, offset: number) => get<AssetRegister>(`${root(id)}?${new URLSearchParams({ placement, search, category, offset: String(offset), limit: "25", ...(kind ? { kind } : {}) })}`),
  createLink: (id: string, body: AssetInput) => post<MarketingAsset>(`${root(id)}/links`, body),
  upload: async (id: string, body: AssetInput, file: File) => postBinary<MarketingAsset>(`${root(id)}/upload?${new URLSearchParams({ title: body.title, category: body.category, notes: body.notes, kind: body.kind, placement: body.placement, filename: file.name })}`, await file.arrayBuffer()),
  update: (id: string, row: MarketingAsset, body: AssetMetadata) => put<MarketingAsset>(`${root(id)}/${row.id}`, { ...body, expected_version: row.version }),
  remove: (id: string, row: MarketingAsset, reason: string) => post<void>(`${root(id)}/${row.id}/delete`, { expected_version: row.version, reason }),
  fileUrl: (id: string, row: MarketingAsset) => `/api/v1${root(id)}/${row.id}/file`,
  download: (id: string, row: MarketingAsset) => download(`${root(id)}/${row.id}/file?download=true`, row.filename ?? row.title),
};
