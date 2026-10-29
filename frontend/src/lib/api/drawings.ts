import { download, get, post, postBinary, put } from "./client";

export const drawingCategories = { general: "General", architecture: "Architecture", structure: "Structure", mep: "MEP", landscape: "Landscape", interiors: "Interiors" };
export const drawingStatuses = { reference: "Reference", for_review: "For review", issued: "Issued", superseded: "Superseded" };
export interface DrawingFields {
  name: string;
  category: keyof typeof drawingCategories;
  drawing_number: string;
  location: string;
  revision: string;
  status: keyof typeof drawingStatuses;
  notes: string;
}
export interface Drawing extends DrawingFields { id: string; filename: string; version: number; created_at: string }
export interface DrawingPreview { page_count: number; image: string }
const base = (projectId: string) => `/projects/${projectId}/drawings`;
export const drawings = {
  list: (projectId: string) => get<Drawing[]>(base(projectId)),
  create: async (projectId: string, fields: DrawingFields, file: File) => {
    if (!file.size || file.size > 10 * 1024 * 1024 || !file.name.toLowerCase().endsWith(".pdf")) throw new Error("Choose a PDF up to 10 MB.");
    return postBinary<Drawing>(`${base(projectId)}?${new URLSearchParams({ ...fields, filename: file.name })}`, await file.arrayBuffer());
  },
  update: (projectId: string, row: Drawing, fields: DrawingFields) => put<Drawing>(`${base(projectId)}/${row.id}`, { ...fields, expected_version: row.version }),
  preview: (projectId: string, row: Drawing, page: number) => get<DrawingPreview>(`${base(projectId)}/${row.id}/preview?page=${page}`),
  download: (projectId: string, row: Drawing) => download(`${base(projectId)}/${row.id}/document`, row.filename),
  remove: (projectId: string, row: Drawing, reason: string) => post<void>(`${base(projectId)}/${row.id}/delete`, { reason, expected_version: row.version }),
};

export function filterDrawings(rows: Drawing[], search: string, category: string, status: string): Drawing[] {
  const term = search.trim().toLocaleLowerCase();
  return rows.filter(row => (!category || row.category === category) && (!status || row.status === status) &&
    [row.name, row.drawing_number, row.location, row.revision, row.filename, row.notes].some(value => value.toLocaleLowerCase().includes(term)));
}
