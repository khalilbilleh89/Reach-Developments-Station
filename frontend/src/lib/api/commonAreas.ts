import { get, post, put, remove } from "./client";

export type CommonArea = { id: string; project_id: string; label: string; category: string; area_sqm: string; apartment_id: string | null; source_reference: string };
const root = (project: string) => `/projects/${project}/inventory/common-areas`;
export const commonAreas = {
  list: (project: string) => get<CommonArea[]>(root(project)),
  create: (project: string, values: Record<string, unknown>) => post<CommonArea>(root(project), values),
  update: (project: string, id: string, values: Record<string, unknown>) => put<CommonArea>(`${root(project)}/${id}`, values),
  remove: (project: string, id: string, reason: string) => remove(`${root(project)}/${id}?${new URLSearchParams({ reason })}`),
};
