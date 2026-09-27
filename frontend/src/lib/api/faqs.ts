import { get, post, put, remove } from "./client";

export interface Faq { id: string; question: string; answer: string; version: number }
export interface FaqData { items: Faq[]; can_edit: boolean }
export interface FaqInput { question: string; answer: string }
const base = (project: string) => `/projects/${project}/faqs`;
export const faqs = {
  list: (project: string) => get<FaqData>(base(project)),
  create: (project: string, input: FaqInput) => post<Faq>(base(project), {...input}),
  update: (project: string, row: Faq, input: FaqInput) => put<Faq>(`${base(project)}/${row.id}`, {...input, expected_version: row.version}),
  delete: (project: string, row: Faq, reason: string) => remove(`${base(project)}/${row.id}?${new URLSearchParams({version: String(row.version), reason})}`),
};
