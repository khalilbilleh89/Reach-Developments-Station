import { get, post, put, remove } from "./client";

export type EmailCategory = "internal" | "clients" | "external";
export interface Email { category: EmailCategory; subject: string; id: string; title: string; body: string; version: number }
export interface EmailData { items: Email[]; can_edit: boolean }
export interface EmailInput { category: EmailCategory; subject: string; title: string; body: string }
const base = (project: string) => `/projects/${project}/emails`;
export const emails = {
  list: (project: string) => get<EmailData>(base(project)),
  create: (project: string, input: EmailInput) => post<Email>(base(project), {...input}),
  update: (project: string, row: Email, input: EmailInput) => put<Email>(`${base(project)}/${row.id}`, {...input, expected_version: row.version}),
  delete: (project: string, row: Email, reason: string) => remove(`${base(project)}/${row.id}?${new URLSearchParams({version: String(row.version), reason})}`),
};
