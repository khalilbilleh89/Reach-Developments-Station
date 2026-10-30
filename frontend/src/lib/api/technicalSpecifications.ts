import { get, post, postBinary, put, remove } from "./client";

export type SpecificationImage = { id: string; filename: string; created_at: string };

export type TechnicalSpecification = {
  id: string; project_id: string; category: string; title: string;
  scope: string; applies_to: string; description: string; buyer_benefit: string; brand_model: string;
  inclusion: string; status: string; source_reference: string; version: number; updated_at: string; images: SpecificationImage[];
};
const root = (project: string) => `/projects/${project}/construction/technical-specifications`;
export const technicalSpecifications = {
  list: (project: string) => get<TechnicalSpecification[]>(root(project)),
  create: (project: string, values: Record<string, unknown>) => post<TechnicalSpecification>(root(project), values),
  update: (project: string, id: string, values: Record<string, unknown>) => put<TechnicalSpecification>(`${root(project)}/${id}`, values),
  addImage: async (project: string, id: string, file: File) => postBinary<SpecificationImage>(root(project) + "/" + id + "/images?" + new URLSearchParams({ filename: file.name }), await file.arrayBuffer()),
  imageUrl: (project: string, id: string, imageId: string) => "/api/v1" + root(project) + "/" + id + "/images/" + imageId + "/file",
  removeImage: (project: string, id: string, imageId: string, reason: string) => remove(root(project) + "/" + id + "/images/" + imageId + "?" + new URLSearchParams({ reason })),
  remove: (project: string, id: string, reason: string) => remove(`${root(project)}/${id}?${new URLSearchParams({ reason })}`),
};
