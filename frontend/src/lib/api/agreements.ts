import { download, get, post, postBinary, put } from "./client";

export interface AgreementFields {
  name: string;
  signing_company: string;
  draft_created_on: string;
}

export interface Agreement extends AgreementFields {
  id: string;
  filename: string;
  version: number;
}

const base = (projectId: string) => `/projects/${projectId}/agreements`;

export const agreements = {
  list: (projectId: string) => get<Agreement[]>(base(projectId)),
  create: async (projectId: string, fields: AgreementFields, file: File) => {
    if (!file.size || file.size > 10 * 1024 * 1024) throw new Error("Upload a non-empty document up to 10 MB.");
    const query = new URLSearchParams({ ...fields, filename: file.name });
    return postBinary<Agreement>(`${base(projectId)}?${query}`, await file.arrayBuffer());
  },
  update: (projectId: string, row: Agreement, fields: AgreementFields) => put<Agreement>(`${base(projectId)}/${row.id}`, { ...fields, expected_version: row.version }),
  download: (projectId: string, row: Agreement) => download(`${base(projectId)}/${row.id}/document`, row.filename),
  remove: (projectId: string, row: Agreement, reason: string) => post<void>(`${base(projectId)}/${row.id}/delete`, { reason, expected_version: row.version }),
};
