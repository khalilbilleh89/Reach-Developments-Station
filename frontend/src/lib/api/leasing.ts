import { get, post, put } from "./client";

export type LeasingStage = "draft" | "marketing" | "negotiating" | "leased" | "closed";
export type LeasingProject = { id: string; name: string; code: string; currency_code: string };
export type LeasingClient = { id: string; display_name: string; client_number: string; is_active: boolean };
export type LeasingUnit = { id: string; unit_reference: string; building: string | null; floor: string | null; is_active: boolean };
export type LeasingSource = {
  unit: LeasingUnit; project_name: string; location: string | null; currency_code: string;
  asset_class: string; bedrooms: number | null; bathrooms: number | null; furnishing: string | null;
  delivery_status: string; internal_area: string | null; area_unit: string | null;
  sale_client: LeasingClient | null; sale_reference: string | null;
};
export type LeasingTerms = {
  owner_client_id: string | null; status: LeasingStage; mandate_date: string | null; mandate_reference: string;
  asking_rent_monthly: string | null; available_from: string | null; tenant_name: string;
  agreed_rent_monthly: string | null; security_deposit: string | null;
  lease_start: string | null; lease_end: string | null; agreement_reference: string;
  next_action: string; follow_up_date: string | null; notes: string;
};
export type LeasingRow = LeasingTerms & {
  id: string; project_id: string; unit_id: string; currency_id: string; currency_code: string; version: number;
  created_at: string; updated_at: string; project_name: string; unit_reference: string; owner_name: string | null; attention: string[];
};
export type LeasingDetail = LeasingRow & { source: LeasingSource; owner: LeasingClient | null; owner_matches_sale: boolean | null };
export type LeasingRegister = { items: LeasingRow[]; total: number; counts: Record<string, number>; as_at: string };
export const LEASING_STAGES: { key: LeasingStage; label: string }[] = [
  { key: "draft", label: "Instruction" }, { key: "marketing", label: "On market" },
  { key: "negotiating", label: "Negotiating" }, { key: "leased", label: "Leased" }, { key: "closed", label: "Closed" },
];
const root = (project: string) => `/projects/${project}/leasing`;
export const leasing = {
  projects: () => get<LeasingProject[]>("/leasing/projects"),
  list: (project: string, search: string, stage: string, focus: string, offset: number) => get<LeasingRegister>(`/leasing?${new URLSearchParams({ ...(project ? { project_id: project } : {}), search, ...(stage ? { stage } : {}), ...(focus ? { focus } : {}), offset: String(offset) })}`),
  units: (project: string, search: string, offset: number) => get<{ items: LeasingUnit[]; total: number }>(`${root(project)}/units?${new URLSearchParams({ search, offset: String(offset) })}`),
  clients: (project: string, search: string) => get<LeasingClient[]>(`${root(project)}/clients?${new URLSearchParams({ search })}`),
  source: (project: string, unit: string) => get<LeasingSource>(`${root(project)}/units/${unit}`),
  detail: (row: Pick<LeasingRow, "project_id" | "id">) => get<LeasingDetail>(`${root(row.project_id)}/${row.id}`),
  create: (project: string, unit: string, values: LeasingTerms) => post<LeasingDetail>(root(project), { ...values, unit_id: unit }),
  update: (row: LeasingRow, values: LeasingTerms, reason: string) => put<LeasingDetail>(`${root(row.project_id)}/${row.id}`, { ...values, expected_version: row.version, reason }),
  remove: (row: LeasingRow, reason: string) => post<void>(`${root(row.project_id)}/${row.id}/delete`, { expected_version: row.version, reason }),
};
