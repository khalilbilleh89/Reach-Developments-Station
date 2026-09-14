import { get, post, put, remove } from "./client";

export type TechnicalSpecification = {
  id: string; project_id: string; category: string; title: string;
  scope: string; applies_to: string; description: string; brand_model: string;
  inclusion: string; status: string; source_reference: string; version: number; updated_at: string;
};
const root = (project: string) => `/projects/${project}/construction/technical-specifications`;
export const technicalSpecifications = {
  list: (project: string) => get<TechnicalSpecification[]>(root(project)),
  create: (project: string, values: Record<string, unknown>) => post<TechnicalSpecification>(root(project), values),
  update: (project: string, id: string, values: Record<string, unknown>) => put<TechnicalSpecification>(`${root(project)}/${id}`, values),
  remove: (project: string, id: string, reason: string) => remove(`${root(project)}/${id}?${new URLSearchParams({ reason })}`),
};
