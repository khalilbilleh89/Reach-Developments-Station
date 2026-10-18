import { download, get, post, postBinary, put, remove } from "./client";
import { inventory } from "./index";
import type { UnitSummary } from "./types";

export type Point = [number, number];
export type Masterplan = {
  id: string; project_id: string; title: string; source_reference: string;
  filename: string; kind: "plan" | "render" | "elevation"; page_number: number;
  pixel_width: number; pixel_height: number; width_m: string | null; version: number;
};
export type FootprintInput = { unit_id: string; points: Point[]; base_m: string; height_m: string };
export type Footprint = FootprintInput & { id: string; plan_id: string; version: number };
export type PlanInput = { title: string; source_reference: string; kind: Masterplan["kind"]; width_m: string | null };
const root = (project: string) => `/projects/${project}/inventory/masterplans`;

export const masterplans = {
  list: (project: string) => get<Masterplan[]>(root(project)),
  source: (project: string, plan: Masterplan) => download(`${root(project)}/${plan.id}/source`, plan.filename),
  upload: async (project: string, file: File, values: PlanInput, page: number) => {
    const query = new URLSearchParams({ title: values.title, source_reference: values.source_reference, kind: values.kind, filename: file.name, page_number: String(page) });
    if (values.width_m) query.set("width_m", values.width_m);
    return postBinary<Masterplan>(`${root(project)}?${query}`, await file.arrayBuffer());
  },
  update: (project: string, plan: Masterplan, values: PlanInput) => put<Masterplan>(`${root(project)}/${plan.id}`, { ...values, version: plan.version }),
  mappings: (project: string, plan: string) => get<Footprint[]>(`${root(project)}/${plan}/mappings`),
  preview: (project: string, plan: string) => `/api/v1${root(project)}/${plan}/preview`,
  saveMapping: (project: string, plan: string, values: FootprintInput, existing?: Footprint) => existing
    ? put<Footprint>(`${root(project)}/${plan}/mappings/${existing.id}`, { ...values, version: existing.version })
    : post<Footprint>(`${root(project)}/${plan}/mappings`, values),
  removePlan: (project: string, plan: Masterplan, reason: string) => remove(`${root(project)}/${plan.id}?${new URLSearchParams({ version: String(plan.version), reason })}`),
  removeMapping: (project: string, plan: string, mapping: Footprint, reason: string) => remove(`${root(project)}/${plan}/mappings/${mapping.id}?${new URLSearchParams({ version: String(mapping.version), reason })}`),
  units: async (project: string): Promise<UnitSummary[]> => {
    const units: UnitSummary[] = [];
    let offset = 0, total = 1;
    while (offset < total) {
      const page = await inventory.units(project, { limit: "200", offset: String(offset), is_active: "true" });
      units.push(...page.units); total = page.total; offset += 200;
    }
    return units;
  },
};
